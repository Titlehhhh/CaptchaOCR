package dev.captcha;

import java.awt.image.BufferedImage;
import java.io.BufferedWriter;
import java.io.File;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Enumeration;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Supplier;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;

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
 *   java -Djava.awt.headless=true -cp build dev.captcha.Gen [outDir] [count]
 * </pre>
 */
public final class Gen {

    /** Class-path sub-path (dotted package = directory path) scanned for generators. */
    private static final String GENS_PKG = "dev.captcha.gens";

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

    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");
        Path out = Paths.get(args.length > 0 ? args[0] : "out");
        int count = args.length > 1 ? Integer.parseInt(args[1]) : 100;

        Img.mkdirs(out);
        List<String> manifest = new ArrayList<>();

        System.out.printf("%-28s %-16s %6s  %s%n", "PLUGIN", "CAPTCHA", "COUNT", "SIZE");
        System.out.println("-".repeat(78));

        long total = 0;
        for (Map.Entry<String, Supplier<Cg>> e : TYPES.entrySet()) {
            String[] parts = e.getKey().split("\\|");
            String plugin = parts[0];
            String id = parts[1];
            Path dir = out.resolve(plugin).resolve(id);
            Img.mkdirs(dir);

            StringBuilder jsonl = new StringBuilder();
            for (int i = 1; i <= count; i++) {
                Cg c = e.getValue().get();
                BufferedImage img = c.image();
                String name = String.format("%03d.png", i);
                Img.write(img, dir, name);
                if (i == 1) {
                    System.out.printf("%-28s %-16s %6d  %dx%d%n", plugin, id, count,
                            img.getWidth(), img.getHeight());
                }
                jsonl.append(String.format(
                        "{\"file\":\"%s\",\"plugin\":\"%s\",\"captcha\":\"%s\",\"answer\":\"%s\","
                                + "\"text\":%s,\"prompt\":%s,\"roi\":%s,\"width\":%d,\"height\":%d,\"source\":\"%s\"}%n",
                        name, esc(c.plugin()), esc(c.id()), esc(c.answer()),
                        c.text() == null ? "null" : "\"" + esc(c.text()) + "\"",
                        c.prompt() == null ? "null" : "\"" + esc(c.prompt()) + "\"",
                        roiJson(c.roi()),
                        img.getWidth(), img.getHeight(), esc(c.source())));
                total++;
            }
            try (BufferedWriter w = Files.newBufferedWriter(dir.resolve("labels.jsonl"),
                    StandardCharsets.UTF_8)) {
                w.write(jsonl.toString());
            }
            manifest.add(plugin + "|" + id);
        }

        System.out.println("-".repeat(78));
        System.out.printf("%d captcha types x %d = %d images -> %s%n",
                TYPES.size(), count, total, out.toAbsolutePath());
        writeIndex(out, count);
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