package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

/**
 * <b>FeelingAlive0/AdvancedCaptcha</b> - two clickable-button chat captchas.
 *
 * <pre>
 *   src/main/java/feelingalive/advancedcaptcha/captcha/MathCaptcha.java
 *   src/main/java/feelingalive/advancedcaptcha/captcha/ButtonCaptcha.java
 *   src/main/resources/config.yml, src/main/resources/messages/messages_en.yml
 * </pre>
 */
public final class AdvancedCaptcha {

    private AdvancedCaptcha() {
    }

    public static final String PLUGIN = "FeelingAlive0/AdvancedCaptcha";

    /** config captcha.button-colors */
    static final String[] BUTTON_COLORS = {"BLUE", "GREEN", "RED", "YELLOW", "WHITE", "BLACK", "GRAY", "LIGHT_PURPLE"};

    /** config captcha.math-captcha.allowed-operations */
    static final String[] OPS = {"PLUS", "MINUS", "MULTIPLY"};

    static final int RANGE_MIN = 1;
    static final int RANGE_MAX = 20;
    static final int BUTTON_MIN = 4;
    static final int BUTTON_MAX = 7;

    /** messages captcha.button-texts */
    static final String[] BUTTON_TEXTS = {
            "[Click]", "[Tap]", "[Press]", "[Select]", "[Push]", "[Hit]", "[Choose]", "[Pick]", "[Touch]",
            "[ClickMe]", "[TapHere]", "[PressThis]", "[SelectMe]", "[PushNow]", "[HitThis]", "[ChooseThis]",
            "[PickMe]", "[TouchHere]", "[ClickNow]", "[TapNow]", "[PressNow]", "[SelectNow]", "[PushHere]",
            "[HitNow]", "[ChooseNow]", "[PickNow]", "[TouchThis]", "[ClickThat]", "[TapThat]", "[PressThat]",
            "[SelectThat]", "[PushThat]"};

    /** messages captcha.color-names */
    static String colorName(String chatColor) {
        return switch (chatColor) {
            case "LIGHT_PURPLE" -> "pink";
            default -> chatColor.toLowerCase();
        };
    }

    /** CaptchaManager: RANDOM type picks one of the two handlers. */
    static int buttonCount(Random r) {
        return BUTTON_MIN + r.nextInt(BUTTON_MAX - BUTTON_MIN + 1);
    }

    /**
     * The band of a piece of a chat line.
     *
     * <p>The chat font is a logical font, so its advances are whole pixels and a
     * throw-away measuring context measures exactly what the drawing context measures.
     *
     * @param line the line as it is drawn, with its colour codes
     * @param needle the piece of the line to isolate
     * @param size the point size the line is drawn at
     * @param x the x the line starts at
     * @param baseline the baseline the line is drawn on
     */
    private static int[] band(String line, String needle, int size, int x, int baseline,
                              int frameWidth) {
        Graphics2D g = TextBand.measure();
        try {
            TextBand.Hit hit = TextBand.locate(g, line, needle, size);
            if (hit == null) {
                return null;
            }
            g.setFont(Img.font("Monospaced", hit.bold() ? Font.BOLD : Font.PLAIN, size));
            FontMetrics fm = g.getFontMetrics();
            return TextBand.fits(
                    TextBand.box(x + hit.x(), baseline, fm.getAscent(), fm.getDescent(),
                            fm.stringWidth(needle)),
                    frameWidth, Integer.MAX_VALUE);
        } finally {
            g.dispose();
        }
    }

    /**
     * The band that spans two pieces of a chat line: from the start of the first piece
     * to the end of the second.
     *
     * @param from the piece that starts the band
     * @param to the piece that ends the band
     */
    private static int[] span(String line, String from, String to, int size, int x, int baseline,
                              int frameWidth) {
        Graphics2D g = TextBand.measure();
        try {
            TextBand.Hit hitFrom = TextBand.locate(g, line, from, size);
            TextBand.Hit hitTo = TextBand.locate(g, line, to, size);
            if (hitFrom == null || hitTo == null) {
                return null;
            }
            g.setFont(Img.font("Monospaced",
                    hitFrom.bold() ? Font.BOLD : Font.PLAIN, size));
            FontMetrics fm = g.getFontMetrics();
            int start = hitFrom.x();
            int end = hitTo.x();
            return TextBand.fits(
                    TextBand.box(x + start, baseline, fm.getAscent(), fm.getDescent(),
                            end + fm.stringWidth(to) - start),
                    frameWidth, Integer.MAX_VALUE);
        } finally {
            g.dispose();
        }
    }

