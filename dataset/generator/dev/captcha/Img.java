package dev.captcha;

import javax.imageio.ImageIO;
import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.geom.AffineTransform;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.ThreadLocalRandom;

/** Shared drawing / IO helpers used by every captcha reimplementation. */
public final class Img {

    private Img() {
    }

    /* ---------------------------------------------------------------- images */

    public static BufferedImage rgb(int w, int h) {
        return new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
    }

    public static BufferedImage bgr(int w, int h) {
        // XProtect builds its map captcha with TYPE_INT_BGR; the byte order does not
        // change the rendered pixels, only the internal storage layout.
        return new BufferedImage(w, h, BufferedImage.TYPE_INT_BGR);
    }

    public static Graphics2D g2d(BufferedImage img, boolean aa) {
        Graphics2D g = img.createGraphics();
        if (aa) {
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING,
                    RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
            g.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
        }
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION,
                RenderingHints.VALUE_INTERPOLATION_BILINEAR);
        return g;
    }

    /* ----------------------------------------------------------------- fonts */

    private static final List<String> FONT_NAMES = List.of(
            "Arial", "Courier New", "Times New Roman", "Verdana", "Tahoma",
            "Impact", "Comic Sans MS", "Georgia", "Segoe UI", "Trebuchet MS",
            "Palatino Linotype", "Consolas", "Calibri", "Cambria", "Garamond",
            "Bookman Old Style", "Century Gothic", "Lucida Console", "Fixedsys",
            "Monospaced", "SansSerif", "Serif");

    private static final List<Font> CACHE = new ArrayList<>();

    public static synchronized Font font(String name, int style, int size) {
        for (Font f : CACHE) {
            if (f.getName().equalsIgnoreCase(name) && f.getStyle() == style && f.getSize() == size) {
                return f;
            }
        }
        Font f = new Font(name, style, size);
        CACHE.add(f);
        return f;
    }

    /** One of the logical AWT family names, for plugins that randomise the family. */
    public static String randomFamily(Random r) {
        return FONT_NAMES.get(r.nextInt(FONT_NAMES.size()));
    }

    public static int randomStyle(Random r) {
        int[] styles = {Font.PLAIN, Font.BOLD, Font.ITALIC, Font.BOLD | Font.ITALIC};
        return styles[r.nextInt(styles.length)];
    }

    public static String fontLine() {
        return String.join(", ", FONT_NAMES);
    }

    /* ---------------------------------------------------------------- random */

    public static int rnd(Random r, int min, int max) {
        return r.nextInt(max - min) + min;
    }

    /** Bukkit's RandomStringUtils.randomAlphabetic alphabet. */
    public static String alphabetic(int n, Random r) {
        StringBuilder sb = new StringBuilder(n);
        for (int i = 0; i < n; i++) {
            sb.append((char) ('A' + r.nextInt(26)));
        }
        return sb.toString();
    }

    public static String numeric(int n, Random r) {
        StringBuilder sb = new StringBuilder(n);
        for (int i = 0; i < n; i++) {
            sb.append((char) ('0' + r.nextInt(10)));
        }
        return sb.toString();
    }

    /* ------------------------------------------------------------- transform */

    /**
     * The distortion families used by the Java captcha libraries that Bukkit
     * anti-bot plugins wrap (captcha4j, easy-captcha, jhlabs).
     */
    public enum Warp {
        NONE, FISH_EYE, RIPPLE, SHEAR, CURL, WAVE, WATER, TWIRL, SWIRL
    }

    /** Applies a per-pixel distortion to a source image, in place, on the target. */
    public static void distort(BufferedImage src, BufferedImage dst, Warp warp, double amount, Random r) {
        int w = src.getWidth();
        int h = src.getHeight();
        double cx = w / 2.0;
        double cy = h / 2.0;
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                double nx = x;
                double ny = y;
                double dx = x - cx;
                double dy = y - cy;
                switch (warp) {
                    case FISH_EYE -> {
                        double d = Math.sqrt(dx * dx + dy * dy) / (cx * 0.9);
                        double k = 1.0 - 0.28 * amount * (1.0 - Math.max(0, 1 - d * d));
                        nx = cx + dx * k;
                        ny = cy + dy * k;
                    }
                    case RIPPLE -> {
                        double d = Math.sqrt(dx * dx + dy * dy);
                        double k = Math.sin(d / (2.4 + 6.0 * (1 - amount)) * 2.0) * amount * 3.4;
                        double a = Math.atan2(dy, dx);
                        nx = cx + Math.cos(a) * (d + k);
                        ny = cy + Math.sin(a) * (d + k);
                    }
                    case SHEAR -> {
                        nx = x + Math.sin((y / h) * Math.PI) * amount * w * 0.22;
                        ny = y + Math.sin((x / w) * Math.PI) * amount * h * 0.06;
                    }
                    case CURL -> {
                        double u = (x - cx) / cx;
                        double v = (y - cy) / cy;
                        double k = amount * 0.30;
                        nx = cx + cx * (u * Math.cos(k * v) - v * Math.sin(k * v));
                        ny = cy + cy * (u * Math.sin(k * v) + v * Math.cos(k * v));
                    }
                    case WAVE -> {
                        nx = x + Math.sin(y / 7.0 * (1.0 + amount)) * amount * 4.0;
                        ny = y + Math.sin(x / 9.0 * (1.0 + amount)) * amount * 2.0;
                    }
                    case WATER -> {
                        nx = x + Math.sin(x / 6.0 + y / 11.0) * amount * 3.0;
                        ny = y + Math.cos(y / 8.0 - x / 13.0) * amount * 3.0;
                    }
                    case TWIRL -> {
                        double d = Math.sqrt(dx * dx + dy * dy) / (cx * 1.6);
                        double a = amount * d * Math.PI;
                        nx = cx + dx * Math.cos(a) - dy * Math.sin(a);
                        ny = cy + dx * Math.sin(a) + dy * Math.cos(a);
                    }
                    case SWIRL -> {
                        double d = Math.sqrt(dx * dx + dy * dy);
                        double a = (d / (cx * 2.2)) * amount * Math.PI * 1.6;
                        nx = cx + dx * Math.cos(a) - dy * Math.sin(a);
                        ny = cy + dx * Math.sin(a) + dy * Math.cos(a);
                    }
                    default -> {
                    }
                }
                dst.setRGB(x, y, sample(src, nx, ny, r));
            }
        }
    }

    private static int sample(BufferedImage src, double x, double y, Random r) {
        int xi = (int) Math.round(x);
        int yi = (int) Math.round(y);
        if (xi < 0 || yi < 0 || xi >= src.getWidth() || yi >= src.getHeight()) {
            return Color.WHITE.getRGB();
        }
        return src.getRGB(xi, yi);
    }

    /** Rotate + shear a single glyph around a pivot, exactly like the source plugins do. */
    public static AffineTransform charTransform(Graphics2D g, double pivotX, double pivotY,
                                               double rotDeg, double shearX, double shearY) {
        AffineTransform base = g.getTransform();
        AffineTransform t = new AffineTransform(base);
        t.rotate(Math.toRadians(rotDeg), pivotX, pivotY);
        t.shear(shearX, shearY);
        return t;
    }

    /* ------------------------------------------------------------------- io */

    public static void write(BufferedImage img, Path dir, String name) throws IOException {
        Files.createDirectories(dir);
        ImageIO.write(normalize(img), "png", dir.resolve(name).toFile());
    }

    /**
     * XProtect builds its map captcha in a {@code TYPE_INT_BGR} surface, which carries an
     * alpha band ImageIO's PNG writer does not reproduce faithfully. Normalising to a plain
     * RGB surface preserves exactly the pixels the plugin drew.
     *
     * <p>Note: on JDK 21 {@code BufferedImage.getGraphics()} hands back a Graphics2D whose
     * current colour is WHITE, not the black the Graphics2D contract implies. XProtect calls
     * {@code fillRect} before any {@code setColor}, so its map captcha really does have a
     * white background - which is also what makes its BLACK interference lines visible.
     */
    public static BufferedImage normalize(BufferedImage img) {
        int t = img.getType();
        if (t == BufferedImage.TYPE_INT_RGB || t == BufferedImage.TYPE_INT_ARGB) {
            return img;
        }
        BufferedImage out = new BufferedImage(img.getWidth(), img.getHeight(), BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < img.getHeight(); y++) {
            for (int x = 0; x < img.getWidth(); x++) {
                int argb = img.getRGB(x, y);
                // Composite any translucent pixel over black, matching the map renderer.
                int a = (argb >>> 24) & 0xFF;
                int r = (argb >> 16) & 0xFF;
                int g = (argb >> 8) & 0xFF;
                int b = argb & 0xFF;
                if (a != 255) {
                    r = r * a / 255;
                    g = g * a / 255;
                    b = b * a / 255;
                }
                out.setRGB(x, y, (r << 16) | (g << 8) | b);
            }
        }
        return out;
    }

    public static void mkdirs(Path p) throws IOException {
        Files.createDirectories(p);
    }

    public static File file(String rel) {
        return new File(rel);
    }
}