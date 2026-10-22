package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;

import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.util.Locale;
import java.util.Random;

/**
 * <b>ringoame196-s-mcPlugin/ReproductionCAPTCHA</b> - the item-frame map challenge this
 * Paper anti-bot plugin drops into an unverified player's inventory.
 *
 * <p>An operator runs {@code /captcha check <selector>}; every selected player is then
 * silenced (move / break / place / interact all cancel) and nagged with a repeating red
 * title while a yellow subtitle spells out the command to type. A filled map named
 * "認証画像" carries the challenge: five uppercase hex glyphs on a white 128x128 sheet.
 * The answer is checked by {@code /captcha auth <code>} against a row in a SQLite table,
 * and success clears the player.
 *
 * <p>The whole anti-OCR budget of the plugin is spent in five places, all of them per
 * character and all of them statistically independent:
 * <ul>
 *   <li>the face is re-drawn at random from a four entry menu (script, comic, serif,
 *       monospace), so one word can mix four typefaces;</li>
 *   <li>the ink is a fresh RGB triple;</li>
 *   <li>the glyph is tilted about its own origin by at most ~5.7 degrees;</li>
 *   <li>the advance to the next glyph carries a random 0-4 px gap;</li>
 *   <li>the leading margin and baseline are fixed, so there is nothing else to learn.</li>
 * </ul>
 * There is deliberately no noise pass, no interference curve, no per-pixel warp and no
 * background pattern - the surface stays pure white. A clean sheet with mixed typefaces
 * and near-black ink is genuinely weak, which is the point of the reimplementation.
 *
 * <pre>
 *   src/main/kotlin/.../managers/AuthMapManager.kt#makeAuthImage
 *   src/main/kotlin/.../managers/AuthMapManager.kt#creationAuthKey
 * </pre>
 *
 * <p>Clean-room reimplementation: the algorithm and the resulting picture were read from
 * the upstream Kotlin and rewritten here; no upstream code, naming or comments are carried
 * over beyond the {@link #PLUGIN} / {@link #SRC} attribution the dataset requires.
 */
public final class ReproCaptcha {

    private ReproCaptcha() {
    }

    public static final String PLUGIN = "ringoame196-s-mcPlugin/ReproductionCAPTCHA";
    public static final String SRC = "AuthMapManager#makeAuthImage";

    /* ------------------------------------------------------------- geometry */

    /** Square surface size; the map canvas is blitted 1:1 from it. */
    private static final int SIZE = 128;

    /** Baseline sits this far below the vertical midline, so the text reads as centred. */
    private static final int BASELINE_DROP = 24;

    /** Left inset the first glyph is anchored at. */
    private static final int LEFT_INSET = 10;

    /** Every face in the menu is drawn at this point size. */
    private static final int GLYPH_SIZE = 16;

    /* ------------------------------------------------------------------ code */

    /** Lowest code the generator can produce: the sixth hex digit can never be 0. */
    private static final int CODE_MIN = 0x10000;

    /** Highest code the generator can produce. */
    private static final int CODE_MAX = 0xFFFFF;

    /** Inclusive width of the code range, i.e. 0xF0000 = 983040 candidates. */
    private static final int CODE_SPAN = CODE_MAX - CODE_MIN + 1;

    /* ------------------------------------------------------------ appearance */

    /**
     * Ink channels are drawn with a 255-wide bound, so a channel spans 0..254 and no
     * glyph is ever drawn at pure {@code (255,255,255)}. Pure black is reachable,
     * which makes the glyph invisible against the sheet.
     */
    private static final int CHANNEL_BOUND = 255;

    /** Peak tilt in radians; the actual tilt is this span scaled by a -0.5..0.5 draw. */
    private static final double TILT_SPAN = 0.2;

    /** The gap appended after each glyph is drawn from 0..4 px. */
    private static final int GAP_BOUND = 5;

    /** The four faces, in the order the upstream menu lists them. */
    private static final String[] FACE_NAME = {
            "Comic Sans MS", "Brush Script MT", "Serif", "Courier New"};

    /** Matching styles: plain, italic, bold, bold-italic. */
    private static final int[] FACE_STYLE = {
            Font.PLAIN, Font.ITALIC, Font.BOLD, Font.BOLD | Font.ITALIC};

    /* ------------------------------------------------------------ the prompt */

    /** The command line the plugin nags the unverified player with, verbatim. */
    public static final String INSTRUCTION = "/captcha auth <入力>";

    /* =================================================================== MAP */

    /**
     * One issued challenge: a 5 character code and the sheet that shows it.
     *
     * <p>The image is produced once at construction and never redrawn, which matches the
     * plugin - it builds a single {@code BufferedImage}, hands it to a map renderer and
     * from then on the map only blits that one frame.
     */
    public static final class Captcha implements Cg {

        private final String code;
        private final BufferedImage img;
        private final int[] roi;

        /** Menu index each glyph was drawn with; kept for diagnostics. */
        private final int[] faceOfGlyph;

