package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;

import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics;
import java.awt.image.BufferedImage;
import java.util.Random;

/**
 * <b>JSH32/Minecaptcha</b> (riku32.captcha) - a plain 4 character code drawn on a
 * Minecraft map, with a "Type this in chat" header and a tries-left counter.
 *
 * <pre>
 *   src/riku32/captcha/player/CaptchaPlayer.java#render
 *   src/riku32/captcha/events/PlayerEvent.java#genCaptcha
 * </pre>
 */
public final class Minecaptcha {

    private Minecaptcha() {
    }

    public static final String PLUGIN = "JSH32/Minecaptcha";
    public static final String SRC = "riku32.captcha.player.CaptchaPlayer#render";

    /** Exactly the charset literal from genCaptcha(). */
    private static final String CHARSET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

    public static final class Map implements Cg {
        private final String captcha;
        private final int triesLeft;
        private final BufferedImage img;
        private final int[] roi;

        public Map() {
            captcha = genCaptcha();
            triesLeft = 1 + new Random().nextInt(3); // captchaTries=3, tries varies
            img = render(captcha, triesLeft);
            roi = codeBand(img, captcha);
        }

        /**
         * The band of the code, in the middle of the map.
         *
         * <p>The map carries three lines of text: the header "Type this in chat", the
         * tries counter and, below them, the code itself. The band is the glyph box of
         * the code - the line the player has to read - and nothing else of the frame.
         */
        private static int[] codeBand(BufferedImage image, String captcha) {
            Graphics g = image.getGraphics();
            try {
                g.setFont(new Font("Arial", Font.BOLD, 30));
                FontMetrics fm = g.getFontMetrics();
                int x = (int) ((image.getWidth() - fm.getStringBounds(captcha, g).getWidth()) / 2);
                return TextBand.fits(
                        TextBand.box(x, 105, fm.getAscent(), fm.getDescent(),
                                (int) fm.getStringBounds(captcha, g).getWidth()),
                        image.getWidth(), image.getHeight());
            } finally {
                g.dispose();
            }
        }

        /**
         * PlayerEvent.genCaptcha - 4 chars. The source calls nextInt(charset.length() - 1),
         * so the final character of the charset is never produced; kept as-is on purpose.
         */
        static String genCaptcha() {
            Random r = new Random();
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 4; i++) {
                sb.append(CHARSET.charAt(r.nextInt(CHARSET.length() - 1)));
            }
            return sb.toString();
        }

        /** CaptchaPlayer.render() - reproduced line for line. */
        static BufferedImage render(String captcha, int triesLeft) {
            BufferedImage image = new BufferedImage(130, 130, BufferedImage.TYPE_INT_RGB);
            Graphics g = image.getGraphics();
            g.setColor(Color.WHITE);
            g.fillRect(0, 0, image.getWidth(), image.getHeight());

            g.setFont(new Font("Arial", Font.BOLD, 15));
            g.setColor(Color.BLACK);
            String title = "Type this in chat";
            g.drawString(title, (int) ((image.getWidth()
                    - g.getFontMetrics().getStringBounds(title, g).getWidth()) / 2), 30);

            g.setFont(new Font("Arial", Font.BOLD, 10));
            String sTries = "Tries Left: ";
            g.setColor(Color.BLACK);
            g.drawString(sTries, (int) ((image.getWidth()
                    - g.getFontMetrics().getStringBounds(sTries, g).getWidth()) / 2), 45);
            g.setColor(triesLeft == 1 ? Color.RED : Color.GREEN);
            g.drawString(String.valueOf(triesLeft), (int) (((image.getWidth()
                    - g.getFontMetrics().getStringBounds(sTries, g).getWidth()) / 2)
                    + g.getFontMetrics().getStringBounds(sTries, g).getWidth() + 2), 45);

            g.setFont(new Font("Arial", Font.BOLD, 30));
            g.setColor(Color.BLACK);
            g.drawString(captcha, (int) ((image.getWidth()
                    - g.getFontMetrics().getStringBounds(captcha, g).getWidth()) / 2), 105);

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

        /**
         * The band of the code, in the middle of the map.
         *
         * <p>The map is a scene: a header, a tries counter and the code, all on a white
         * field. The band is the line that carries the answer - the four bold glyphs on
         * the baseline y=105 - and it excludes the header and the counter.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        /** The Arial BOLD 15 header {@code render()} draws at y=30 - the whole instruction. */
        @Override
        public String prompt() {
            return "Type this in chat";
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        @Override
        public String source() {
            return SRC;
        }
    }
}