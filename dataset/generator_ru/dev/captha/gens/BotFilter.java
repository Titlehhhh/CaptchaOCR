package dev.captcha.gens;

import dev.captcha.Cg;

import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.font.GlyphVector;
import java.awt.geom.AffineTransform;
import java.awt.geom.Point2D;
import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;
import java.awt.image.ConvolveOp;
import java.awt.image.Kernel;
import java.util.Random;

/**
 * Clean-room reimplementation of the map captcha of <b>Leymooo/BungeeCord</b> - the
 * anti-bot plugin ("BotFilter") that ships inside that BungeeCord fork.
 *
 * <h2>What the player sees</h2>
 * A Minecraft map item whose 128x128 canvas carries a short number, drawn in a single
 * colour on a white field:
 * <ul>
 *   <li>the answer is digits only - four digits (1000-9999) or five digits
 *       (10000-99999), each with the same probability;</li>
 *   <li>the font is one of three logical faces at size 50 (sans-serif, serif, or
 *       bold monospaced), picked per captcha;</li>
 *   <li>every digit gets its own rotation and the digits are squeezed together, so
 *       the number reads as a slightly ragged, leaning row;</li>
 *   <li>the whole row is then bent by a horizontal wave and softened by a 3x3 blur;</li>
 *   <li>finally the image is reduced to the 140 colours of the Minecraft map palette,
 *       because the player only ever sees the captcha as a map.</li>
 * </ul>
 * There are no interference lines, no dots, no background image and <b>no caption on
 * the picture</b> - the instruction is a separate chat message.
 *
 * <h2>Provenance</h2>
 * The upstream plugin is Leymooo's BungeeCord fork
 * (<a href="https://github.com/Leymooo/BungeeCord">Leymooo/BungeeCord</a>, author
 * Leymooo / Vjatšeslav Maspanov). Its licence is the md_5/BungeeCord BSD 2-clause
 * <em>plus</em> a clause forbidding commercial hosting use without permission, so the
 * house rule of this repository applies: what is reproduced here is a <b>clean-room
 * reimplementation</b> - the algorithm was read from the upstream source and written
 * again from scratch, with no upstream code, comments, identifiers or copyright
 * headers carried over.
 *
 * <p>Upstream renderer: {@code ru.leymooo.botfilter.captcha.generator.CaptchaPainter#draw}
 * (with {@code ru.leymooo.botfilter.captcha.generator.Rippler} for the wave and
 * {@code ru.leymooo.botfilter.captcha.generator.map.MapPalette} for the colours);
 * the answer, the font choice and the text colour come from
 * {@code ru.leymooo.botfilter.captcha.CaptchaGeneration}.
 *
 * <h2>Upstream quirks, reproduced on purpose</h2>
 * <ul>
 *   <li>The text colour is drawn from the <em>whole</em> palette, the four black
 *       shades included, so a black captcha is possible; only the six near-white
 *       entries are rejected.</li>
 *   <li>The map palette holds four black entries that are never used for matching,
 *       and the palette is larger (144 entries) than the 128 colours a vanilla map
 *       item can show - the upper 16 slots are the "second half" of the map colour
 *       space, which vanilla clients cannot render but the plugin still picks from.</li>
 *   <li>Only the digits change: the code is four or five digits, never a fixed
 *       length, so a solver cannot rely on the length of the answer.</li>
 * </ul>
 */
public final class BotFilter {

    private BotFilter() {
    }

    /** Plugin name, flat, as the {@code dataset/out_ru/} layout expects it. */
    public static final String PLUGIN = "BotFilter";

    /** Upstream file and method this generator reproduces. */
    public static final String SRC = "ru.leymooo.botfilter.captcha.generator.CaptchaPainter#draw";

    /** Edge length of the map canvas. */
    private static final int SIZE = 128;

    /** The instruction the proxy sends to the player in chat. */
    private static final String PROMPT = "Введите код с картинки";

