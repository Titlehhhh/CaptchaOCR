package dev.captcha;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Sanity pass over a generated dataset: catches blank frames, duplicated samples and
 * label/image mismatches. Run after {@link Gen}.
 *
 * <pre>java -cp out dev.captcha.Validate out</pre>
 */
public final class Validate {

    public static void main(String[] args) throws Exception {
        Path root = Paths.get(args.length > 0 ? args[0] : "out");
        // Plugin ids contain "/" so the layout is out/<plugin>/<captchaType>/NNN.png.
        List<Path> typeDirs = new ArrayList<>();
        try (var s = Files.walk(root, 3)) {
            s.filter(Files::isDirectory)
                    // real_shots/ holds reference screenshots of the real plugin, not
                    // generated samples: they have no labels.jsonl and are not captcha types
                    .filter(d -> !isUnderRealShots(root, d))
                    .filter(d -> {
                        try (var k = Files.list(d)) {
                            return k.anyMatch(p -> p.getFileName().toString().endsWith(".png"));
                        } catch (Exception e) {
                            return false;
                        }
                    })
                    .sorted()
                    .forEach(typeDirs::add);
        }

        int images = 0;
        int problems = 0;
        for (Path dir : typeDirs) {
            File type = dir.toFile();
            File[] pngs = type.listFiles((d, n) -> n.endsWith(".png"));
            if (pngs == null || pngs.length == 0) {
                continue;
            }
            java.util.Arrays.sort(pngs);
            Set<String> digests = new HashSet<>();
            int blanks = 0;
            int minColors = Integer.MAX_VALUE;
            for (File p : pngs) {
                images++;
                BufferedImage img = ImageIO.read(p);
                int colors = distinctColors(img);
                minColors = Math.min(minColors, colors);
                if (colors <= 2) {
                    blanks++;
                }
                digests.add(hash(img));
            }
            int dupes = pngs.length - digests.size();
            int labels = countLines(dir.resolve("labels.jsonl"));
            boolean ok = blanks == 0 && labels == pngs.length;
            if (!ok) {
                problems++;
            }
            String rel = root.relativize(dir).toString().replace('\\', '/');
            System.out.printf("%-38s n=%3d  minColors=%3d  blank=%d  dupes=%d  labels=%d  %s%n",
                    rel, pngs.length, minColors, blanks, dupes, labels, ok ? "OK" : "<-- CHECK");
        }
        System.out.println("-".repeat(92));
        System.out.printf("%d images, %d captcha types needing a look%n", images, problems);
    }

    private static int countLines(Path p) throws Exception {
        return Files.exists(p) ? (int) Files.lines(p).count() : -1;
    }

    /** True when {@code dir} sits inside a {@code real_shots/} folder of the dataset. */
    private static boolean isUnderRealShots(Path root, Path dir) {
        Path rel = root.relativize(dir);
        for (Path part : rel) {
            if (part.toString().equals("real_shots")) {
                return true;
            }
        }
        return false;
    }

    private static int distinctColors(BufferedImage img) {
        Set<Integer> s = new HashSet<>(4096);
        for (int y = 0; y < img.getHeight(); y++) {
            for (int x = 0; x < img.getWidth(); x++) {
                s.add(img.getRGB(x, y) & 0xFFFFFF);
                if (s.size() > 512) {
                    return s.size();
                }
            }
        }
        return s.size();
    }

    private static String hash(BufferedImage img) {
        try {
            var md = java.security.MessageDigest.getInstance("SHA-1");
            md.update(new java.io.ByteArrayOutputStream() {{
                javax.imageio.ImageIO.write(img, "png", this);
            }}.toByteArray());
            return java.util.HexFormat.of().formatHex(md.digest()).substring(0, 16);
        } catch (Exception e) {
            return "err";
        }
    }
}