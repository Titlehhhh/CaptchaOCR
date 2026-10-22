package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;

import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.Random;

/**
 * Clean-room reimplementation of <b>Mateitaa1/CaptchaVerifyZ</b>
 * ({@code com.Mateitaa1.CaptchaVerifyZ}), the map captcha a joining player is shown.
 *
 * <h2>What the player sees</h2>
 * A Minecraft map item whose 128x128 canvas carries three lines of text on a flat
 * dark-grey field:
 * <ul>
 *   <li>a white header, {@code SECURITY VERIFICATION};</li>
 *   <li>the code itself, in yellow, horizontally centred;</li>
 *   <li>a light-grey footer, {@code Type the code in chat}.</li>
 * </ul>
 * There is no noise of any kind: no interference lines, no curves, no rotation, no
 * per-glyph jitter, no anti-aliasing hints.
 *
 * <h2>Provenance</h2>
 * The upstream jar is published on Modrinth
 * (<a href="https://modrinth.com/plugin/captchaverifyz">captchaverifyz</a>, by
 * {@code mateita254}) under an all-rights-reserved licence, so no upstream code is
 * carried over here. The algorithm was read from the decompiled renderer and rewritten
 * from scratch: canvas size, colours, fonts, positions, the charset literal and the
 * code length are the upstream values, the drawing code is not.
 *
 * <p>Upstream renderer: {@code com/Mateitaa1/CaptchaVerifyZ/CaptchaVerifyZ} - inner class
 * {@code CaptchaMapRenderer}, method {@code render(MapView, MapCanvas, Player)}.
 *
 * <h2>Upstream defect, reproduced on purpose</h2>
 * The plugin also prints the code into the chat window
 * ({@code &a&l➤ &f&l{captcha}} in {@code messages.welcome}, and again in
 * {@code messages.incorrect-attempt}). The image challenge is therefore trivially
 * bypassable by reading chat. A solver that only reads the image is still the right
 * behaviour, but the defect is recorded here rather than hidden.
 */
public final class CaptchaVerifyZ {

    private CaptchaVerifyZ() {
    }

    public static final String PLUGIN = "CaptchaVerifyZ";
    public static final String SRC = "com.Mateitaa1.CaptchaVerifyZ$CaptchaMapRenderer#render";

    /** The map canvas size. */
    private static final int SIZE = 128;

    /** The charset literal from the plugin's default config. */
    private static final String CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

    /** The default code length from the plugin's default config. */
    private static final int LENGTH = 5;

    private static final String HEADER = "SECURITY VERIFICATION";
    private static final String FOOTER = "Type the code in chat";

    /**
     * The map canvas: a flat dark-grey field with a white header, a centred yellow code
     * and a light-grey footer.
     */
    public static final class Map implements Cg {

        /** The random code the plugin would hand out. */
        static String randomCode(Random r) {
            StringBuilder sb = new StringBuilder(LENGTH);
            for (int i = 0; i < LENGTH; i++) {
                sb.append(CHARSET.charAt(r.nextInt(CHARSET.length())));
            }
            return sb.toString();
        }

        private final String code;
        private final BufferedImage img;
        private final int[] roi;

        public Map() {
            this(new Random());
        }

        public Map(Random r) {
            this(randomCode(r));
        }

        /**
         * Renders a specific code. Used by the pixel-diff harness that checks this
         * generator against the reference renders of the upstream algorithm.
         */
        public Map(String code) {
            this.code = code;

            BufferedImage image = new BufferedImage(SIZE, SIZE, BufferedImage.TYPE_INT_RGB);
            // plain createGraphics: the upstream renderer sets no rendering hints at all
            Graphics2D g = image.createGraphics();

            g.setColor(Color.DARK_GRAY);
            g.fillRect(0, 0, SIZE, SIZE);

            g.setColor(Color.WHITE);
            g.setFont(new Font("Arial", Font.BOLD, 12));
            g.drawString(HEADER, 5, 20);

            g.setColor(Color.YELLOW);
            g.setFont(new Font("Arial", Font.BOLD, 24));
            FontMetrics fm = g.getFontMetrics();
            int x = (SIZE - fm.stringWidth(code)) / 2;
            g.drawString(code, x, 70);

            g.setColor(Color.LIGHT_GRAY);
            g.setFont(new Font("Arial", Font.PLAIN, 10));
            g.drawString(FOOTER, 15, 100);

            g.dispose();
            img = image;
            // the band of the yellow code line, and nothing else of the frame
            roi = new int[]{x, 70 - fm.getAscent(), fm.stringWidth(code),
                    fm.getAscent() + fm.getDescent()};
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

        /** The instruction printed under the code, and the one the chat message repeats. */
        @Override
        public String prompt() {
            return FOOTER;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the code, in the middle of the map.
         *
         * <p>The map is a scene: a white header "SECURITY VERIFICATION" on top, the
         * yellow code in the middle and a light grey footer "Type the code in chat"
         * below it. The band is the code line - the five yellow glyphs on the baseline
         * y=70 - and it leaves the header and the footer out.
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
}
