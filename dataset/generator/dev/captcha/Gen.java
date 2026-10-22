package dev.captcha;

import java.awt.image.BufferedImage;
import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Enumeration;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;

import javax.imageio.ImageIO;
import javax.imageio.ImageWriter;
import javax.imageio.spi.IIORegistry;
import javax.imageio.spi.ImageWriterSpi;
import javax.imageio.stream.ImageOutputStream;

/**
 * Generates samples for every captcha type reimplemented in {@code dev.captcha.gens}.
 *
 * <p>Generators are discovered automatically: every public class under
 * {@code dev/captcha/gens} that implements {@link Cg} and exposes a public no-arg
 * constructor is registered. Adding a captcha therefore means adding a generator file
 * (or a {@code public static} nested class) and nothing else - no edit to this class,
 * so parallel contributors never collide here.
 *
 * <pre>
 *   java -Djava.awt.headless=true -cp build dev.captcha.Gen [outDir] [count] [--jobs N]
 * </pre>
 *
 * <h2>Parallel rendering</h2>
 *
 * <p>The samples of every type are rendered by a pool of worker threads. The default
 * worker count is the number of logical processors; {@code --jobs N} picks another one
 * and {@code --jobs 1} restores the old one-thread behaviour.
 *
 * <p><b>What the parallelism does not change.</b> Every sample is still written to
 * {@code NNN.png} with the same NNN, every type still gets its own
 * {@code labels.jsonl} whose rows are in the same order, the types are still visited
 * in the same order and the console table and {@code index.html} have the same shape.
 * Only the wall-clock time changes.
 *
 * <h2>Why it is safe</h2>
 *
 * <ul>
 *   <li>One <b>fresh generator instance per sample</b>, exactly as before - no instance
 *       is ever shared between two threads.</li>
 *   <li>Every sample draws into its <b>own {@link BufferedImage}</b> and its own
 *       {@code Graphics2D}; nothing is drawn into a shared surface.</li>
 *   <li>The only mutable statics in the tree are guarded already: the font cache in
 *       {@link Img} and the lazy font/glyph caches in the generators are
 *       {@code synchronized}, the noise tables are filled in static initialisers and
 *       the one counter ({@code AnBot.STRONG_TOGGLE}) is an {@code AtomicInteger}.</li>
 *   <li>The PNG writer is <b>not</b> shared: {@link ImageIO#write} would drive one
 *       global {@code ImageWriter} instance from several threads at once, and that
 *       instance carries the output stream in a field. Each worker therefore gets its
 *       own writer instance from the PNG {@link ImageWriterSpi}.</li>
 * </ul>
 */
public final class Gen {

    /** Class-path sub-path (dotted package = directory path) scanned for generators. */
    private static final String GENS_PKG = "dev.captcha.gens";

    /** Upper bound for the default worker count (the number of processors is the default). */
    private static final int MAX_DEFAULT_JOBS = 64;

    /** plugin/id -> factory. One fresh instance per call, never a shared one. */
    private static final Map<String, Supplier<Cg>> TYPES = new LinkedHashMap<>();

    /** plugin/id -> the class that claimed it, used only for duplicate diagnostics. */
    private static final Map<String, String> OWNER = new LinkedHashMap<>();

    static {
        // Discovery instantiates one probe per generator, and generators render through AWT.
        System.setProperty("java.awt.headless", "true");
        for (Candidate c : discover()) {
            reg(c);
        }
    }

    /** A generator class plus the metadata read off a single throw-away probe instance. */
    private record Candidate(String className, String plugin, String id, String source) {
    }

    private static void reg(Candidate c) {
        String key = c.plugin() + "|" + c.id();
        if (TYPES.containsKey(key)) {
            warn(c.className(), "duplicate plugin/id '" + key + "' already claimed by "
                    + OWNER.get(key));
            return;
        }
        OWNER.put(key, c.className());
        TYPES.put(key, () -> instantiate(c.className()));
    }

    /** New instance per sample: every generator draws its own {@code new Random()}. */
    private static Cg instantiate(String className) {
        try {
            return (Cg) Class.forName(className, true, Gen.class.getClassLoader())
                    .getConstructor().newInstance();
        } catch (ReflectiveOperationException | RuntimeException | Error e) {
            throw new IllegalStateException("generator " + className + " failed to instantiate", e);
        }
    }

