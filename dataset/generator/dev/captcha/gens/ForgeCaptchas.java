package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.GradientPaint;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.Random;

/**
 * Two captcha screens taken from client-side Minecraft mods that guard a single
 * action instead of guarding a whole server.
 *
 * <ul>
 *   <li><b>laforetbrut/are-you-sure</b> (MIT, Forge + NeoForge, CLIENT) intercepts the
 *       attack / use / pick-block keys and demands a typed 6 character code before it
 *       lets one key press through. The code panel is 140x30 with a dark 0xFF202020
 *       background, forty 2x2 noise dots and six coloured glyphs - no rotation, no
 *       shear, no per-pixel distortion. The only "interference" is a one pixel
 *       translucent strike bar drawn <i>after</i> the glyphs, so it sits on top of them.</li>
 *   <li><b>Mrbysco/Captcha</b> (MIT, Forge, SERVER) pings every player every 50 ticks
 *       with a 20% chance and opens one of two screens. The server code is a 10
 *       character {@code RandomStringUtils.randomAlphanumeric(10)} string that is
 *       <b>never rendered</b>: MathScreen only answers with its own arithmetic sum, and
 *       NotARobotScreen only asks for a tick in a checkbox. The answer of a math sample
 *       is therefore the SUM, never the hidden server code.</li>
 * </ul>
 *
 * <p>Everything below is drawn as a Minecraft GUI screen: a dimmed game backdrop, a
 * centred title/body block, the challenge and the widget strip. The small widget
 * primitives (buttons, edit boxes, checkboxes, the Minecraft text shadow) are private
 * to this file so no shared helper had to be touched.
 *
 * <pre>
 *   laforetbrut/are-you-sure  neoforge-1.21.1 .../com/vyrriox/areyousure/SureScreen.java#newCode
 *   laforetbrut/are-you-sure  neoforge-1.21.1 .../com/vyrriox/areyousure/SureScreen.java#render
 *   Mrbysco/Captcha           src/.../com/mrbysco/captcha/util/CaptchaManager.java#generateRandomCode
 *   Mrbysco/Captcha           src/.../com/mrbysco/captcha/client/screen/MathScreen.java#changeQuestion
 *   Mrbysco/Captcha           src/.../com/mrbysco/captcha/client/ScreenHandler.java#openCaptcha
 *   Mrbysco/Captcha           src/.../com/mrbysco/captcha/handler/CaptchaHandler.java#onPlayerTick
 *   Mrbysco/Captcha           src/.../com/mrbysco/captcha/config/CaptchaConfig.java
 * </pre>
 *
 * <p>Both upstreams are MIT licensed, so a faithful re-render is permitted; every
 * comment here was written for this project rather than copied.
 */
public final class ForgeCaptchas {

    private ForgeCaptchas() {
    }

    /* =================================================================== AYS */

    /**
     * <b>laforetbrut/are-you-sure</b> - SureScreen.newCode().
     *
     * <p>All five constants below are copied verbatim out of SureScreen. The alphabet
     * is deliberately ambiguous-free: it drops {@code I} and {@code O} from the letters
     * and never uses {@code 0} or {@code 1}, which is what makes a six character code
     * readable without any distortion at all.
     */
    public static final String AYS_PLUGIN = "laforetbrut/are-you-sure";
    public static final String AYS_SRC = "com.vyrriox.areyousure.SureScreen#newCode";

    /** 24 letters (no I, no O) followed by 8 digits (no 0, no 1): 32 symbols. */
    private static final String ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    private static final int CODE_LENGTH = 6;
    private static final int NOISE_DOTS = 40;
    /**
     * Seven fully opaque "minecraft-ish" palette entries. The first six are the vanilla
     * chat colour codes rendered at full alpha; the last one, 0xFFFFAA00, is plain orange
     * and does not correspond to any {@code §} code.
     */
    private static final int[] COLORS = {
            0xFFFF5555, 0xFF55FF55, 0xFF5599FF, 0xFFFFFF55, 0xFFFF55FF, 0xFF55FFFF, 0xFFFFAA00};