    /* ============================================================ MATH CAPTCHA */
    /** MathCaptcha.showCaptcha - expression plus N clickable candidate answers. */
    public static final class Math implements Cg {
        private final Random r = new Random();
        private final int correct;
        private final String expression;
        private final String operands;
        private final BufferedImage img;
        private final int[] roi;

        public Math() {
            String op = OPS[r.nextInt(OPS.length)];
            int n1 = RANGE_MIN + r.nextInt(RANGE_MAX - RANGE_MIN + 1);
            int n2 = RANGE_MIN + r.nextInt(RANGE_MAX - RANGE_MIN + 1);
            int correct = switch (op) {
                case "MINUS" -> n1 - n2;
                case "MULTIPLY" -> n1 * n2;
                default -> n1 + n2;
            };
            this.correct = correct;
            String expression = n1 + " " + ("MULTIPLY".equals(op) ? "*" : "PLUS".equals(op) ? "+" : "-") + " " + n2 + " = ?";
            this.expression = expression;
            // the two operands without the "= ?" - that is the part a solver has to read
            this.operands = n1 + " " + ("MULTIPLY".equals(op) ? "*" : "PLUS".equals(op) ? "+" : "-") + " " + n2;

            // generateAnswers: correct first, decoys within correct + [-5, 4], then shuffled.
            int count = buttonCount(r);
            List<Integer> answers = new ArrayList<>();
            answers.add(correct);
            for (int i = 1; i < count; i++) {
                int wrong;
                do {
                    wrong = correct + r.nextInt(10) - 5;
                } while (answers.contains(wrong));
                answers.add(wrong);
            }
            Collections.shuffle(answers, r);

            List<String> colors = new ArrayList<>(List.of(BUTTON_COLORS));
            Collections.shuffle(colors, r);

            int w = 20 + count * 70;
            BufferedImage base = McUi.chat(w, 84);
            Graphics2D g = Img.g2d(base, true);
            String line = "[AdvancedCaptcha] Solve: " + expression;
            McUi.drawColored(g, McUi.codes(line), 6, 26, 15f, true);
            int x = 6;
            for (int i = 0; i < count; i++) {
                x = McUi.drawColored(g, McUi.codes("§" + mc(colors.get(i % colors.size()))
                        + "[" + answers.get(i) + "]"), x, 58, 15f, true);
                if (i < count - 1) {
                    x = McUi.drawColored(g, McUi.codes("   "), x, 58, 15f, true);
                }
            }
            g.dispose();
            img = base;
            roi = band(line, operands, 15, 6, 26, w);
        }

        private static char mc(String chatColor) {
            return switch (chatColor) {
                case "BLACK" -> '0';
                case "DARK_BLUE" -> '1';
                case "DARK_GREEN" -> '2';
                case "DARK_AQUA" -> '3';
                case "DARK_RED" -> '4';
                case "DARK_PURPLE" -> '5';
                case "GOLD" -> '6';
                case "GRAY" -> '7';
                case "DARK_GRAY" -> '8';
                case "BLUE" -> '9';
                case "GREEN" -> 'a';
                case "AQUA" -> 'b';
                case "RED" -> 'c';
                case "LIGHT_PURPLE" -> 'd';
                case "YELLOW" -> 'e';
                default -> 'f';
            };
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "math";
        }

        @Override
        public String answer() {
            return String.valueOf(correct);
        }

        /**
         * What is actually written in the picture: the two operands and the operator,
         * not the result. The result is worked out by the solver, so the recogniser is
         * trained on the expression the player reads.
         */
        @Override
        public String text() {
            return operands;
        }