    /** Probe every discovered class, drop the ones that cannot stand in for a generator. */
    private static List<Candidate> discover() {
        List<Candidate> found = new ArrayList<>();
        List<String> names = classNames();
        if (names.isEmpty()) {
            System.err.println("[gen] warning: no compiled classes found under " + GENS_PKG
                    + " on the class path (" + System.getProperty("java.class.path")
                    + ") - nothing will be generated");
            return found;
        }
        for (String name : names) {
            Class<?> c;
            try {
                c = Class.forName(name, false, Gen.class.getClassLoader());
            } catch (Throwable t) {
                warn(name, "not loadable", t);
                continue;
            }
            if (!isGenerator(c)) {
                continue;
            }
            try {
                Cg probe = (Cg) c.getConstructor().newInstance();
                found.add(new Candidate(name, probe.plugin(), probe.id(), probe.source()));
            } catch (Throwable t) {
                warn(name, "not instantiable", t);
            }
        }
        found.sort(Comparator.comparing(Candidate::plugin)
                .thenComparing(Candidate::id)
                .thenComparing(Candidate::className));
        return found;
    }

    /** Public, concrete {@link Cg} with a public no-arg constructor - nested statics included. */
    private static boolean isGenerator(Class<?> c) {
        int mod = c.getModifiers();
        if (!Cg.class.isAssignableFrom(c) || c.isInterface()
                || !Modifier.isPublic(mod) || Modifier.isAbstract(mod)) {
            return false;
        }
        try {
            c.getConstructor(); // only public constructors, exactly zero parameters
            return true;
        } catch (NoSuchMethodException e) {
            return false;
        }
    }

    /** Binary names of every class file under {@code dev/captcha/gens}, dirs and jars alike. */
    private static List<String> classNames() {
        String rel = GENS_PKG.replace('.', '/') + "/";
        Set<String> names = new LinkedHashSet<>();
        for (Path root : classpathRoots()) {
            try {
                if (Files.isDirectory(root)) {
                    Path dir = root.resolve(rel);
                    if (!Files.isDirectory(dir)) {
                        continue;
                    }
                    try (var s = Files.walk(dir)) {
                        s.filter(p -> p.getFileName().toString().endsWith(".class"))
                                .forEach(p -> names.add(binaryName(
                                        dir.relativize(p).toString())));
                    }
                } else if (Files.isRegularFile(root)) {
                    try (JarFile jar = new JarFile(root.toFile())) {
                        Enumeration<JarEntry> es = jar.entries();
                        while (es.hasMoreElements()) {
                            String e = es.nextElement().getName();
                            if (e.endsWith(".class") && e.startsWith(rel)) {
                                names.add(binaryName(e.substring(rel.length())));
                            }
                        }
                    }
                }
            } catch (Exception e) {
                warn(root.toString(), "not scannable", e);
            }
        }
        return new ArrayList<>(names);
    }

    /** {@code XProtect$MapCaptcha.class} -> {@code dev.captcha.gens.XProtect$MapCaptcha}. */
    private static String binaryName(String relPath) {
        String name = relPath.replace(File.separatorChar, '/');
        return GENS_PKG + "." + name.substring(0, name.length() - ".class".length());
    }

    /** The -cp entries plus the location Gen itself was loaded from, dirs first. */
    private static List<Path> classpathRoots() {
        Set<Path> roots = new LinkedHashSet<>();
        for (String e : System.getProperty("java.class.path", "").split(File.pathSeparator)) {
            if (!e.isBlank()) {
                roots.add(Paths.get(e.trim()).toAbsolutePath());
            }
        }
        try {
            var src = Gen.class.getProtectionDomain().getCodeSource();
            if (src != null && src.getLocation() != null) {
                roots.add(Paths.get(src.getLocation().toURI()).toAbsolutePath());
            }
        } catch (Exception ignored) {
            // jdk modules / exotic launchers: the -cp entries above are enough.
        }
        return new ArrayList<>(roots);
    }

    private static void warn(String what, String why) {
        System.err.println("[gen] warning: " + what + ": " + why + " - skipped");
    }

    private static void warn(String what, String why, Throwable t) {
        Throwable c = t;
        while (c instanceof java.lang.reflect.InvocationTargetException && c.getCause() != null) {
            c = c.getCause();
        }
        warn(what, why + " (" + c.getClass().getSimpleName() + ": " + c.getMessage() + ")");
    }

    /* ================================================================== options */

    /** Command line: {@code outDir}, {@code count} and the optional {@code --jobs N}. */
    private record Options(Path out, int count, int jobs) {
    }