    /* ================================================================ MRBYSCO */

    public static final String MB_PLUGIN = "Mrbysco/Captcha";
    /**
     * The arithmetic is built by the private {@code changeQuestion()} of MathScreen - the
     * brief guessed that it would live in CaptchaManager, but CaptchaManager only ever
     * produces the hidden alphanumeric string via {@code generateRandomCode()}.
     */
    public static final String MB_SRC = "MathScreen#changeQuestion";

    /** CaptchaManager.generateRandomCode(): RandomStringUtils.randomAlphanumeric(10). */
    public static final int SERVER_CODE_LENGTH = 10;
    /** ScreenHandler.openCaptcha(): nextInt(3) -> 0 and 2 open the checkbox, 1 opens math. */
    private static final int MATH_ODDS = 1;
    private static final int CHECKBOX_ODDS = 2;
    /** CaptchaConfig: captchaTime default 15 (seconds), captchaCooldown default 900 (seconds). */
    public static final int CAPTCHA_TIME = 15;
    public static final int CAPTCHA_COOLDOWN = 900;

    /** The GUI scaled viewport both screens are laid out in: 1920x1080 at GUI scale 4. */
    private static final int SCR_W = 480;
    private static final int SCR_H = 270;

    /** Minecraft's font is a 9px bitmap face; Monospaced at 9pt is the closest stand-in. */
    private static final String MC_FONT = "Monospaced";
    private static final int MC_SIZE = 9;
    /** Minecraft glyphs are 8px tall inside a 9px line, which is what the widgets centre on. */
    private static final int GLYPH_H = 8;

    /** en_us.json strings actually referenced by the two screens. */
    private static final String AYS_TITLE = "ARE YOU SURE?";
    private static final String AYS_QUESTION = "Do you really want to %s?";
    private static final String AYS_WARNING = "This decision could change everything. Think carefully.";
    private static final String AYS_PROMPT = "Prove you are not a robot:";
    private static final String AYS_VERIFY = "Verify";
    private static final String AYS_REFRESH = "New code";
    private static final String AYS_NO = "No, never mind";
    private static final String AYS_WRONG = "Wrong captcha. Here is a new one.";

    private static final String MB_MATH_LINE1 = "Just to prove you are a player,";
    private static final String MB_MATH_LINE2 = "please answer the following math challenge.";
    private static final String MB_MATH_QUESTION = "%s + %s = ?";
    private static final String MB_MATH_NOTE = "Note: When filled in incorrectly it will regenerate.";
    private static final String MB_NOTAROBOT = "Please check the box below to proceed.";
    private static final String MB_CHECKBOX = "I'm not a monster";

    /** areyousure.action.<kind>.<target> - what ActionGuard.describe() can produce. */
    private static final String[] ACTIONS = {
            "break Diamond Ore", "attack Creeper", "swing at the air",
            "interact with Crafting Table", "use Diamond Pickaxe", "use your empty hand",
            "pick Stone", "pick Zombie", "pick nothing at all"};

    /* ============================================================== ARE YOU SURE */

    /**
     * The six character code plus the three per-character arrays and the noise table,
     * i.e. every piece of state SureScreen.newCode() rebuilds in one go.
     */
    public static final class Code {
        final String code;
        final int[] charOffsets;
        final int[] charColors;
        final int[] noise;

        Code(String code, int[] charOffsets, int[] charColors, int[] noise) {
            this.code = code;
            this.charOffsets = charOffsets;
            this.charColors = charColors;
            this.noise = noise;
        }
    }

