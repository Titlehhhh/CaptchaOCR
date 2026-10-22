package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;

import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.GradientPaint;
import java.awt.Graphics2D;
import java.awt.geom.RoundRectangle2D;
import java.awt.image.BufferedImage;
import java.util.Random;

/**
 * The generic web-captcha family, reconstructed from the reference screenshots of the
 * gallery's web-captcha section (70 samples).
 *
 * <h2>What the samples look like</h2>
 * A 150x90 canvas carrying a short mixed-case alphanumeric string, in a display face,
 * over a background that is picked per sample: plain white, a flat colour, a gradient,
 * a diagonal hatch, a scatter of coloured dots, or a graph-paper grid. On top of that
 * sits the usual web-captcha interference - a few coloured strokes, a noise sprinkle, a
 * wavy line - and sometimes a rounded-rectangle border around the whole thing.
 *
 * <h2>Provenance - read this before trusting the pixels</h2>
 * These are <b>not</b> Minecraft plugin output. A 150x90 image of a short string over a
 * decorated background is what a website's "are you human" widget produces, and no
 * Minecraft plugin is responsible for it.
 *
 * <p>More than that: <b>this family has no single generator at all</b>, and that was
 * measured rather than assumed. The gallery's own FAQ says its catalogue covers "more
 * than 6000 kinds of captchas from all over the internet", and the 70 reference samples
 * are a grab bag: 19 RGB / 41 RGBA / 10 palette PNGs, between 2 and 12 728 distinct
 * colours, strings of 3, 4, 5 and 6 characters, a charset that is sometimes
 * digits-only and sometimes Cyrillic, per-character colours in some samples, and
 * backgrounds from plain white to photographs. No one renderer produces that spread -
 * the neighbouring catalogue sections are all uniform, this one is not.
 *
 * <p>Every candidate library was measured from its source and each defaults to a
 * different size (Gregwar/Captcha 150x40, captcha4j 200x50, easy-captcha 200x100,
 * kaptcha 200x50, Securimage 250x75, miraculx/captcha 190x90, claptcha 100x30, ...),
 * so none of them produced this corpus either. The closest algorithmic match is
 * walijoy/captcha-generator, which has the same shape - same charset literal, random
 * length, per-character contrast colour, lines plus noise plus a curve, a folder of
 * background images.
 *
 * <p>So this generator is a reconstruction of the <b>idiom</b>, driven by the reference
 * screenshots: the canvas size, the character count, the character set, the background
 * catalogue, the interference passes and the border are taken from the samples, while
 * the exact face list and the exact probability of each variant are a reconstruction.
 * It is deliberately not labelled as any one library's output.
 *
 * <p>The catalogue's tile-puzzle sections are a separate family: they are the
 * <b>framed</b> captcha of the LimboFilter plugin ({@code LimboFilter/framed3x3} and
 * {@code LimboFilter/framed2x2}), and they are not built from this renderer.
 */
public final class WebCaptcha {

    private WebCaptcha() {
    }

    public static final String PLUGIN = "GalleryCaptcha";
    public static final String SRC = "GalleryCaptcha/ru-web: clean-room reconstruction of the generic "
            + "web-captcha family, measured from reference screenshots; no vendor assets redistributed";

    /** The canvas the web captcha samples are rendered at. */
    static final int W = 150;
    static final int H = 90;


    /** The characters the samples use: mixed case letters and digits. */
    private static final String CHARSET =
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

    /** The number of characters in the samples. */
    private static final int LENGTH = 5;

    /** The faces the samples are set in. */
    private static final String[] FACES = {
            "Times New Roman", "Georgia", "Serif", "Bookman Old Style", "Arial",
            "SansSerif", "Monospaced", "Courier New", "Dialog"};

    /* ============================================================ web captcha */

    /**
     * The base web captcha: a short string over a decorated background.
     */
    public static final class Web implements Cg {

        private final String answer;
        private final BufferedImage img;
        private final int[] roi;

        public Web() {
            this(new Random());
        }

        public Web(Random r) {
            StringBuilder sb = new StringBuilder(LENGTH);
            for (int i = 0; i < LENGTH; i++) {
                sb.append(CHARSET.charAt(r.nextInt(CHARSET.length())));
            }
            answer = sb.toString();
            int[] band = new int[4];
            img = render(r, answer, W, H, band);
            roi = band;
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "ru-web";
        }

        @Override
        public String answer() {
            return answer;
        }

        @Override
        public String prompt() {
            return "Введите символы с картинки";
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the string, in the middle of the picture.
         *
         * <p>The web captcha is a short string over a decorated background: a flat
         * colour, a gradient, a hatch, a scatter of dots or a graph paper, with the
         * usual interference over it and sometimes a border around the whole thing. The
         * band is the run of the five characters - the only text in the frame - so a
         * solver can crop the decoration away.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return SRC;
        }
    }

    /* ------------------------------------------------------------- internals */

    /** A random string of the family's charset. */
    static String randomString(Random r) {
        StringBuilder sb = new StringBuilder(LENGTH);
        for (int i = 0; i < LENGTH; i++) {
            sb.append(CHARSET.charAt(r.nextInt(CHARSET.length())));
        }
        return sb.toString();
    }