        @Override
        public String prompt() {
            return expression;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the expression, in the first line of the chat frame.
         *
         * <p>The frame has two lines: {@code [AdvancedCaptcha] Solve: 7 + 4 = ?} and,
         * below it, the row of clickable candidate answers. The band is the two
         * operands of the first line - the numbers the player has to add up - without
         * the plugin prefix, without the "= ?" and without the candidates below.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return "feelingalive.advancedcaptcha.captcha.MathCaptcha#showCaptcha";
        }
    }

    /* ========================================================== BUTTON CAPTCHA */
    /** ButtonCaptcha.showCaptcha - "Click the [X] button in &lt;colour&gt; color!". */
    public static final class Buttons implements Cg {
        private final Random r = new Random();
        private final String text;
        private final String color;
        private final BufferedImage img;
        private final int[] roi;

        public Buttons() {
            int count = buttonCount(r);
            int correctButton = r.nextInt(count);
            int dup;
            do {
                dup = r.nextInt(count);
            } while (dup == correctButton);

            text = BUTTON_TEXTS[r.nextInt(BUTTON_TEXTS.length)];
            color = BUTTON_COLORS[r.nextInt(BUTTON_COLORS.length)];

            List<String> colors = new ArrayList<>(List.of(BUTTON_COLORS));
            Collections.shuffle(colors, r);
            colors.remove(color);

            List<String> label = new ArrayList<>();
            List<String> col = new ArrayList<>();
            for (int i = 0; i < count; i++) {
                if (i == correctButton) {
                    label.add(text);
                    col.add(color);
                } else if (i == dup) {
                    // Same colour, different text - the actual trap.
                    label.add(BUTTON_TEXTS[r.nextInt(BUTTON_TEXTS.length)]);
                    col.add(color);
                } else {
                    label.add(BUTTON_TEXTS[r.nextInt(BUTTON_TEXTS.length)]);
                    col.add(colors.get(i % colors.size()));
                }
            }

            String line = "[AdvancedCaptcha] Click the " + text
                    + " button in " + colorName(color) + " color!";
            // the frame has to be wide enough for the instruction line: the button
            // labels run up to eleven characters, and a line that runs off the right
            // edge would cut the very words the answer is made of
            int w = McUi.chatWidth(line, 14f, 30 + count * 100);
            BufferedImage base = McUi.chat(w, 84);
            Graphics2D g = Img.g2d(base, true);
            McUi.drawColored(g, McUi.codes(line), 6, 26, 14f, true);
            int x = 6;
            for (int i = 0; i < count; i++) {
                x = McUi.drawColored(g, McUi.codes("§" + mc(col.get(i)) + label.get(i)), x, 58, 15f, true);
                if (i < count - 1) {
                    x = McUi.drawColored(g, "  ", x, 58, 15f, true);
                }
            }
            g.dispose();
            img = base;
            roi = span(line, text, colorName(color), 14, 6, 26, w);
        }

        private static char mc(String chatColor) {
            return switch (chatColor) {
                case "BLACK" -> '0';
                case "GRAY" -> '7';
                case "BLUE" -> '9';
                case "GREEN" -> 'a';
                case "RED" -> 'c';
                case "LIGHT_PURPLE" -> 'd';
                case "YELLOW" -> 'e';
                case "WHITE" -> 'f';
                default -> 'f';
            };
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "button";
        }

        @Override
        public String answer() {
            return text + " in " + colorName(color) + " color";
        }

        @Override
        public String prompt() {
            return "Click the " + text + " button in " + colorName(color) + " color!";
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the button label and the colour name, in the first line of the chat
         * frame.
         *
         * <p>The line reads {@code [AdvancedCaptcha] Click the [Tap] button in blue
         * color!}; the band runs from the label to the end of the colour name, i.e. it
         * holds the two words the answer is made of. The row of clickable buttons below
         * is not part of it - those are the candidates, and the same label is printed on
         * one of them, in a colour the answer also names.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return "feelingalive.advancedcaptcha.captcha.ButtonCaptcha#showCaptcha";
        }
    }
}