    /**
     * newCode() reproduced statement for statement, including the order in which the
     * random numbers are pulled: symbol, y jitter, colour per character, then the whole
     * noise table afterwards.
     */
    public static Code newCode(Random random) {
        StringBuilder sb = new StringBuilder();
        int[] charOffsets = new int[CODE_LENGTH];
        int[] charColors = new int[CODE_LENGTH];
        for (int i = 0; i < CODE_LENGTH; i++) {
            sb.append(ALPHABET.charAt(random.nextInt(ALPHABET.length())));
            charOffsets[i] = random.nextInt(9) - 4;
            charColors[i] = COLORS[random.nextInt(COLORS.length)];
        }
        int[] noise = new int[NOISE_DOTS * 3];
        for (int i = 0; i < noise.length; i += 3) {
            noise[i] = random.nextInt(138);
            noise[i + 1] = random.nextInt(28);
            // 0x88FFFFFF only rewrites the alpha byte of a 0xFFRRGGBB palette entry, so
            // every dot keeps its hue at alpha 0x88 and blends over the panel.
            noise[i + 2] = COLORS[random.nextInt(COLORS.length)] & 0x88FFFFFF;
        }
        return new Code(sb.toString(), charOffsets, charColors, noise);
    }

    /**
     * The captcha step of the two step SureScreen confirm dialog.
     *
     * <p>SureScreen does not override renderBackground(), so all the text sits straight on
     * the dimmed game view - there is no dialog panel behind it. Every string is a
     * {@code drawCenteredString} with a one pixel shadow, and the y values are offsets
     * from the vertical centre: title cy-60, question cy-45, prompt cy-32, feedback cy+65.
     * The widget strip sits at cy+10 (the 120x20 edit box) and cy+40 (the three buttons).
     */
    public static final class AreYouSure implements Cg {

        private final Code state;
        private final String action;
        private final BufferedImage img;

        public AreYouSure() {
            Random random = new Random();
            state = newCode(random);
            // ActionGuard.describe() picks the sentence from whatever the player aimed at.
            action = ACTIONS[random.nextInt(ACTIONS.length)];
            img = render(state, action);
        }

        static BufferedImage render(Code state, String action) {
            int cx = SCR_W / 2;
            int cy = SCR_H / 2;

            BufferedImage img = McUi.backdrop(SCR_W, SCR_H);
            Graphics2D g = Img.g2d(img, true);
            g.setFont(Img.font(MC_FONT, Font.PLAIN, MC_SIZE));

            mcCenter(g, AYS_TITLE, cx, cy - 60, 0xFFFF5555);
            mcCenter(g, String.format(AYS_QUESTION, action), cx, cy - 45, 0xFFFFFFFF);
            mcCenter(g, AYS_PROMPT, cx, cy - 32, 0xFFAAAAAA);

            captchaPanel(g, cx, cy, state);

            // init(): the edit box is 120x20 at (cx-60, cy+10) and takes initial focus.
            editBox(g, cx - 60, cy + 10, 120, 20, "", true);
            button(g, cx - 105, cy + 40, 70, 20, AYS_VERIFY);
            button(g, cx - 30, cy + 40, 60, 20, AYS_REFRESH);
            button(g, cx + 35, cy + 40, 70, 20, AYS_NO);

            // feedback is Component.empty() until a wrong code is submitted, so a screen
            // that has just handed out a code draws nothing at cy+65.
            mcCenter(g, "", cx, cy + 65, 0xFFFF5555);

            g.dispose();
            return img;
        }