    /**
     * The base web captcha renderer.
     */
    static BufferedImage render(Random r, String text, int w, int h, int[] band) {
        BufferedImage image = Img.rgb(w, h);
        Graphics2D g = Img.g2d(image, true);

        // ---- background ----
        Color ink;
        int kind = r.nextInt(6);
        if (kind == 0) {
            g.setColor(Color.WHITE);
            g.fillRect(0, 0, w, h);
            ink = Color.BLACK;
        } else if (kind == 1) {
            Color c = new Color(r.nextInt(256), r.nextInt(256), r.nextInt(256));
            g.setColor(c);
            g.fillRect(0, 0, w, h);
            // the ink is a light or a dark shade of the field, whichever reads
            int lum = (c.getRed() * 30 + c.getGreen() * 59 + c.getBlue() * 11) / 100;
            ink = lum > 140 ? new Color(0x10, 0x10, 0x10) : new Color(0xF0, 0xF0, 0xF0);
        } else if (kind == 2) {
            Color a = new Color(r.nextInt(256), r.nextInt(256), r.nextInt(256));
            Color b = new Color(r.nextInt(256), r.nextInt(256), r.nextInt(256));
            g.setPaint(new GradientPaint(0, 0, a, w, h, b));
            g.fillRect(0, 0, w, h);
            int lum = (a.getRed() * 30 + a.getGreen() * 59 + a.getBlue() * 11) / 100;
            ink = lum > 140 ? new Color(0x10, 0x10, 0x10) : new Color(0xF0, 0xF0, 0xF0);
        } else if (kind == 3) {
            // diagonal hatch
            g.setColor(Color.WHITE);
            g.fillRect(0, 0, w, h);
            g.setColor(new Color(0xE0, 0xE0, 0xE0));
            g.setStroke(new BasicStroke(1f));
            for (int x = -h; x < w; x += 6) {
                g.drawLine(x, 0, x + h, h);
            }
            ink = Color.BLACK;
        } else if (kind == 4) {
            // a scatter of coloured dots
            g.setColor(Color.WHITE);
            g.fillRect(0, 0, w, h);
            for (int i = 0; i < 90; i++) {
                g.setColor(new Color(r.nextInt(256), r.nextInt(256), r.nextInt(256)));
                g.fillOval(r.nextInt(w), r.nextInt(h), 2, 2);
            }
            ink = Color.BLACK;
        } else {
            // graph-paper grid
            g.setColor(Color.WHITE);
            g.fillRect(0, 0, w, h);
            g.setColor(new Color(0xD0, 0xD0, 0xD0));
            g.setStroke(new BasicStroke(1f));
            for (int x = 0; x <= w; x += 10) {
                g.drawLine(x, 0, x, h);
            }
            for (int y = 0; y <= h; y += 10) {
                g.drawLine(0, y, w, y);
            }
            ink = Color.BLACK;
        }

        // ---- the string ----
        String face = FACES[r.nextInt(FACES.length)];
        int style = r.nextBoolean() ? Font.BOLD : Font.PLAIN;
        int size = 30 + r.nextInt(14);
        Font font = Img.font(face, style, size);
        g.setFont(font);
        int tw = g.getFontMetrics().stringWidth(text);
        int x = (w - tw) / 2;
        int y = (h + size) / 2 - 6;

        // a soft drop shadow, the way the samples emboss the glyphs
        g.setColor(new Color(0, 0, 0, 40));
        g.drawString(text, x + 1, y + 1);
        g.setColor(ink);
        g.drawString(text, x, y);

        // The band of the run of characters, shadow included.
        //
        // It is clamped to the canvas: a string that is wider than the canvas starts
        // outside of it, and a band that starts at a negative x is not a rectangle of
        // the picture - a cropper would have to guess what to do with it.
        FontMetrics fm = g.getFontMetrics();
        int bx = Math.max(0, x - 1);
        int by = Math.max(0, y - fm.getAscent() - 1);
        band[0] = bx;
        band[1] = by;
        band[2] = Math.min(w - bx, tw + 3);
        band[3] = Math.min(h - by, fm.getAscent() + fm.getDescent() + 3);

        // ---- interference ----
        int noise = r.nextInt(10);
        if (noise < 4) {
            // coloured strokes across the string
            g.setStroke(new BasicStroke(1.4f));
            for (int i = 0; i < 3; i++) {
                g.setColor(new Color(r.nextInt(256), r.nextInt(256), r.nextInt(256)));
                g.drawLine(r.nextInt(w), r.nextInt(h), r.nextInt(w), r.nextInt(h));
            }
        } else if (noise < 7) {
            // a noise sprinkle
            for (int i = 0; i < 120; i++) {
                g.setColor(new Color(r.nextInt(256), r.nextInt(256), r.nextInt(256)));
                g.fillRect(r.nextInt(w), r.nextInt(h), 1, 1);
            }
        } else if (noise < 9) {
            // a wavy line
            g.setStroke(new BasicStroke(1.4f));
            g.setColor(new Color(r.nextInt(256), r.nextInt(256), r.nextInt(256)));
            int yy = r.nextInt(h);
            g.drawArc(-20, yy - 20, w + 40, 40 + r.nextInt(40), 0, 180);
        }

        // ---- optional border ----
        if (r.nextInt(4) == 0) {
            g.setStroke(new BasicStroke(3f));
            g.setColor(new Color(r.nextInt(256), r.nextInt(256), r.nextInt(256)));
            g.draw(new RoundRectangle2D.Float(2, 2, w - 5, h - 5, 14, 14));
        }

        g.dispose();
        return image;
    }
}