    /** The three logical faces the upstream plugin cycles through, all at size 50. */
    private static final Font[] FONTS = {
            new Font(Font.SANS_SERIF, Font.PLAIN, 50),
            new Font(Font.SERIF, Font.PLAIN, 50),
            new Font(Font.MONOSPACED, Font.BOLD, 50)
    };

    /**
     * The Minecraft map colour palette of the upstream plugin: four black shades
     * (the slots the map uses for "nothing here") followed by the 140 real colours.
     * Packed as {@code 0xRRGGBB}.
     */
    private static final int[] MAP_PALETTE = {
            0x000000, 0x000000, 0x000000, 0x000000,
            0x597D27, 0x6D9930, 0x7FB238, 0x435E1D,
            0xAEA473, 0xD5C98C, 0xF7E9A3, 0x827B56,
            0x8C8C8C, 0xABABAB, 0xC7C7C7, 0x696969,
            0xB40000, 0xDC0000, 0xFF0000, 0x870000,
            0x7070B4, 0x8A8ADC, 0xA0A0FF, 0x545487,
            0x757575, 0x909090, 0xA7A7A7, 0x585858,
            0x005700, 0x006A00, 0x007C00, 0x004100,
            0xB4B4B4, 0xDCDCDC, 0xFFFFFF, 0x878787,
            0x737681, 0x8D909E, 0xA4A8B8, 0x565861,
            0x6A4C36, 0x825E42, 0x976D4D, 0x4F3928,
            0x4F4F4F, 0x606060, 0x707070, 0x3B3B3B,
            0x2D2DB4, 0x3737DC, 0x4040FF, 0x212187,
            0x645432, 0x7B663E, 0x8F7748, 0x4B3F26,
            0xB4B1AC, 0xDCD9D3, 0xFFFCF5, 0x878581,
            0x985924, 0xBA6D2C, 0xD87F33, 0x72431B,
            0x7D3598, 0x9941BA, 0xB24CD8, 0x5E2872,
            0x486C98, 0x5884BA, 0x6699D8, 0x365172,
            0xA1A124, 0xC5C52C, 0xE5E533, 0x79791B,
            0x599011, 0x6DB015, 0x7FCC19, 0x436C0D,
            0xAA5974, 0xD06D8E, 0xF27FA5, 0x804357,
            0x353535, 0x414141, 0x4C4C4C, 0x282828,
            0x6C6C6C, 0x848484, 0x999999, 0x515151,
            0x35596C, 0x416D84, 0x4C7F99, 0x284351,
            0x592C7D, 0x6D3699, 0x7F3FB2, 0x43215E,
            0x24357D, 0x2C4199, 0x334CB2, 0x1B285E,
            0x483524, 0x58412C, 0x664C33, 0x36281B,
            0x485924, 0x586D2C, 0x667F33, 0x36431B,
            0x6C2424, 0x842C2C, 0x993333, 0x511B1B,
            0x111111, 0x151515, 0x191919, 0x0D0D0D,
            0xB0A836, 0xD7CD42, 0xFAEE4D, 0x847E28,
            0x409A96, 0x4FBCB7, 0x5CDBD5, 0x307370,
            0x345AB4, 0x3F6EDC, 0x4A80FF, 0x274387,
            0x009928, 0x00BB32, 0x00D93A, 0x00721E,
            0x5B3C22, 0x6F4A2A, 0x815631, 0x442D19,
            0x4F0100, 0x600100, 0x700200, 0x3B0100
    };

    /** First palette slot that may be used as a match target (the four blacks are not). */
    private static final int FIRST_MATCHABLE = 4;

    /**
     * The map captcha of the BotFilter plugin: digits on a white map, waved, blurred
     * and quantised to the map palette.
     */
    public static final class Map implements Cg {

        private final String answer;
        private final BufferedImage image;

        public Map() {
            this(new Random());
        }

        public Map(Random rnd) {
            this(randomAnswer(rnd), rnd);
        }