        /**
         * The 140x30 challenge panel.
         *
         * <p>left/top are the panel corner; the background is one opaque 0xFF202020
         * fill, the forty noise dots are 2x2 fills whose colour is a palette entry at
         * alpha 0x88, and the six glyphs are drawn at a fixed 19px pitch starting 16px
         * in. Minecraft's drawString takes the top of the glyph, so top+11 is the line
         * top and the jitter simply moves that top by -4..+4. The strike bar is a single
         * translucent row and is emitted <i>after</i> the glyph loop, so it covers them.
         */
        static void captchaPanel(Graphics2D g, int cx, int cy, Code state) {
            int left = cx - 70;
            int top = cy - 22;

            mcFill(g, left, top, left + 140, top + 30, 0xFF202020);

            for (int i = 0; i < state.noise.length; i += 3) {
                mcFill(g, left + state.noise[i], top + state.noise[i + 1],
                        left + state.noise[i] + 2, top + state.noise[i + 1] + 2,
                        state.noise[i + 2]);
            }

            for (int i = 0; i < state.code.length(); i++) {
                mcDraw(g, String.valueOf(state.code.charAt(i)),
                        left + 16 + i * 19, top + 11 + state.charOffsets[i],
                        state.charColors[i]);
            }

            mcFill(g, left + 4, top + 15, left + 136, top + 16, 0xAAFFFFFF);
        }

        @Override
        public String plugin() {
            return AYS_PLUGIN;
        }

        @Override
        public String id() {
            return "code";
        }

        @Override
        public String answer() {
            return state.code;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the six code glyphs, in the captcha panel.
         *
         * <p>The screen is a full Minecraft GUI: a title, the question, a prompt, the
         * captcha panel with its 140x30 background, an edit box and three buttons. The
         * band is the code inside the panel - the six coloured glyphs on their 19px
         * pitch, starting 16px inside the panel.
         *
         * <p>The band is the same for every sample: the glyphs are jittered by up to
         * four pixels up and down, and the band is the box that holds them in every
         * case.
         */
        @Override
        public int[] roi() {
            int cx = SCR_W / 2;
            int cy = SCR_H / 2;
            int left = cx - 70;
            int top = cy - 22;
            // the first glyph sits 16px inside the panel, the pitch is 19px and the
            // jitter is at most four pixels up and down
            return new int[]{left + 16, top + 11 - 5, CODE_LENGTH * 19 - 13, 18};
        }

        @Override
        public String prompt() {
            return AYS_PROMPT;
        }

        @Override
        public String source() {
            return AYS_SRC;
        }
    }

    /* =============================================================== MRBYSCO */

    /**
     * The arithmetic question, i.e. MathScreen.changeQuestion().
     *
     * <p>Both operands are {@code (int)(Math.random() * 100)}, so each is 0..99. The
     * 0+0 case never reaches the player: the source replaces it with 9 + 10.
     */
    public static final class Question {
        final int x;
        final int y;
        final int answer;

        Question(int x, int y, int answer) {
            this.x = x;
            this.y = y;
            this.answer = answer;
        }
    }

    public static Question changeQuestion(Random random) {
        int valueX = random.nextInt(100);
        int valueY = random.nextInt(100);
        int answer = valueX + valueY;
        if (answer == 0) {
            valueX = 9;
            valueY = 10;
            answer = 19;
        }
        return new Question(valueX, valueY, answer);
    }

    /**
     * Both of Mrbysco/Captcha's screens.
     *
     * <p>ScreenHandler.openCaptcha() rolls {@code random.nextInt(3)}: two of the three
     * outcomes open the checkbox screen and one opens the math screen. The two screens
     * share the same frame, so they are rendered as one full screen plus the alternate
     * challenge stacked underneath it.
     *
     * <p>The server-side 10 character code
     * ({@code RandomStringUtils.randomAlphanumeric(10)}, produced by
     * {@code CaptchaManager.generateRandomCode()}) is carried through to the client and
     * echoed back in CompletedCaptchaMessage, but neither screen ever draws it: MathScreen
     * compares {@code answerBox.getInt()} against its own sum, NotARobotScreen only reads
     * {@code notARobot.selected()}. That is why the answer of this sample is the SUM.
     */
    public static final class MrbyscoMath implements Cg {

        private final Question question;
        private final String hiddenCode;
        private final boolean mathMode;
        private final BufferedImage img;