    private static Options options(String[] args) {
        Path out = Paths.get("out");
        int count = 100;
        Integer jobs = null;
        List<String> positional = new ArrayList<>();
        for (int i = 0; i < args.length; i++) {
            String a = args[i];
            if (a.equals("--jobs") || a.equals("-j")) {
                if (i + 1 >= args.length) {
                    throw new IllegalArgumentException("--jobs needs a worker count");
                }
                jobs = Integer.parseInt(args[++i]);
            } else if (a.startsWith("--jobs=")) {
                jobs = Integer.parseInt(a.substring("--jobs=".length()));
            } else if (a.equals("--help") || a.equals("-h")) {
                usage();
                System.exit(0);
            } else {
                positional.add(a);
            }
        }
        if (!positional.isEmpty()) {
            out = Paths.get(positional.get(0));
        }
        if (positional.size() > 1) {
            count = Integer.parseInt(positional.get(1));
        }
        if (positional.size() > 2) {
            throw new IllegalArgumentException("unexpected argument: " + positional.get(2));
        }
        int j = jobs == null ? defaultJobs() : jobs;
        if (j < 1) {
            throw new IllegalArgumentException("--jobs must be 1 or more");
        }
        return new Options(out, count, j);
    }

    /** One worker per logical processor, capped so a huge machine cannot melt the box. */
    private static int defaultJobs() {
        return Math.max(1, Math.min(Runtime.getRuntime().availableProcessors(), MAX_DEFAULT_JOBS));
    }

    private static void usage() {
        System.err.println("usage: dev.captcha.Gen [outDir] [count] [--jobs N]");
        System.err.println("  outDir   where the dataset is written (default: out)");
        System.err.println("  count    samples per captcha type (default: 100)");
        System.err.println("  --jobs   worker threads (default: number of processors, "
                + "max " + MAX_DEFAULT_JOBS + "; 1 = the old sequential run)");
    }

    /* ==================================================================== types */

    /** One captcha type: where it goes, how it is produced and what it produced. */
    private static final class TypeJob {
        final String plugin;
        final String id;
        final Path dir;
        final Supplier<Cg> factory;
        /** One label row per sample, kept in sample order so the file stays identical. */
        final String[] rows;
        /** Size of the first sample - the table shows the size of sample 001. */
        int width;
        int height;
        /** Summed worker time spent on this type, and the part of it spent in the PNG encoder. */
        long nanos;
        long pngNanos;

        TypeJob(String plugin, String id, Path dir, Supplier<Cg> factory, int count) {
            this.plugin = plugin;
            this.id = id;
            this.dir = dir;
            this.factory = factory;
            this.rows = new String[count];
        }
    }

    /* ====================================================================== png */

    /**
     * One PNG writer per worker thread.
     *
     * <p>{@link ImageIO#write} hands the image to a writer taken from the global
     * {@code IIORegistry}, and that writer instance is shared by every caller - it
     * keeps the output stream in a field, so two threads writing at the same time
     * would drive the same stream. Each worker therefore asks the PNG
     * {@link ImageWriterSpi} for a writer of its own; the bytes written are the bytes
     * the shared writer would have written.
     */
    private static final ThreadLocal<ImageWriter> PNG_WRITER =
            ThreadLocal.withInitial(Gen::newPngWriter);

    private static ImageWriter newPngWriter() {
        try {
            return pngSpi().createWriterInstance();
        } catch (IOException e) {
            throw new IllegalStateException("no PNG writer available", e);
        }
    }

    private static ImageWriterSpi pngSpi() {
        IIORegistry registry = IIORegistry.getDefaultInstance();
        for (Iterator<ImageWriterSpi> it =
                registry.getServiceProviders(ImageWriterSpi.class, false); it.hasNext(); ) {
            ImageWriterSpi spi = it.next();
            for (String f : spi.getFormatNames()) {
                if (f != null && f.equalsIgnoreCase("png")) {
                    return spi;
                }
            }
        }
        throw new IllegalStateException("no PNG writer SPI on the class path");
    }

    /** Writes one PNG. Same bytes as {@code Img.write} / {@code ImageIO.write}. */
    private static void writePng(BufferedImage img, Path file) throws IOException {
        BufferedImage norm = Img.normalize(img);
        // ImageIO.write deletes the target first - a RandomAccessFile does not truncate.
        Files.deleteIfExists(file);
        ImageWriter writer = PNG_WRITER.get();
        ImageOutputStream stream = ImageIO.createImageOutputStream(file.toFile());
        try {
            writer.setOutput(stream);
            writer.write(norm);
        } finally {
            stream.close();
        }
    }