        /** Packed 0xRRGGBB ink each glyph was drawn in; kept for diagnostics. */
        private final int[] inkOfGlyph;

        public Captcha() {
            code = newCode();
            faceOfGlyph = new int[code.length()];
            inkOfGlyph = new int[code.length()];
            int[] band = new int[4];
            img = paint(code, faceOfGlyph, inkOfGlyph, band);
            roi = band;
        }

        /**
         * Diagnostic view of the per-glyph randomness: menu index, resolved face name,
         * style and ink of every glyph, in drawing order, {@code |} separated. Not part of
         * {@link Cg}; used to confirm a sample really mixes faces.
         */
        public String fontTrace() {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < code.length(); i++) {
                if (i > 0) {
                    sb.append('|');
                }
                sb.append(faceOfGlyph[i])
                        .append(':').append(Img.font(FACE_NAME[faceOfGlyph[i]],
                                FACE_STYLE[faceOfGlyph[i]], GLYPH_SIZE).getFamily())
                        .append('/').append(faceToHex(faceOfGlyph[i]))
                        .append('#').append(String.format(Locale.ROOT, "%06X", inkOfGlyph[i]));
            }
            return sb.toString();
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
            return code;
        }

        @Override
        public String prompt() {
            return INSTRUCTION;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the code, in the lower half of the sheet.
         *
         * <p>The sheet is white and carries nothing but the five hex glyphs of the
         * code, but they sit in one line in the lower half of it, so the band is that
         * line - the box the glyphs occupy, from the fixed left inset to the end of the
         * run. The width differs a little from sample to sample, because the gaps
         * between the glyphs are drawn at random.
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

    /* ============================================================ generation */

    /**
     * A uniformly distributed code over the inclusive range above, rendered as exactly
     * five uppercase hex digits. Because the value never drops below 0x10000 the
     * leftmost digit is always 1..F and no padding is ever needed; the declared column
     * width of 5 in the plugin's schema is therefore always exactly filled.
     */
    private static String newCode() {
        return String.format(Locale.ROOT, "%05X", CODE_MIN + new Random().nextInt(CODE_SPAN));
    }

    /**
     * The whole renderer: a white sheet and five independently decorated glyphs walking
     * rightwards from a fixed anchor along a fixed baseline.
     *
     * <p>Every random draw in the upstream loop allocates its own generator, so the face,
     * the three ink channels, the tilt and the gap are independent of one another and of
     * the neighbouring glyph. That is preserved here rather than folded into one stream.
     */
    private static BufferedImage paint(String code, int[] faceOfGlyph, int[] inkOfGlyph,
                                       int[] band) {
        BufferedImage image = Img.rgb(SIZE, SIZE);
        Graphics2D g = image.createGraphics();

        // the sheet is an opaque white fill, not a cleared buffer
        g.setColor(Color.WHITE);
        g.fillRect(0, 0, SIZE, SIZE);

        // shape antialiasing only - glyph antialiasing is deliberately left at its
        // default, which is what keeps the type looking as raw as the plugin's maps do
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);

        int x = LEFT_INSET;
        int y = SIZE / 2 + BASELINE_DROP;
        int ascent = 0;
        int descent = 0;

        for (int i = 0; i < code.length(); i++) {
            String glyph = String.valueOf(code.charAt(i));

            int face = new Random().nextInt(FACE_NAME.length);
            g.setFont(Img.font(FACE_NAME[face], FACE_STYLE[face], GLYPH_SIZE));

            g.setColor(new Color(
                    new Random().nextInt(CHANNEL_BOUND),
                    new Random().nextInt(CHANNEL_BOUND),
                    new Random().nextInt(CHANNEL_BOUND)));

            // tilt about the glyph's own origin, then cancel it again so the next glyph
            // starts from the unrotated frame
            double tilt = (new Random().nextDouble() - 0.5) * TILT_SPAN;
            g.rotate(tilt, x, y);
            g.drawString(glyph, x, y);
            g.rotate(-tilt, x, y);

            faceOfGlyph[i] = face;
            inkOfGlyph[i] = g.getColor().getRGB() & 0xFFFFFF;

            ascent = Math.max(ascent, g.getFontMetrics().getAscent());
            descent = Math.max(descent, g.getFontMetrics().getDescent());

            x += g.getFontMetrics().stringWidth(glyph) + new Random().nextInt(GAP_BOUND);
        }

        // The band of the five glyphs. The tilt is at most five degrees, so the glyphs
        // reach a pixel or two outside their advance box.
        int margin = 2;
        band[0] = LEFT_INSET - margin;
        band[1] = y - ascent - margin;
        band[2] = x - LEFT_INSET + margin;
        band[3] = ascent + descent + margin * 2;

        g.dispose();
        return image;
    }

    /** Plain / italic / bold / bold-italic, for the trace line. */
    private static String faceToHex(int face) {
        return switch (face) {
            case 0 -> "PLAIN";
            case 1 -> "ITALIC";
            case 2 -> "BOLD";
            default -> "BOLD+ITALIC";
        };
    }
}
