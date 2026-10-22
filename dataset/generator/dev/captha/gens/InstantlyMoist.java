package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.Random;

/**
 * Faithful reimplementation of <b>InstantlyMoist/Captcha</b> (me.kyllian.captcha),
 * the text captcha that is rendered onto a Minecraft map item.
 *
 * <pre>
 *   src/main/java/me/kyllian/captcha/spigot/captchas/TextCaptcha.java
 *   src/main/java/me/kyllian/captcha/spigot/handlers/FontHandler.java
 * </pre>
 */
public final class InstantlyMoist {

    private InstantlyMoist() {
    }

    public static final String PLUGIN = "InstantlyMoist/Captcha";
    public static final String SRC = "me.kyllian.captcha.spigot.captchas.TextCaptcha";

    /** Fonts a server admin drops into the plugin's fonts/ folder; FontHandler derives PLAIN 34. */
    private static final String[] CUSTOM_FONTS = {
            "Comic Sans MS", "Impact", "Papyrus", "Chiller", "Jokerman", "Algerian",
            "Bank Gothic", "Blackadder ITC", "Brush Script MT", "Castellar", "Cooper Black",
            "Javanese Text", "Kristen ITC", "Matura MT Script Capitals", "Old English Text MT"};

    /** One generator instance = one server configuration, reused for many samples. */
    public static final class Text implements Cg {
        private final Random r = new Random();
        private final boolean colorCfg;
        private final boolean linesCfg;
        private final boolean reverseCfg;
        private final boolean randomFont;
        private final String answer;
        private final BufferedImage img;

        public Text() {
            this(new Random());
        }

        public Text(Random cfgRandom) {
            colorCfg = cfgRandom.nextBoolean();
            linesCfg = cfgRandom.nextBoolean();
            reverseCfg = cfgRandom.nextInt(100) < 25;
            randomFont = cfgRandom.nextBoolean();

            // RandomStringUtils.randomAlphabetic(5).toLowerCase()
            answer = Img.alphabetic(5, r).toLowerCase();
            String[] split = answer.split("");

            BufferedImage image = new BufferedImage(128, 128, BufferedImage.TYPE_INT_RGB);
            Graphics2D graphics = Img.g2d(image, true);
            graphics.setColor(Color.WHITE);
            graphics.fillRect(0, 0, 128, 128);

            if (linesCfg) {
                int lines = r.nextInt(15) + 10; // ThreadLocalRandom 10..24
                while (lines != 0) {
                    graphics.setColor(colorCfg ? randomColor() : Color.DARK_GRAY);
                    lines--;
                    graphics.drawLine(rnd(128), rnd(128), rnd(128), rnd(128));
                }
            }

            graphics.setFont(font(r));

            for (int i = 0; i != split.length; i++) {
                var original = graphics.getTransform();
                int rotation = r.nextInt(45); // 0..44
                graphics.rotate(Math.toRadians(rotation) * (r.nextBoolean() ? 1 : -1), 10 + (20 * (i + 1)), 64);
                graphics.setColor(colorCfg ? randomColor() : Color.BLACK);
                graphics.drawString(split[i], (20 * (i + 1)), 70);
                graphics.setTransform(original);
            }
            graphics.dispose();

            this.img = image;
        }

        private static int rnd(int bound) {
            return new Random().nextInt(bound);
        }

        private Color randomColor() {
            return new Color(r.nextInt(255), r.nextInt(255), r.nextInt(255));
        }

        private Font font(Random rr) {
            if (randomFont) {
                return Img.font(CUSTOM_FONTS[rr.nextInt(CUSTOM_FONTS.length)], Font.PLAIN, 34);
            }
            return Img.font("Arial", Font.PLAIN, 34);
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "textcaptcha";
        }

        @Override
        public String answer() {
            return reverseCfg ? new StringBuilder(answer).reverse().toString() : answer;
        }

        /**
         * {@code join} from {@code messages.yml}, verbatim. The map frame itself carries
         * no wording at all, so this line is the entire challenge as the player meets it.
         */
        @Override
        public String prompt() {
            return McUi.strip(
                    "&7Please type the text on the map in order to verify you're a human being");
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * No band: the frame is nothing but the code.
         *
         * <p>The map is a white field with the five rotated characters of the code on
         * it and nothing else - no title, no counter - and the characters are turned by
         * up to 22 degrees each, so they do not form one tight line.
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
}