        /**
         * Renders one specific answer. Handy to re-render a known number for
         * side-by-side comparisons.
         */
        public Map(String answer) {
            this(answer, new Random());
        }

        private Map(String answer, Random rnd) {
            this.answer = answer;
            this.image = paint(answer, pickFont(rnd), pickTextColour(rnd), rnd);
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
            return answer;
        }

        /** The instruction the proxy prints in chat; the picture itself carries no text. */
        @Override
        public String prompt() {
            return PROMPT;
        }

        @Override
        public BufferedImage image() {
            return image;
        }

        /**
         * No band: the answer fills the frame.
         *
         * <p>The upstream painter scales the digits until they fill the whole 128x128
         * canvas - both axes are scaled by a factor that is computed from the text box -
         * so the numbers cover the map and there is no smaller box around them. The
         * picture carries no other text either; the instruction is a separate chat
         * message.
         */
        @Override
        public int[] roi() {
            return null;
        }

        @Override
        public String source() {
            return SRC;
        }
    }

    /* ----------------------------------------------------------------- picking */

    /** Four or five digits, equally likely - the upstream answer generator. */
    private static String randomAnswer(Random rnd) {
        if (rnd.nextBoolean()) {
            return Integer.toString(rnd.nextInt(99999 - 10000 + 1) + 10000);
        }
        return Integer.toString(rnd.nextInt(9999 - 1000 + 1) + 1000);
    }

    /** One of the three logical faces, uniform. */
    private static Font pickFont(Random rnd) {
        return FONTS[rnd.nextInt(FONTS.length)];
    }

    /**
     * A palette colour for the text. The upstream generator keeps drawing until it
     * gets a colour that is not one of the six near-white entries - the four black
     * slots stay in the pool, so a black captcha is possible.
     */
    private static int pickTextColour(Random rnd) {
        int colour = MAP_PALETTE[rnd.nextInt(MAP_PALETTE.length)];
        while (isNearWhite(colour)) {
            colour = MAP_PALETTE[rnd.nextInt(MAP_PALETTE.length)];
        }
        return colour;
    }

    /** The six palette entries the upstream generator refuses to draw with. */
    private static boolean isNearWhite(int colour) {
        return switch (colour) {
            case 0xFFFFFF, 0xDCDCDC, 0xC7C7C7, 0xFFFCF5, 0xDCD9D3, 0xF7E9A3 -> true;
            default -> false;
        };
    }

    /* ---------------------------------------------------------------- painting */

    /**
     * The whole upstream pipeline: draw the digits, bend them, soften them, and
     * reduce the result to the colours a map item can show.
     */
    private static BufferedImage paint(String answer, Font font, int textColour, Random rnd) {
        BufferedImage canvas = new BufferedImage(SIZE, SIZE, BufferedImage.TYPE_3BYTE_BGR);
        Graphics2D g = canvas.createGraphics();
        try {
            applyQualityHints(g);
            g.setColor(new Color(textColour));
            g.setBackground(Color.WHITE);
            g.setFont(font);
            g.clearRect(0, 0, SIZE, SIZE);

            GlyphVector glyphs = font.createGlyphVector(g.getFontRenderContext(), answer);
            scatterGlyphs(glyphs, rnd);

            Rectangle2D box = glyphs.getPixelBounds(null, 0, SIZE);
            float boxWidth = (float) box.getWidth();
            float boxHeight = (float) box.getHeight();

            float scaleX = SIZE / boxWidth * (rnd.nextFloat() / 20 + 0.89f);
            float scaleY = SIZE / boxHeight * (rnd.nextFloat() / 20 + 0.68f);
            g.translate((SIZE - boxWidth * scaleX) / 2, (SIZE - boxHeight * scaleY) / 2);
            g.scale(scaleX, scaleY);

            float originX = (float) box.getX();
            float originY = (float) box.getY();
            // The stroked copy of the glyphs, nudged by at most 0.64 px sideways and
            // 1.83 px vertically; it is drawn in the text colour, so it only fattens
            // the digits.
            float outlineX = Math.signum(rnd.nextFloat() - 0.5f) * SIZE / 200 - originX;
            float outlineY = Math.signum(rnd.nextFloat() - 0.5f) * SIZE / 70 + SIZE - originY;
            g.draw(glyphs.getOutline(outlineX, outlineY));
            g.drawGlyphVector(glyphs, -originX, SIZE - originY);
        } finally {
            g.dispose();
        }

        return toMapColours(soften(bend(canvas, rnd), rnd));
    }

