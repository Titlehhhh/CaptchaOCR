package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;

import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.GradientPaint;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.geom.AffineTransform;
import java.awt.image.BufferedImage;
import java.util.concurrent.ThreadLocalRandom;

/**
 * <b>just-captcha/ProstoCaptcha</b> (github.com/just-captcha/ProstoCaptcha, MIT) - the
 * map captcha of a Velocity 3 proxy anti-bot, shown to a joining player in a Limbo
 * world. It is by some distance the busiest generator in this dataset: one 128x128
 * {@code TYPE_INT_RGB} map carrying five noise passes, per-glyph rotation and jitter,
 * a second overlay pass drawn <i>above</i> the text, and a watermark.
 *
 * <pre>
 *   src/main/java/me/prostoac/captcha/CaptchaSessionHandler.java#renderCaptchaImage
 *   src/main/java/me/prostoac/captcha/CaptchaSessionHandler.java#generateCaptchaText
 *   src/main/java/me/prostoac/captcha/CaptchaSessionHandler.java#sanitizeChatInput
 *   src/main/java/me/prostoac/captcha/CaptchaConfig.java#mapAlphabet
 *   src/main/resources/config.yml   (captcha.alphabet, captcha.code-length, timings.captcha-seconds)
 * </pre>
 *
 * <p>There is no distortion filter at all: no ripple, no wave, no shear. Readability is
 * attacked with rotation, jitter and sheer quantity of noise instead.
 *
 * <p><b>Case matters.</b> {@code generateCaptchaText} rolls {@code Character.toUpperCase}
 * / {@code toLowerCase} per letter and {@code onChat} compares
 * {@code sanitizeChatInput(message).equals(mapAnswer)} with no case folding, so the drawn
 * answer must be reproduced character for character, capitalisation included.
 */
public final class Prosto {

    private Prosto() {
    }

    public static final String PLUGIN = "just-captcha/ProstoCaptcha";
    public static final String SRC = "me.prostoac.captcha.CaptchaSessionHandler#renderCaptchaImage";

    /* ----------------------------------------------------------------- config */

    /**
     * {@code captcha.alphabet} exactly as shipped in the plugin's {@code config.yml} -
     * 57 symbols, upper case block first, then lower case, then the digits that lack a
     * lower case form.
     *
     * <p>Both {@code CaptchaConfig#mapAlphabet} and {@code generateCaptchaText} fall back
     * to the 32-symbol upper case-only string {@code "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"}
     * when the key is absent or blank, but a shipped install reads the 57-symbol literal,
     * so that is the one that produces real images.
     *
     * <p>Faithfully inherited quirk: the lower case half drops {@code l} and the upper
     * case half drops {@code I} and {@code O}, so none of them can ever be drawn.
     */
    private static final String ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";

    /**
     * The 32-symbol fallback the code itself reaches for, kept for completeness: it is
     * upper case only and does omit the same three letters.
     */
    private static final String FALLBACK_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

    /** {@code captcha.code-length} (clamped by {@code intValue(..., 6, 4, 12)}). */
    private static final int CODE_LENGTH = 6;

    /** {@code Math.max(4, length)} - the second floor the generator applies itself. */
    private static final int MIN_LENGTH = 4;

    /** {@code timings.captcha-seconds}, clamped by {@code intValue(..., 25, 5, 180)}. */
    private static final int CAPTCHA_SECONDS = 25;

    /* ------------------------------------------------------------------ paint */

    /** The map surface: one Minecraft map pixel is one image pixel. */
    private static final int SIZE = 128;

    /** Gradient endpoints, {@code new GradientPaint(0, 0, a, SIZE, SIZE, b)}. */
    private static final int GRADIENT_FROM = 0x101622; // rgb(16, 22, 34)
    private static final int GRADIENT_TO = 0x223042;   // rgb(34, 48, 66)

    /** The ink the glyphs are drawn in, {@code new Color(235, 242, 255)}. */
    private static final int TEXT_RGB = 0xEBF2FF;

    /** Baseline of the glyph run. */
    private static final int TEXT_BASELINE = 74;