        public MrbyscoMath() {
            Random random = new Random();
            question = changeQuestion(random);
            // Generated and checked by the server, but never shown - kept so the state
            // matches what a real CaptchaManager would be holding for this player.
            hiddenCode = randomAlphanumeric(SERVER_CODE_LENGTH, random);
            // Two thirds of the screens are the checkbox one; this sample keeps the
            // math screen in front and stacks the checkbox variant underneath it.
            mathMode = true;
            img = McUi.over(mathScreen(question), notARobotScreen());
        }

        /** CaptchaManager.generateRandomCode() - [A-Za-z0-9], ten characters. */
        static String randomAlphanumeric(int n, Random random) {
            final String alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
            StringBuilder sb = new StringBuilder(n);
            for (int i = 0; i < n; i++) {
                sb.append(alphabet.charAt(random.nextInt(alphabet.length())));
            }
            return sb.toString();
        }

        /**
         * MathScreen. The four line message block is centred at y=70 with a 9px line
         * pitch: the two prompt lines, a blank line, then the yellow "%s + %s = ?".
         * The red note is centred separately at y=120 and the 60x20 NumberEditBox is
         * centred horizontally at y=140.
         */
        static BufferedImage mathScreen(Question q) {
            BufferedImage img = McUi.backdrop(SCR_W, SCR_H);
            Graphics2D g = Img.g2d(img, true);
            g.setFont(Img.font(MC_FONT, Font.PLAIN, MC_SIZE));

            int cx = SCR_W / 2;
            mcCenter(g, MB_MATH_LINE1, cx, 70, 0xFFFFFFFF);
            mcCenter(g, MB_MATH_LINE2, cx, 79, 0xFFFFFFFF);
            // MultiLineLabel renders an empty third line; nothing to draw. The question is
            // the fourth line of a block that starts at y=70, so its top is 70 + 3*9.
            mcColoredCenter(g, McUi.codes("&" + McUi.Mc.YELLOW.code
                    + String.format(MB_MATH_QUESTION, q.x, q.y)), cx, 97);
            mcColoredCenter(g, McUi.codes("&" + McUi.Mc.RED.code + MB_MATH_NOTE), cx, 120);

            // init(): new NumberEditBox(font, 76 + 45, 140, 60, 20, EMPTY) then
            // setX(width/2 - 60/2), so the box ends up 60 wide and horizontally centred.
            // Nothing calls setInitialFocus here, so the box renders unfocused.
            editBox(g, cx - 30, 140, 60, 20, "", false);

            g.dispose();
            return img;
        }

        /**
         * NotARobotScreen. The single prompt line is wrapped to width-50 and centred at
         * y=70; the checkbox sits 18px below it (76 + (1 line + 1) * 9) and is offset
         * left by its own label width plus 20 so the whole control group is centred.
         */
        static BufferedImage notARobotScreen() {
            BufferedImage img = McUi.backdrop(SCR_W, SCR_H);
            Graphics2D g = Img.g2d(img, true);
            g.setFont(Img.font(MC_FONT, Font.PLAIN, MC_SIZE));

            int cx = SCR_W / 2;
            mcCenter(g, MB_NOTAROBOT, cx, 70, 0xFFFFFFFF);
            checkbox(g, cx - mcWidth(g, MB_CHECKBOX) - 20, 94, MB_CHECKBOX, false);

            g.dispose();
            return img;
        }

        @Override
        public String plugin() {
            return MB_PLUGIN;
        }

        @Override
        public String id() {
            return "math";
        }

        /**
         * The ground truth is the SUM of the two operands, not the hidden server code:
         * that code is never displayed, so no player could ever read it off the screen.
         */
        @Override
        public String answer() {
            return String.valueOf(question.answer);
        }