    /** The rendering hints the upstream painter sets - all of them, they matter. */
    private static void applyQualityHints(Graphics2D g) {
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING,
                RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_FRACTIONALMETRICS,
                RenderingHints.VALUE_FRACTIONALMETRICS_ON);
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING,
                RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_COLOR_RENDERING,
                RenderingHints.VALUE_COLOR_RENDER_QUALITY);
        g.setRenderingHint(RenderingHints.KEY_DITHERING,
                RenderingHints.VALUE_DITHER_ENABLE);
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION,
                RenderingHints.VALUE_INTERPOLATION_BICUBIC);
        g.setRenderingHint(RenderingHints.KEY_ALPHA_INTERPOLATION,
                RenderingHints.VALUE_ALPHA_INTERPOLATION_QUALITY);
        g.setRenderingHint(RenderingHints.KEY_RENDERING,
                RenderingHints.VALUE_RENDER_QUALITY);
    }

    /**
     * Rotates the digits one by one and squeezes them together. The rotation of the
     * first digit is a small random tilt, every following digit adds a step whose
     * sign flips with a probability of a quarter; the horizontal gap between two
     * neighbours is squeezed to about 27-32 % of the narrower digit.
     */
    private static void scatterGlyphs(GlyphVector glyphs, Random rnd) {
        int count = glyphs.getNumGlyphs();
        Point2D previousPosition = null;
        Rectangle2D previousBox = null;

        double angle = (rnd.nextDouble() - 0.5) * Math.PI / 8;
        double step = Math.signum(angle) * (rnd.nextDouble() * 3 * Math.PI / 8 / count);

        for (int i = 0; i < count; i++) {
            AffineTransform turn = AffineTransform.getRotateInstance(angle);
            if (rnd.nextDouble() < 0.25) {
                step = -step;
            }
            angle += step;
            glyphs.setGlyphTransform(i, turn);

            Point2D position = glyphs.getGlyphPosition(i);
            Rectangle2D box = glyphs.getGlyphVisualBounds(i).getBounds2D();
            Point2D target;
            if (previousPosition == null) {
                target = new Point2D.Double(position.getX() - box.getX(), position.getY());
            } else {
                target = new Point2D.Double(
                        previousBox.getMaxX() + position.getX() - box.getX()
                                - Math.min(previousBox.getWidth(), box.getWidth())
                                * (rnd.nextDouble() / 20 + 0.27),
                        position.getY());
            }
            glyphs.setGlyphPosition(i, target);
            previousPosition = target;
            previousBox = glyphs.getGlyphVisualBounds(i).getBounds2D();
        }
    }

    /**
     * The wave: the picture is bent along the vertical axis by up to a tenth of the
     * canvas height and along the horizontal axis by up to a hundredth of its width.
     * A pixel of the source ends up at the displaced position, so the wave really
     * moves the ink instead of only smearing it.
     */
    private static BufferedImage bend(BufferedImage src, Random rnd) {
        int width = src.getWidth();
        int height = src.getHeight();

        int[] verticalShift = waveOffsets(
                rnd.nextDouble() * 2 * Math.PI,
                (1 + rnd.nextDouble() * 2) * Math.PI,
                height / 10.0,
                width);
        int[] horizontalShift = waveOffsets(
                rnd.nextDouble() * 2 * Math.PI,
                (2 + rnd.nextDouble() * 2) * Math.PI,
                width / 100.0,
                height);

        BufferedImage dest = new BufferedImage(width, height, BufferedImage.TYPE_3BYTE_BGR);
        for (int x = 0; x < width; x++) {
            for (int y = 0; y < height; y++) {
                int ny = Math.floorMod(y + verticalShift[x], height);
                int nx = Math.floorMod(x + horizontalShift[ny], width);
                dest.setRGB(nx, ny, src.getRGB(x, y));
            }
        }
        return dest;
    }

    /**
     * The per-axis wave samples: a sine that is folded into one period range and
     * sampled at {@code points} places, rounded to whole pixels.
     */
    private static int[] waveOffsets(double phase, double span, double amplitude, int points) {
        double start = foldInto(phase, 2);
        double length = foldInto(span, 4);
        double step = length / points;
        int[] offsets = new int[points];
        for (int i = 0; i < points; i++) {
            offsets[i] = (int) Math.round(amplitude * Math.sin(start + i * step));
        }
        return offsets;
    }

    /** Folds a value into {@code [0, multiples * PI)}. */
    private static double foldInto(double value, int multiples) {
        double bound = multiples * Math.PI;
        double magnitude = Math.abs(value);
        return magnitude - Math.floor(magnitude / bound) * bound;
    }

    /**
     * The blur: a 3x3 kernel whose nine weights are random and sum up to one. The
     * outer ring of the picture keeps its pixels, the rest is convolved.
     */
    private static BufferedImage soften(BufferedImage src, Random rnd) {
        float[] weights = new float[9];
        float total = 0;
        for (int i = 0; i < weights.length; i++) {
            weights[i] = rnd.nextFloat();
            total += weights[i];
        }
        for (int i = 0; i < weights.length; i++) {
            weights[i] /= total;
        }
        ConvolveOp blur = new ConvolveOp(new Kernel(3, 3, weights), ConvolveOp.EDGE_NO_OP, null);
        return blur.filter(src, null);
    }

    /* ------------------------------------------------------------- quantisation */

    /**
     * The map conversion: every pixel is replaced by the palette colour closest to
     * it. The player receives the captcha as a map item, so this is what the player
     * actually sees - the rendering is not "nearly" palette coloured, it is palette
     * coloured.
     */
    private static BufferedImage toMapColours(BufferedImage src) {
        int width = src.getWidth();
        int height = src.getHeight();
        BufferedImage dest = new BufferedImage(width, height, BufferedImage.TYPE_3BYTE_BGR);
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                dest.setRGB(x, y, nearestMapColour(src.getRGB(x, y)));
            }
        }
        return dest;
    }

    /**
     * The palette match of the upstream map code: a weighted RGB distance, where red
     * and blue count a little less than green, and the red weight grows with the
     * lightness of the pair. The first palette slot with the smallest distance wins.
     */
    private static int nearestMapColour(int argb) {
        int r = (argb >> 16) & 0xFF;
        int g = (argb >> 8) & 0xFF;
        int b = argb & 0xFF;

        int best = -1;
        double bestDistance = -1;
        for (int i = FIRST_MATCHABLE; i < MAP_PALETTE.length; i++) {
            int candidate = MAP_PALETTE[i];
            int cr = (candidate >> 16) & 0xFF;
            int cg = (candidate >> 8) & 0xFF;
            int cb = candidate & 0xFF;

            double mean = (r + cr) / 2.0;
            int dr = r - cr;
            int dg = g - cg;
            int db = b - cb;
            double weightR = 2.0 + mean / 256.0;
            double weightG = 4.0;
            double weightB = 2.0 + (255.0 - mean) / 256.0;
            double distance = weightR * dr * dr + weightG * dg * dg + weightB * db * db;

            if (bestDistance < 0 || distance < bestDistance) {
                bestDistance = distance;
                best = i;
            }
        }
        return 0xFF000000 | MAP_PALETTE[best];
    }
}
