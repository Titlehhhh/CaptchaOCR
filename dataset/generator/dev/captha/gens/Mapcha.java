package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;

import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.Locale;
import java.util.Random;

/**
 * <b>haq/mapcha</b> (github.com/haq/mapcha, MIT) - the map captcha a joining player
 * has to read off an item frame and type in chat before they are allowed in.
 *
 * <p>The whole challenge is one 128x128 {@code TYPE_INT_RGB} surface handed straight
 * to {@code MapCanvas.drawImage(0, 0, p.render())}: a bold title, a tries-left and a
 * time-left counter, the code itself, and then 100 single-pixel dots plus 10 random
 * lines drawn <i>over</i> everything. There is no rotation, no per-character jitter and
 * no distortion of any kind - the code is four plain bold glyphs on one line.
 *
 * <pre>
 *   src/main/java/dev/affan/mapcha/player/CaptchaPlayer.java#render
 *   src/main/java/dev/affan/mapcha/player/CaptchaPlayer.java#drawTitle
 *   src/main/java/dev/affan/mapcha/player/CaptchaPlayer.java#drawTries
 *   src/main/java/dev/affan/mapcha/player/CaptchaPlayer.java#drawTime
 *   src/main/java/dev/affan/mapcha/player/CaptchaPlayer.java#drawCaptcha
 *   src/main/java/dev/affan/mapcha/player/CaptchaPlayer.java#drawPoints
 *   src/main/java/dev/affan/mapcha/player/CaptchaPlayer.java#drawLines
 *   src/main/java/dev/affan/mapcha/player/CaptchaPlayer.java#generateCaptcha
 *   src/main/java/dev/affan/mapcha/Config.java
 *   src/main/java/dev/affan/mapcha/handlers/MapHandler.java#onMapInitialize
 * </pre>
 *
 * <p>The plugin's own {@code config.yml} is generated at runtime from the field
 * defaults in {@code Config.java}; the constants below are exactly those defaults.
 */
public final class Mapcha {

    private Mapcha() {
    }

    public static final String PLUGIN = "haq/mapcha";
    public static final String SRC = "dev.affan.mapcha.player.CaptchaPlayer#generateCaptcha";

    /* ------------------------------------------------------------- config.yml */

    /** captcha.font */
    private static final String FONT = "Arial";
    /** captcha.title - drawn bold 30 at y=30. */
    private static final String TITLE = "Captcha";
    /** captcha.tries - how many wrong answers a player gets before the kick. */
    private static final int TRIES = 3;
    /** captcha.time - seconds on the clock before KickPlayerTask fires. */
    private static final int TIME_LIMIT = 30;
    /** captcha.invert_color - default false, so BLACK background / WHITE ink. */
    private static final boolean INVERT_COLOR = false;
    /** captcha.points - the 100 single-pixel dots. */
    private static final boolean POINTS = true;
    /** captcha.lines - the 10 interference lines. */
    private static final boolean LINES = true;

    /** The surface size the plugin allocates in the CaptchaPlayer constructor. */
    private static final int SIZE = 128;

    /** The charset literal from generateCaptcha(), digits then lower then upper case. */
    private static final String CHARSET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

    /** What the joining player is told, from the map item's lore in onPlayerJoin. */
    private static final String INSTRUCTION = "Open the map to see the captcha.";

    /* =================================================================== MAP */

    /**
     * The single image captcha: a 4 character code under a "Captcha" title.
     *
     * <p>{@code render()} is invoked by the map renderer on every map update, so the
     * code stays the same while the dots and lines are regenerated each pass. A sample
     * is therefore modelled as one such mid-attempt frame.
     */
    public static final class Map implements Cg {

        private final String captcha;
        private final int triesLeft;
        private final long millisLeft;
        private final BufferedImage img;
        private final int[] roi;

        public Map() {
            Random rnd = new Random();
            captcha = generateCaptcha();
            // onCaptchaFail increments tries once per wrong answer and kicks the player
            // as soon as tries >= TRIES - 1, so a player still playing is on tries 0 or 1.
            triesLeft = TRIES - rnd.nextInt(2);
            // the clock runs from CaptchaPlayer construction down to the kick task
            millisLeft = rnd.nextInt((TIME_LIMIT - 1) * 1000 + 1) + 1000L;
            img = render(captcha, triesLeft, millisLeft);
            roi = codeBand(img, captcha);
        }

        /**
         * The band of the code, in the middle of the map.
         *
         * <p>The map carries four lines of text: the title "Captcha", "Tries Left: n",
         * "Time Left: nn sec" and, below them, the code itself. The band is the glyph
         * box of the code - the line the player has to read - and nothing else of the
         * frame.
         */
        private static int[] codeBand(BufferedImage image, String captcha) {
            Graphics g = image.getGraphics();
            try {
                g.setFont(Img.font(FONT, Font.BOLD, 40));
                FontMetrics fm = g.getFontMetrics();
                int x = centred(g, captcha);
                // a code of four wide glyphs is wider than the map, and then the frame
                // cuts the answer in half - and a cut band is no band
                return TextBand.fits(
                        TextBand.box(x, 105, fm.getAscent(), fm.getDescent(),
                                (int) fm.getStringBounds(captcha, g).getWidth()),
                        image.getWidth(), image.getHeight());
            } finally {
                g.dispose();
            }
        }