    /** Watermark colour, {@code new Color(255, 200, 80)}. */
    private static final int WATERMARK_RGB = 0xFFC850;

    /* ==================================================================== MAP */

    /**
     * The map captcha: a six glyph mixed-case code centred on a dark blue gradient,
     * buried under 260 translucent specks, 20 hairlines and 9 scan bands drawn before
     * it, and 12 lines plus 10 stripes drawn after it.
     */
    public static final class Captcha implements Cg {

        private final String captcha;
        private final BufferedImage img;
        private final int[] roi;

        public Captcha() {
            captcha = generateCaptchaText(CODE_LENGTH);
            img = renderCaptchaImage(captcha);
            roi = codeBand(captcha);
        }

        /**
         * The band of the code, in the middle of the map.
         *
         * <p>The map is a scene: the code on a dark blue gradient, and a watermark
         * "PROSTO CAPTCHA" in the top left corner. The band is the run of the six
         * glyphs on the baseline y=74; the watermark is 60px above it and stays out.
         *
         * <p>The glyphs are turned by up to 18 degrees and jittered by a few pixels, so
         * the band is a little wider than the run of the text itself.
         */
        private static int[] codeBand(String answer) {
            Graphics2D g = TextBand.measure();
            try {
                g.setFont(new Font("Monospaced", Font.BOLD, 32));
                FontMetrics fm = g.getFontMetrics();
                int textWidth = fm.stringWidth(answer);
                int x = (SIZE - textWidth) / 2;
                int margin = 8;
                return TextBand.inside(
                        TextBand.box(x - margin, TEXT_BASELINE, fm.getAscent() + margin,
                                fm.getDescent() + margin, textWidth + margin * 2),
                        SIZE, SIZE);
            } finally {
                g.dispose();
            }
        }

        /**
         * {@code generateCaptchaText} - one character per iteration from
         * {@code ThreadLocalRandom.current()}, then a coin flip that case-folds every
         * letter. Digits are unaffected because {@code isLetter} is false for them.
         */
        static String generateCaptchaText(int length) {
            String alphabet = ALPHABET;
            if (alphabet == null || alphabet.isBlank()) {
                alphabet = FALLBACK_ALPHABET;
            }
            int safeLength = Math.max(MIN_LENGTH, length);
            StringBuilder builder = new StringBuilder(safeLength);
            ThreadLocalRandom random = ThreadLocalRandom.current();
            for (int i = 0; i < safeLength; i++) {
                char ch = alphabet.charAt(random.nextInt(alphabet.length()));
                if (Character.isLetter(ch)) {
                    ch = random.nextBoolean() ? Character.toUpperCase(ch) : Character.toLowerCase(ch);
                }
                builder.append(ch);
            }
            return builder.toString();
        }