        /**
         * What is actually written in the picture: the two operands, not their sum.
         * The sum is worked out by the solver, so the recogniser is trained on the
         * expression the player reads.
         */
        @Override
        public String text() {
            return question.x + " + " + question.y;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the two operands of the question.
         *
         * <p>The frame is the math screen with the checkbox screen stacked underneath
         * it: two prompt lines, the yellow question "12 + 34 = ?", a red note and an
         * answer box, and below that the second screen. The band is the two operands of
         * the yellow line - the numbers the player has to add up - and it leaves the
         * prompts, the note and the checkbox screen out.
         */
        @Override
        public int[] roi() {
            Graphics2D g = TextBand.measure();
            try {
                g.setFont(Img.font(MC_FONT, Font.PLAIN, MC_SIZE));
                FontMetrics fm = g.getFontMetrics();
                String mcText = McUi.codes("&" + McUi.Mc.YELLOW.code
                        + String.format(MB_MATH_QUESTION, question.x, question.y));
                // the two operands are the first characters of the yellow run
                String operands = question.x + " + " + question.y;
                int left = mcColoredCenterX(g, mcText, SCR_W / 2);
                return TextBand.box(left, 97 + fm.getAscent(), fm.getAscent(), fm.getDescent(),
                        fm.stringWidth(operands));
            } finally {
                g.dispose();
            }
        }

        @Override
        public String prompt() {
            return MB_MATH_LINE1 + " " + MB_MATH_LINE2;
        }

        @Override
        public String source() {
            return MB_SRC;
        }

        /* accessors kept for the probe: the operands the rendered question was built from */
        public int valueX() {
            return question.x;
        }

        public int valueY() {
            return question.y;
        }

        /** The 10 character string the server generated and never shows. */
        public String serverCode() {
            return hiddenCode;
        }

        /** ScreenHandler.openCaptcha() favours the checkbox screen two times out of three. */
        public int mathOdds() {
            return MATH_ODDS;
        }

        public int checkboxOdds() {
            return CHECKBOX_ODDS;
        }

        public boolean mathMode() {
            return mathMode;
        }
    }

    /* ==================================================== minecraft gui widgets */

    /**
     * Minecraft's drop shadow: the colour is desaturated toward the palette floor and
     * quartered, while the alpha byte is passed through untouched.
     */
    private static int shadowOf(int argb) {
        return ((argb & 0xFCFCFC) >> 2) | (argb & 0xFF000000);
    }

    /**
     * Font#drawString - y is the top of the glyph box, AWT wants the baseline, and the
     * shadow is always drawn at +1/+1 underneath the lit glyph.
     */
    private static void mcDraw(Graphics2D g, String s, int x, int topY, int argb) {
        int baseline = topY + g.getFontMetrics().getAscent();
        g.setColor(new Color(shadowOf(argb), true));
        g.drawString(s, x + 1, baseline + 1);
        g.setColor(new Color(argb, true));
        g.drawString(s, x, baseline);
    }

    /** Font#drawCenteredString - the text is shifted left by half of its own advance. */
    private static void mcCenter(Graphics2D g, String s, int cx, int topY, int argb) {
        mcDraw(g, s, cx - mcWidth(g, s) / 2, topY, argb);
    }

    /**
     * A centred line that carries section-sign colour codes, e.g. the yellow question.
     *
     * <p>The line is shifted left by half a space, so that the visible glyphs - and not
     * the colour marker - sit centred.
     */
    private static void mcColoredCenter(Graphics2D g, String mcText, int cx, int topY) {
        int baseline = topY + g.getFontMetrics().getAscent();
        McUi.drawColored(g, mcText, mcColoredCenterX(g, mcText, cx), baseline, MC_SIZE, true);
    }

    /**
     * The x a centred, coloured line is drawn at.
     *
     * <p>Shared with the band of the question, so the two cannot drift apart.
     */
    private static int mcColoredCenterX(Graphics2D g, String mcText, int cx) {
        String visible = McUi.strip(mcText);
        int halfSpace = g.getFontMetrics().charWidth(' ') / 2;
        return cx - mcWidth(g, visible) / 2 - halfSpace;
    }

