package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.Random;

/**
 * <b>n1zamu/NCaptcha</b> - an anvil-GUI challenge. A random number below 66666 is shown
 * as Unicode superscript digits and the player has to type the plain decimal number.
 *
 * <pre>
 *   nCaptcha/src/main/java/wtf/n1zamu/utils/VerifyUtil.java#verification
 *   nCaptcha/src/main/java/wtf/n1zamu/utils/SuperscriptNumbers.java#convertNumber
 *   nCaptcha/src/main/resources/config.yml   (anvilName: "&amp;7Введите число %number%")
 * </pre>
 */
public final class NCaptcha {

    private NCaptcha() {
    }

    public static final String PLUGIN = "n1zamu/NCaptcha";
    public static final String SRC = "wtf.n1zamu.utils.VerifyUtil#verification";

    /** Superscript mapping exactly as in SuperscriptNumbers.convertNumber. */
    static String superscript(int numeric) {
        StringBuilder sb = new StringBuilder();
        for (char c : String.valueOf(numeric).toCharArray()) {
            int v = Character.getNumericValue(c);
            switch (v) {
                case 1 -> sb.append('¹');
                case 2 -> sb.append('²');
                case 3 -> sb.append('³');
                default -> sb.append((char) ('\u2070' + v));
            }
        }
        return sb.toString();
    }

    public static final class Anvil implements Cg {
        private final Random r = new Random();
        // ThreadLocalRandom.current().nextInt(66666) -> 0..66665
        private final int number = r.nextInt(66666);
        private final BufferedImage img;
        private final int[] roi;

        public Anvil() {
            String title = "&7Введите число " + superscript(number);
            BufferedImage out = McUi.chat(420, 150);
            Graphics2D g = Img.g2d(out, true);

            // Anvil chrome.
            g.setColor(new Color(0xC6, 0xC6, 0xC6));
            g.fillRect(30, 20, 360, 110);
            g.setColor(new Color(0x55, 0x55, 0x55));
            g.drawRect(30, 20, 360, 110);

            // Title strip.
            g.setColor(new Color(0x8B, 0x8B, 0x8B));
            g.fillRect(30, 20, 360, 18);
            McUi.drawColored(g, McUi.codes(title), 34, 33, 13f, true);

            // Left slot: the PAPER item, its name is what gets replaced with superscripts.
            McUi.slotItem(g, 3, 1, 0, new Color(0xF2, 0xF2, 0xF2), "");
            // Input text field, empty.
            g.setColor(new Color(0x8B, 0x8B, 0x8B));
            g.fillRect(92, 52, 130, 22);
            g.setColor(Color.WHITE);
            g.drawRect(92, 52, 130, 22);

            // The superscript number as it appears inside the anvil.
            g.setFont(Img.font("Segoe UI", Font.PLAIN, 16));
            g.setColor(new Color(0x3F, 0x3F, 0x3F));
            g.drawString(superscript(number), 98, 68);

            // Output slot.
            McUi.slotItem(g, 3, 1, 2, new Color(0x37, 0x37, 0x37), "");

            // Footer: what the player must type.
            String footer = "&7Ответ (обычные цифры): &f" + number;
            McUi.drawColored(g, McUi.codes(footer), 34, 145, 12f, true);
            g.dispose();
            img = out;
            roi = footerBand(footer, number);
        }

        /**
         * The band of the plain digits in the footer.
         *
         * <p>The number is printed twice: as Unicode superscripts in the anvil's input
         * field, which is the challenge the plugin means, and as plain digits in the
         * footer, which is the upstream defect this dataset keeps. The band is the
         * plain digits - the only place where the glyphs <i>are</i> the answer, so a
         * recogniser trained on it needs no superscript folding.
         */
        private static int[] footerBand(String footer, int number) {
            Graphics2D g = TextBand.measure();
            try {
                int size = 12;
                String digits = String.valueOf(number);
                TextBand.Hit hit = TextBand.locate(g, footer, digits, size);
                if (hit == null) {
                    return null;
                }
                g.setFont(Img.font("Monospaced", hit.bold() ? Font.BOLD : Font.PLAIN, size));
                FontMetrics fm = g.getFontMetrics();
                return TextBand.box(34 + hit.x(), 145, fm.getAscent(), fm.getDescent(),
                        fm.stringWidth(digits));
            } finally {
                g.dispose();
            }
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "anvil";
        }

        @Override
        public String answer() {
            return String.valueOf(number);
        }

        @Override
        public String prompt() {
            return "Введите число " + superscript(number);
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the plain digits in the footer of the anvil.
         *
         * <p>The frame is an anvil dialog: a title strip that repeats the number as
         * Unicode superscripts, the input field that shows it a second time in the same
         * superscript form, and a footer that prints it in plain digits.
         *
         * <p>The band is the <b>footer</b>, i.e. the plain digits, because that is the
         * only band whose glyphs are the answer itself - a recogniser that reads it
         * produces the answer with no normalisation at all. The superscript form in the
         * input field is the challenge the plugin means; a solver that wants to answer
         * the way a human does crops that field instead (it sits at x=98, baseline y=68,
         * in the 16pt Segoe UI face) and folds the superscripts back into digits.
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