        /**
         * {@code renderCaptchaImage} - reproduced in the original order, because the
         * order is load bearing: a single {@code ThreadLocalRandom} instance feeds every
         * pass, so swapping two loops changes which noise lands where.
         *
         * <p>The Glyph pass is the only part that touches the transform. Each character is
         * rotated about its own draw position, drawn, and then the transform is restored
         * to the identity before the next character - the source captures the transform
         * into a local rather than calling {@code rotate(-angle)}, so the advance used
         * for the next character is always the un-rotated one.
         */
        static BufferedImage renderCaptchaImage(String answer) {
            BufferedImage image = Img.rgb(SIZE, SIZE);
            Graphics2D g = image.createGraphics();
            try {
                // exactly the two hints the source sets - no stroke or interpolation hints
                g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
                g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);

                // The single per-image RNG, shared by every pass below.
                ThreadLocalRandom random = ThreadLocalRandom.current();

                // --- background: one diagonal gradient across the whole surface
                g.setPaint(new GradientPaint(0, 0, new Color(GRADIENT_FROM), SIZE, SIZE, new Color(GRADIENT_TO)));
                g.fillRect(0, 0, SIZE, SIZE);

                // --- 1-3 px translucent specks all over, under everything else
                for (int i = 0; i < 260; i++) {
                    g.setColor(new Color(
                            random.nextInt(30, 190),
                            random.nextInt(30, 190),
                            random.nextInt(30, 190),
                            random.nextInt(30, 150)));
                    g.fillRect(random.nextInt(SIZE), random.nextInt(SIZE),
                            random.nextInt(1, 3), random.nextInt(1, 3));
                }

                // --- 20 full-diagonal hairlines
                g.setStroke(new BasicStroke(2.1f));
                for (int i = 0; i < 20; i++) {
                    g.setColor(new Color(
                            random.nextInt(80, 255),
                            random.nextInt(80, 255),
                            random.nextInt(80, 255),
                            random.nextInt(50, 170)));
                    g.drawLine(random.nextInt(SIZE), random.nextInt(SIZE),
                            random.nextInt(SIZE), random.nextInt(SIZE));
                }

                // --- 9 bright horizontal bands that skip the watermark corner
                for (int i = 0; i < 9; i++) {
                    g.setColor(new Color(
                            random.nextInt(100, 255),
                            random.nextInt(100, 255),
                            random.nextInt(100, 255),
                            random.nextInt(40, 120)));
                    int y = random.nextInt(16, 112);
                    g.fillRect(0, y, SIZE, random.nextInt(1, 3));
                }

                // --- the code itself: one rotated, jittered glyph at a time
                g.setFont(new Font("Monospaced", Font.BOLD, 32));
                int textWidth = g.getFontMetrics().stringWidth(answer);
                int x = (SIZE - textWidth) / 2;
                int y = TEXT_BASELINE;

                for (int i = 0; i < answer.length(); i++) {
                    char ch = answer.charAt(i);
                    AffineTransform original = g.getTransform();
                    double angle = Math.toRadians(random.nextInt(-18, 19));
                    int charX = x + random.nextInt(-2, 3);
                    int charY = y + random.nextInt(-4, 5);
                    g.rotate(angle, charX, charY);
                    g.setColor(new Color(TEXT_RGB));
                    g.drawString(String.valueOf(ch), charX, charY);
                    g.setTransform(original);
                    x += g.getFontMetrics().charWidth(ch);
                }

                // --- overlay pass, drawn ON TOP of the glyphs
                g.setStroke(new BasicStroke(2.5f));
                for (int i = 0; i < 12; i++) {
                    g.setColor(new Color(
                            random.nextInt(140, 255),
                            random.nextInt(120, 240),
                            random.nextInt(120, 240),
                            random.nextInt(90, 180)));
                    int x1 = random.nextInt(SIZE);
                    int y1 = random.nextInt(28, 106);
                    int x2 = random.nextInt(SIZE);
                    int y2 = random.nextInt(28, 106);
                    g.drawLine(x1, y1, x2, y2);
                }
                for (int i = 0; i < 10; i++) {
                    g.setColor(new Color(
                            random.nextInt(120, 255),
                            random.nextInt(120, 255),
                            random.nextInt(120, 255),
                            random.nextInt(70, 150)));
                    int stripeY = random.nextInt(20, 112);
                    g.fillRect(0, stripeY, SIZE, random.nextInt(1, 4));
                }

                // --- watermark, last, over the overlay
                g.setColor(new Color(WATERMARK_RGB));
                g.setFont(new Font("SansSerif", Font.BOLD, 10));
                g.drawString("PROSTO CAPTCHA", 8, 12);
            } finally {
                g.dispose();
            }
            return image;
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "map";
        }

        @Override
        public String answer() {
            return captcha;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the code, in the middle of the map.
         *
         * <p>The frame carries the code and the watermark "PROSTO CAPTCHA" in the top
         * left corner, so it is a scene and not a picture of a string. The band is the
         * six glyphs on the baseline y=74 and it leaves the watermark out.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        /**
         * {@code messages.captcha-start} as the shipped Russian config renders it
         * (the config literal also carries a leading "🧩" icon and colour tags). It is
         * sent once per round with the full allowance, so the number is fixed.
         */
        @Override
        public String prompt() {
            return "Введи код с карты. Время: " + CAPTCHA_SECONDS + " сек.";
        }

        @Override
        public String source() {
            return SRC;
        }
    }
}