    private static int mcWidth(Graphics2D g, String s) {
        return g.getFontMetrics().stringWidth(s);
    }

    /** GuiGraphics#fill - Minecraft takes two corners, AWT wants a width and a height. */
    private static void mcFill(Graphics2D g, int x1, int y1, int x2, int y2, int argb) {
        g.setColor(new Color(argb, true));
        g.fillRect(x1, y1, x2 - x1, y2 - y1);
    }

    /**
     * An idle Minecraft button: the vanilla 0xFF6C6C6C to 0xFF383838 vertical gradient
     * (the hover/focus state uses 0xFF5A5A5A / 0xFF2D2D2D) with a one pixel bevel and a
     * centred white label.
     */
    private static void button(Graphics2D g, int x, int y, int w, int h, String label) {
        g.setPaint(new GradientPaint(0, y, new Color(0x6C6C6C), 0, y + h, new Color(0x383838)));
        g.fillRect(x, y, w, h);
        mcFill(g, x, y, x + w, y + 1, 0xFF737373);
        mcFill(g, x, y + h - 1, x + w, y + h, 0xFF2B2B2B);
        mcFill(g, x, y, x + 1, y + h, 0xFF6C6C6C);
        mcFill(g, x + w - 1, y, x + w, y + h, 0xFF2E2E2E);
        int labelTop = y + (h - GLYPH_H) / 2;
        mcDraw(g, label, x + w / 2 - mcWidth(g, label) / 2, labelTop, 0xFFFFFFFF);
    }

    /**
     * An EditBox / NumberEditBox: a one pixel border that turns white while the widget
     * has focus and stays 0xFFA0A0A0 otherwise, wrapped around a black interior. The
     * caret sits six pixels inside the left border, which is where the widget's scroll
     * logic places its text area.
     */
    private static void editBox(Graphics2D g, int x, int y, int w, int h, String text,
                                boolean focused) {
        mcFill(g, x - 1, y - 1, x + w + 1, y + 1, focused ? 0xFFFFFFFF : 0xFFA0A0A0);
        mcFill(g, x - 1, y + h - 1, x + w + 1, y + h + 1, focused ? 0xFFFFFFFF : 0xFFA0A0A0);
        mcFill(g, x - 1, y, x, y + h, focused ? 0xFFFFFFFF : 0xFFA0A0A0);
        mcFill(g, x + w, y, x + w + 1, y + h, focused ? 0xFFFFFFFF : 0xFFA0A0A0);
        mcFill(g, x, y, x + w, y + h, 0xFF000000);
        mcDraw(g, text, x + 6, y + (h - GLYPH_H) / 2, 0xE0E0E0);
    }

    /**
     * A Checkbox. Upstream blits the vanilla sprite; the frame, the fill and the tick
     * are reproduced with fills, and the label is drawn 24px in at the widget's 0xFFE0E0E0.
     */
    private static void checkbox(Graphics2D g, int x, int y, String label, boolean selected) {
        int s = 20;
        mcFill(g, x, y, x + s, y + s, 0xFF3A3A3A);
        mcFill(g, x + 1, y + 1, x + s - 1, y + s - 1, selected ? 0xFFC8C8C8 : 0xFFB0B0B0);
        if (selected) {
            // A tick made of three short strokes, drawn as 2px quads.
            mcFill(g, x + 5, y + 10, x + 7, y + 12, 0xFF101010);
            mcFill(g, x + 7, y + 12, x + 9, y + 14, 0xFF101010);
            mcFill(g, x + 9, y + 8, x + 11, y + 10, 0xFF101010);
            mcFill(g, x + 11, y + 6, x + 13, y + 8, 0xFF101010);
            mcFill(g, x + 13, y + 4, x + 15, y + 6, 0xFF101010);
        }
        mcDraw(g, label, x + s + 4, y + (20 - GLYPH_H) / 2, 0xFFE0E0E0);
    }
}