        /**
         * The exact 4 character charset literal from generateCaptcha().
         *
         * <p>The source indexes it with {@code charset.length() - 1}, i.e. nextInt(61),
         * so the last entry of the literal - {@code 'Z'} at index 61 - can never be
         * produced. Kept verbatim on purpose: the reachable alphabet really is 61 wide.
         */
        static String generateCaptcha() {
            StringBuilder sb = new StringBuilder(4);
            for (int i = 0; i < 4; i++) {
                // the source builds a fresh Random per character, not one per captcha
                sb.append(CHARSET.charAt(new Random().nextInt(CHARSET.length() - 1)));
            }
            return sb.toString();
        }

        /** {@code render()} plus the four private draw helpers, in the original order. */
        static BufferedImage render(String captcha, int triesLeft, long millisLeft) {
            Color background = INVERT_COLOR ? Color.WHITE : Color.BLACK;
            Color foreground = INVERT_COLOR ? Color.BLACK : Color.WHITE;

            BufferedImage image = Img.rgb(SIZE, SIZE);
            // plain image.getGraphics() as in the source: no antialiasing hints at all
            Graphics2D g = (Graphics2D) image.getGraphics();

            g.setColor(background);
            g.fillRect(0, 0, image.getWidth(), image.getHeight());

            drawTitle(g, foreground);
            drawTries(g, foreground, triesLeft);
            drawTime(g, foreground, millisLeft);
            drawCaptcha(g, foreground, captcha);
            // the noise pass gets its own Random instance per call, as upstream does
            drawPoints(g, foreground, new Random());
            drawLines(g, foreground, new Random());

            g.dispose();
            return image;
        }

        /** drawTitle - bold 30, horizontally centred, baseline at y=30. */
        private static void drawTitle(Graphics2D g, Color color) {
            g.setFont(Img.font(FONT, Font.BOLD, 30));
            g.setColor(color);
            g.drawString(TITLE, centred(g, TITLE), 30);
        }

        /**
         * drawTries - "Tries Left: " in the foreground colour, then the count right
         * after it. The count turns RED when exactly one attempt is left.
         */
        private static void drawTries(Graphics2D g, Color color, int triesLeft) {
            String label = "Tries Left: ";
            g.setFont(Img.font(FONT, Font.BOLD, 10));
            g.setColor(color);
            g.drawString(label, centred(g, label), 45);

            g.setColor(triesLeft == 1 ? Color.RED : Color.GREEN);
            g.drawString(String.valueOf(triesLeft), afterLabel(g, label), 45);
        }

        /**
         * drawTime - "Time Left: " followed by {@code SimpleDateFormat("ss")} of the
         * remaining milliseconds plus a " sec" suffix. The source compares the raw
         * millisecond value against 1000, which in practice is never true, so the
         * clock is green for the whole of a live attempt.
         */
        private static void drawTime(Graphics2D g, Color color, long millisLeft) {
            String label = "Time Left: ";
            g.setFont(Img.font(FONT, Font.BOLD, 10));
            g.setColor(color);
            g.drawString(label, centred(g, label), 55);

            g.setColor(millisLeft == 1000L ? Color.RED : Color.GREEN);
            // DateFormat("ss") of a millisecond value is just seconds mod 60, zero padded
            g.drawString(seconds(millisLeft) + " sec", afterLabel(g, label), 55);
        }

        /**
         * drawCaptcha - the code itself: bold 40, centred, baseline at y=105. The whole
         * string is measured and placed as one run, so the glyphs keep their natural
         * advances and receive no per-character rotation or offset.
         */
        private static void drawCaptcha(Graphics2D g, Color color, String captcha) {
            g.setFont(Img.font(FONT, Font.BOLD, 40));
            g.setColor(color);
            g.drawString(captcha, centred(g, captcha), 105);
        }

        /**
         * drawPoints - 100 dots of one pixel, both coordinates random over the full
         * width but with the y forced into the lower half of the surface.
         */
        private static void drawPoints(Graphics2D g, Color color, Random random) {
            if (!POINTS) {
                return;
            }
            g.setColor(color);
            for (int i = 0; i < 100; i++) {
                g.drawOval(random.nextInt(SIZE), random.nextInt(SIZE / 2) + SIZE / 2, 1, 1);
            }
        }

        /**
         * drawLines - 10 short random segments, again restricted to the lower half.
         * The first x is taken modulo the width, which is a no-op the source still does.
         */
        private static void drawLines(Graphics2D g, Color color, Random random) {
            if (!LINES) {
                return;
            }
            g.setColor(color);
            for (int i = 0; i < 10; i++) {
                g.drawLine(
                        random.nextInt(SIZE) % SIZE,
                        random.nextInt(SIZE / 2) + SIZE / 2,
                        random.nextInt(SIZE),
                        random.nextInt(SIZE / 2) + SIZE / 2);
            }
        }

        /** {@code (int)((SIZE - stringBounds(s).getWidth()) / 2)} from the source. */
        private static int centred(Graphics g, String s) {
            return (int) ((SIZE - g.getFontMetrics().getStringBounds(s, g).getWidth()) / 2);
        }

        /** Label start plus its advance plus the hard-coded 2px gap the source adds. */
        private static int afterLabel(Graphics g, String label) {
            return (int) (centred(g, label) + g.getFontMetrics().getStringBounds(label, g).getWidth() + 2);
        }

        /** What {@code new SimpleDateFormat("ss").format(millis)} prints. */
        private static String seconds(long millis) {
            return String.format(Locale.ROOT, "%02d", (millis / 1000L) % 60L);
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
         * <p>The map is a scene: a title, a tries counter, a clock and the code, all on
         * a black field with noise over it. The band is the line that carries the
         * answer - the four bold glyphs on the baseline y=105 - and it excludes the
         * title, the counters and the footer.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String prompt() {
            return INSTRUCTION;
        }

        @Override
        public String source() {
            return SRC;
        }
    }
}