    /* ==================================================================== main */

    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");
        Options opt = options(args);
        Path out = opt.out;
        int count = opt.count;
        int jobs = opt.jobs;

        Img.mkdirs(out);

        System.out.printf("%-28s %-16s %6s  %s%n", "PLUGIN", "CAPTCHA", "COUNT", "SIZE");
        System.out.println("-".repeat(78));

        List<TypeJob> types = plan(out, count);
        long t0 = System.nanoTime();
        render(types, count, jobs);
        long t1 = System.nanoTime();

        long total = 0;
        for (TypeJob t : types) {
            StringBuilder jsonl = new StringBuilder();
            for (String row : t.rows) {
                jsonl.append(row);
            }
            try (BufferedWriter w = Files.newBufferedWriter(t.dir.resolve("labels.jsonl"),
                    StandardCharsets.UTF_8)) {
                w.write(jsonl.toString());
            }
            System.out.printf("%-28s %-16s %6d  %dx%d%n", t.plugin, t.id, count,
                    t.width, t.height);
            total += count;
        }

        System.out.println("-".repeat(78));
        System.out.printf("%d captcha types x %d = %d images -> %s%n",
                TYPES.size(), count, total, out.toAbsolutePath());
        writeIndex(out, count);

        double sec = (t1 - t0) / 1e9;
        System.err.printf("[gen] %d images in %.1f s with %d worker(s) -> %.1f images/s%n",
                total, sec, jobs, sec == 0 ? 0 : total / sec);
        for (TypeJob t : types) {
            System.err.printf("[gen]   %-28s %-16s worker-time %7.1f s (png %6.1f s)%n",
                    t.plugin, t.id, t.nanos / 1e9, t.pngNanos / 1e9);
        }
    }

    /** One entry per captcha type, in the discovery order, with its output folder ready. */
    private static List<TypeJob> plan(Path out, int count) throws IOException {
        List<TypeJob> types = new ArrayList<>();
        for (Map.Entry<String, Supplier<Cg>> e : TYPES.entrySet()) {
            String[] parts = e.getKey().split("\\|");
            Path dir = out.resolve(parts[0]).resolve(parts[1]);
            Img.mkdirs(dir);
            types.add(new TypeJob(parts[0], parts[1], dir, e.getValue(), count));
        }
        return types;
    }

    /**
     * Renders every sample of every type.
     *
     * <p>The samples are the unit of work: one task renders one sample and writes one
     * PNG. The tasks are handed to the pool round-robin over the types, so the slow
     * types and the fast ones are in flight at the same time and no type is left
     * alone on the tail of the run.
     */
    private static void render(List<TypeJob> types, int count, int jobs) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(jobs, new WorkerFactory());
        List<Future<Void>> futures = new ArrayList<>(types.size() * count);
        try {
            for (int i = 1; i <= count; i++) {
                final int index = i;
                for (TypeJob t : types) {
                    futures.add(pool.submit(new SampleTask(t, index)));
                }
            }
            for (Future<Void> f : futures) {
                f.get();
            }
        } finally {
            pool.shutdown();
            pool.awaitTermination(1, TimeUnit.HOURS);
        }
    }

    /** One sample: a fresh generator, one PNG, one label row. */
    private static final class SampleTask implements Callable<Void> {
        private final TypeJob type;
        private final int index;

        SampleTask(TypeJob type, int index) {
            this.type = type;
            this.index = index;
        }

        @Override
        public Void call() throws Exception {
            long start = System.nanoTime();
            Cg c = type.factory.get();
            BufferedImage img = c.image();
            String name = String.format("%03d.png", index);
            long pngStart = System.nanoTime();
            writePng(img, type.dir.resolve(name));
            type.pngNanos += System.nanoTime() - pngStart;
            if (index == 1) {
                type.width = img.getWidth();
                type.height = img.getHeight();
            }
            type.rows[index - 1] = String.format(
                    "{\"file\":\"%s\",\"plugin\":\"%s\",\"captcha\":\"%s\",\"answer\":\"%s\","
                            + "\"text\":%s,\"prompt\":%s,\"roi\":%s,\"width\":%d,\"height\":%d,\"source\":\"%s\"}%n",
                    name, esc(c.plugin()), esc(c.id()), esc(c.answer()),
                    c.text() == null ? "null" : "\"" + esc(c.text()) + "\"",
                    c.prompt() == null ? "null" : "\"" + esc(c.prompt()) + "\"",
                    roiJson(c.roi()),
                    img.getWidth(), img.getHeight(), esc(c.source()));
            type.nanos += System.nanoTime() - start;
            return null;
        }
    }

    /** Worker threads, named so a stuck run can be recognised in a thread dump. */
    private static final class WorkerFactory implements ThreadFactory {
        private final AtomicInteger seq = new AtomicInteger();

        @Override
        public Thread newThread(Runnable r) {
            Thread t = new Thread(r, "gen-worker-" + seq.incrementAndGet());
            t.setDaemon(true);
            return t;
        }
    }

    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    /** The ROI array as JSON, or {@code null} when the type has no text band. */
    private static String roiJson(int[] roi) {
        if (roi == null || roi.length != 4) {
            return "null";
        }
        return "[" + roi[0] + "," + roi[1] + "," + roi[2] + "," + roi[3] + "]";
    }

    private static void writeIndex(Path out, int count) throws Exception {
        StringBuilder sb = new StringBuilder();
        sb.append("<!doctype html><meta charset=utf-8><title>Captcha dataset</title>\n");
        sb.append("<style>");
        sb.append("body{background:#14161c;color:#ddd;font:14px/1.5 system-ui,-apple-system,Segoe UI;margin:0;padding:28px}");
        sb.append("h1{font-size:20px;margin:0 0 4px}h2{color:#8cf;font-size:15px;margin:34px 0 4px;");
        sb.append("border-bottom:1px solid #2a2f3a;padding-bottom:6px}");
        sb.append(".s{color:#7a8496;font-size:12px;margin-bottom:10px}");
        sb.append(".s b{color:#ffd479}");
        sb.append(".g{display:flex;flex-wrap:wrap;gap:10px}");
        sb.append(".c{background:#000;border:1px solid #2a2f3a;padding:4px;border-radius:4px;text-align:center}");
        sb.append(".c img{display:block;image-rendering:pixelated;max-width:230px;max-height:190px;");
        sb.append("background:repeating-conic-gradient(#222 0 25%,#191b20 0 50%) 0 0/12px 12px}");
        sb.append(".c div{font:11px ui-monospace,Consolas,monospace;color:#6f7c8f;padding-top:3px}");
        sb.append("nav a{color:#8cf;margin-right:14px;font-size:12px}");
        sb.append("</style>\n");

        sb.append("<h1>Minecraft anti-bot captcha dataset</h1>");
        sb.append("<div class=s>").append(TYPES.size()).append(" captcha types &times; ").append(count)
                .append(" samples &middot; showing first 16 of each</div><nav>");
        for (Map.Entry<String, Supplier<Cg>> e : TYPES.entrySet()) {
            String[] p = e.getKey().split("\\|");
            sb.append("<a href=#").append(p[0]).append("_").append(p[1]).append(">")
                    .append(p[0]).append(" / ").append(p[1]).append("</a>");
        }
        sb.append("</nav>\n");

        for (Map.Entry<String, Supplier<Cg>> e : TYPES.entrySet()) {
            String[] parts = e.getKey().split("\\|");
            Path dir = out.resolve(parts[0]).resolve(parts[1]);
            String anchor = parts[0] + "_" + parts[1];
            sb.append("<h2 id=").append(anchor).append(">").append(parts[0]).append(" &middot; ")
                    .append(parts[1]).append("</h2>");
            sb.append("<div class=s>source: <b>").append(sample(e.getValue()))
                    .append("</b></div><div class=g>");
            int show = Math.min(count, 16);
            for (int i = 1; i <= show; i++) {
                sb.append(String.format("<div class=c><img loading=lazy src=\"%s/%s/%03d.png\">"
                        + "<div>%03d &middot; %s</div></div>",
                        parts[0], parts[1], i, i, esc(sampleAnswer(dir, i))));
            }
            sb.append("</div>\n");
        }
        Files.writeString(out.resolve("index.html"), sb.toString());
    }

    private static String sample(Supplier<Cg> f) {
        return f.get().source();
    }

    private static String sampleAnswer(Path dir, int i) {
        try {
            List<String> lines = Files.readAllLines(dir.resolve("labels.jsonl"));
            String l = lines.get(i - 1);
            int a = l.indexOf("\"answer\":\"") + 10;
            return l.substring(a, l.indexOf('"', a));
        } catch (Exception e) {
            return "?";
        }
    }
}
