package dev.captcha;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.TreeMap;

/**
 * Small diagnostic: dumps the colour histogram of generated PNGs so the render
 * can be sanity-checked without an image-capable viewer.
 *
 * <pre>java -cp out dev.captcha.Stats out\LagBug\XProtect\map\001.png</pre>
 */
public final class Stats {

    public static void main(String[] args) throws Exception {
        for (String a : args) {
            File f = new File(a);
            if (f.isDirectory()) {
                File[] kids = f.listFiles((d, n) -> n.endsWith(".png"));
                if (kids != null && kids.length > 0) {
                    java.util.Arrays.sort(kids);
                    dump(kids[0]);
                }
                continue;
            }
            dump(f);
        }
    }

    private static void dump(File f) throws Exception {
        BufferedImage img = ImageIO.read(f);
        Map<Integer, Integer> hist = new TreeMap<>();
        for (int y = 0; y < img.getHeight(); y++) {
            for (int x = 0; x < img.getWidth(); x++) {
                hist.merge(img.getRGB(x, y), 1, Integer::sum);
            }
        }
        int total = img.getWidth() * img.getHeight();
        System.out.printf("%n%s  (%dx%d)%n", f.getPath(), img.getWidth(), img.getHeight());
        Map<Integer, Integer> top = new LinkedHashMap<>();
        hist.entrySet().stream()
                .sorted((a, b) -> b.getValue() - a.getValue())
                .limit(8)
                .forEach(e -> top.put(e.getKey(), e.getValue()));
        for (Map.Entry<Integer, Integer> e : top.entrySet()) {
            System.out.printf("   #%06X  %7d px  %5.1f%%%n", e.getKey() & 0xFFFFFF,
                    e.getValue(), 100.0 * e.getValue() / total);
        }
        System.out.println("   distinct colours: " + hist.size());
    }
}