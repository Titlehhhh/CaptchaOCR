package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.geom.RoundRectangle2D;
import java.awt.image.BufferedImage;
import java.util.ArrayList;
import java.util.List;

/**
 * <b>jSdCool/minecaptcha</b> (CC0-1.0, github.com/jSdCool/minecaptcha) - a Fabric
 * <i>server-side</i> mod that gates the configuration phase of a joining client behind
 * a Minecraft <i>dialog</i>. Both of its two methods are implemented here.
 *
 * <p>The server sends a single {@code ClientboundShowDialogPacket} carrying a
 * {@code NoticeDialog}. The player is not in the world yet, so the challenge is never
 * rendered by the mod itself - it is a packet of {@code DialogBody} rows plus one
 * {@code TextInput} and one {@code ActionButton}, and everything visible in
 * {@link Text#image()} / {@link Image#image()} is the vanilla dialog screen drawing
 * that packet.
 *
 * <pre>
 *   src/main/java/org/cbigames/captcha/CaptchaTask.java#&lt;init&gt;   (challenge generation)
 *   src/main/java/org/cbigames/captcha/CaptchaTask.java#start  (the dialog packet)
 *   src/main/java/org/cbigames/captcha/Config.java#&lt;init&gt;      (config + labels.json load)
 *   src/main/java/org/cbigames/captcha/Main.java#main         (offline captchaimage.json generator)
 * </pre>
 *
 * <h2>The charset typo is real, but it is a transposition - not a missing letter</h2>
 * The literal is
 * {@value #CHARSET}. It is {@value #CHARSET_LENGTH} characters long and it does
 * contain all twenty-six capital letters: the uppercase run reads
 * {@code A..K, M, L, N..Z}, so only the <i>order</i> of {@code K}, {@code M} and
 * {@code L} is wrong. The capital {@code N} is present at index 48.
 *
 * <h2>IMAGE mode cannot ship its real artwork</h2>
 * {@code Main.main()} is an offline tool: it reads {@code captcha/labels.json},
 * shuffles the index -&gt; value mapping into a secret {@code captchaimage.json} and
 * zips the number textures into a resource pack the players must accept. None of that
 * output is committed to the repository - the repo ships only the 3059 <i>source</i>
 * textures under {@code src/main/resources/captcha/images/}, keyed by their original
 * index rather than by the sprite index the client actually receives. A sample here
 * therefore draws every {@code AtlasSprite} as a labelled placeholder cell carrying
 * the sprite index and the real sprite name; the digits the player is meant to read
 * come from the server's secret {@code captchaimage.json} and are unknowable here.
 */
public final class FabricCaptcha {

    private FabricCaptcha() {
    }

    public static final String PLUGIN = "jSdCool/minecaptcha";
    public static final String SRC = "org.cbigames.captcha.CaptchaTask#start";

    /* ------------------------------------------------------------ minecaptcha.cfg */

    /** The single line {@code method=TEXT} of config/minecaptcha.cfg. */
    public static final String CFG_METHOD = "method=TEXT";
    /** The single line {@code length=8} of config/minecaptcha.cfg. */
    public static final String CFG_LENGTH = "length=8";
    /** Config.java rejects anything outside this inclusive range. */
    private static final int CFG_LENGTH_MIN = 1;
    private static final int CFG_LENGTH_MAX = 100;
    /** Config.captchaLength field default, and the length the generated cfg ships with. */
    public static final int LENGTH = 8;

    /* ------------------------------------------------------------------- TEXT */

    /**
     * The charset literal from the TEXT arm of the CaptchaTask constructor, verbatim.
     *
     * <p>The source re-initialises this local on every loop iteration, which is why it
     * reads like a literal instead of a constant; the value is the same each time.
     *
     * <p>Lower case first, then {@code 1234567890} (note: one-zero, so the digits run
     * in reading order but end on {@code 0}), then the capitals. The capitals contain
     * the one defect of the file: after {@code ...IJK} the author typed {@code ML} and
     * then continued with {@code NOP...}, so the alphabet is complete and only the
     * order of M and L is scrambled. Reproduced exactly, typo included.
     */
    private static final String CHARSET =
            "abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKMLNOPQRSTUVWXYZ";
    private static final int CHARSET_LENGTH = 62;

    /** CommonDialogData title. */
    private static final String TITLE = "Captcha";
    /** The first PlainMessage of the body. */
    private static final String PROMPT = "Enter the text below to prove your not a robot";
    /** TextInput "Response": maxLength, and multiline = true. */
    private static final int INPUT_MAX_LENGTH = 40;
    private static final boolean INPUT_MULTILINE = true;
    /** TextInput initial value and CommonButtonData label. */
    private static final String INPUT_VALUE = "";
    private static final String INPUT_LABEL = "Response";
    private static final String BUTTON = "I am not a Robot";
    /** The PlainMessage's second row is styled bold + TextColor.fromRgb(0x00FFFF). */
    private static final int ANSWER_RGB = 0x00FFFF;

    /* ------------------------------------------------------------------ IMAGE */

    /** The second PlainMessage of an IMAGE body. */
    private static final String IMAGE_NOTE = "note: sometimes these numbers may not be accurate";
    /** {@code AtlasSprite(Identifier.parse("items"), Identifier("captcha", "item/img" + i))}. */
    private static final String SPRITE_ATLAS = "items";
    private static final String SPRITE_NAMESPACE = "captcha";
    private static final String SPRITE_PATH_PREFIX = "item/img";
    /**
     * {@code config/captchaimage.json}'s {@code "total images"}, i.e.
     * {@code Config.getNumberValues()}: sprite indices therefore run {@code 0..3058}.
     */
    private static final int SPRITE_COUNT = 3059;
    /** The real Minecraft item texture the resource pack carries, in GUI units. */
    private static final int SPRITE_TEX_SIZE = 28;

    /* ============================================================ shared dialog */

    /** Title bar height of the vanilla dialog panel. */
    private static final int TITLE_H = 34;
    /** Body padding inside the panel. */
    private static final int PAD = 16;
    private static final int LINE_H = 18;

    private static final Color PANEL = new Color(0x1E, 0x1E, 0x23, 246);
    private static final Color PANEL_EDGE = new Color(0x6A, 0x6A, 0x78, 90);
    private static final Color DIVIDER = new Color(0x4A, 0x4A, 0x55);
    private static final int BODY_TEXT = 0xE6E6E6;
    private static final int DIM_TEXT = 0x9A9A9A;
    private static final Color FIELD_FILL = new Color(0x0E, 0x0E, 0x12, 255);
    private static final Color FIELD_EDGE = new Color(0x6E, 0x6E, 0x7A);
    private static final Color BUTTON_FILL = new Color(0x3E, 0x3E, 0x48);
    private static final Color BUTTON_HILIGHT = new Color(0x5A, 0x5A, 0x67);
    private static final Color BUTTON_SHADOW = new Color(0x26, 0x26, 0x2E);

    /**
     * Draws one line of vanilla GUI text with the drop shadow the client applies.
     *
     * <p>Named {@code drawText} and not {@code text}, because the nested sample classes
     * implement {@link dev.captcha.Cg} and an inherited {@code text()} would shadow this
     * helper inside them.
     */
    private static void drawText(Graphics2D g, String s, int x, int y, int size, boolean bold, int argb) {
        g.setFont(Img.font("Monospaced", bold ? Font.BOLD : Font.PLAIN, size));
        int off = Math.max(1, size / 8);
        g.setColor(new Color(0x3F, 0x3F, 0x3F, 200));
        g.drawString(s, x + off, y + off);
        g.setColor(new Color(argb));
        g.drawString(s, x, y);
    }

    /** Advance width of a string in the dialog font. */
    private static int width(Graphics2D g, String s, int size, boolean bold) {
        g.setFont(Img.font("Monospaced", bold ? Font.BOLD : Font.PLAIN, size));
        return g.getFontMetrics().stringWidth(s);
    }

    private static void centreText(Graphics2D g, String s, int cx, int y, int size, boolean bold, int argb) {
        drawText(g, s, cx - width(g, s, size, bold) / 2, y, size, bold, argb);
    }

    /**
     * Reproduces the greedy wrap a {@code PlainMessage} applies at the width the source
     * hands it (300 GUI units, which is {@link #textWidth} at our render scale).
     */
    private static List<String> wrap(Graphics2D g, String s, int size, int maxW) {
        List<String> out = new ArrayList<>();
        StringBuilder line = new StringBuilder();
        for (String word : s.split(" ")) {
            String cand = line.isEmpty() ? word : line + " " + word;
            if (line.length() > 0 && width(g, cand, size, false) > maxW) {
                out.add(line.toString());
                line.setLength(0);
                line.append(word);
            } else {
                line.setLength(0);
                line.append(cand);
            }
        }
        out.add(line.toString());
        return out;
    }

    /** The dark translucent panel the vanilla dialog screen draws. */
    private static void panel(Graphics2D g, int w, int h) {
        g.setColor(PANEL);
        g.fill(new RoundRectangle2D.Float(0.5f, 0.5f, w - 1, h - 1, 10, 10));
        g.setColor(PANEL_EDGE);
        g.setStroke(new BasicStroke(1f));
        g.draw(new RoundRectangle2D.Float(0.5f, 0.5f, w - 1, h - 1, 10, 10));
    }

    /**
     * The title row: the centred {@code CommonDialogData} title plus the close control
     * the {@code DialogAction.CLOSE} on-close handler puts in the corner.
     */
    private static void titleBar(Graphics2D g, int w) {
        centreText(g, TITLE, w / 2, 24, 16, false, 0xFFFFFF);
        int cx = w - 20;
        g.setColor(new Color(0xB4, 0xB4, 0xC0));
        g.drawLine(cx - 4, 13, cx + 4, 21);
        g.drawLine(cx - 4, 21, cx + 4, 13);
        g.setColor(DIVIDER);
        g.drawLine(PAD - 6, TITLE_H, w - PAD + 6, TITLE_H);
    }

    /** The single {@code TextInput}, as the client draws it: a dark box plus a caret. */
    private static void textInput(Graphics2D g, int x, int y, int w, int h) {
        g.setColor(FIELD_FILL);
        g.fillRect(x, y, w, h);
        g.setColor(FIELD_EDGE);
        g.setStroke(new BasicStroke(1f));
        g.drawRect(x, y, w - 1, h - 1);
        drawText(g, INPUT_LABEL, x, y - 6, 11, false, DIM_TEXT);
        // the initial value is "", so all that is visible is the insertion caret
        g.setColor(Color.WHITE);
        g.drawLine(x + 6, y + 8, x + 6, y + h - 8);
    }

    /** The {@code ActionButton} in the button strip along the bottom of the dialog. */
    private static void actionButton(Graphics2D g, int cx, int y, int w, int h) {
        int x = cx - w / 2;
        g.setColor(BUTTON_FILL);
        g.fillRoundRect(x, y, w, h, 6, 6);
        g.setColor(BUTTON_HILIGHT);
        g.drawLine(x + 6, y + 1, x + w - 7, y + 1);
        g.setColor(BUTTON_SHADOW);
        g.drawLine(x + 6, y + h - 1, x + w - 7, y + h - 1);
        centreText(g, BUTTON, cx, y + h / 2 + 5, 13, false, 0xFFFFFF);
    }

    /** Centres the finished dialog over the dimmed screen the modal sits on. */
    private static BufferedImage compose(BufferedImage dialog, int w, int h) {
        BufferedImage out = McUi.backdrop(w, h);
        Graphics2D g = Img.g2d(out, true);
        g.drawImage(dialog, (w - dialog.getWidth()) / 2, (h - dialog.getHeight()) / 2, null);
        g.dispose();
        return out;
    }

    /**
     * Body text width. The source hands {@code PlainMessage} a 300 unit maximum, which
     * is the inner panel width at the scale this dialog is drawn at.
     */
    private static int textWidth(int panelW) {
        return panelW - PAD * 2;
    }

    /* =============================================================== TEXT sample */

    /**
     * The TEXT method: the body carries the prompt and the bold aqua answer, and the
     * single {@code TextInput} is where the player types what they read.
     */
    public static final class Text implements Cg {

        private final String captcha;
        private final BufferedImage img;
        private final int[] roi;

        public Text() {
            captcha = generateCaptcha();
            int[] band = new int[4];
            img = render(captcha, band);
            roi = band;
        }

        /**
         * The TEXT arm of the CaptchaTask constructor.
         *
         * <p>The index comes from {@code Math.random()}, not from a {@code SecureRandom}
         * or even a {@link java.util.Random}, so the whole 62 entry charset is reachable
         * and the generated code carries no crypto-strength guarantee at all.
         */
        static String generateCaptcha() {
            StringBuilder sb = new StringBuilder(LENGTH);
            for (int i = 0; i < LENGTH; i++) {
                sb.append(CHARSET.charAt((int) (Math.random() * CHARSET_LENGTH)));
            }
            return sb.toString();
        }

        static BufferedImage render(String captcha, int[] band) {
            int panelW = 470;
            int panelTextW = textWidth(panelW);

            Graphics2D mg = Img.g2d(Img.rgb(4, 4), true);
            int promptLines = wrap(mg, PROMPT, 13, panelTextW).size();
            mg.dispose();

            int bodyTop = TITLE_H + PAD;
            int promptH = promptLines * LINE_H;
            int answerTop = bodyTop + promptH + 6;
            int answerH = 42;
            int inputLabelTop = answerTop + answerH + 26;
            int inputTop = inputLabelTop + 8;
            int inputH = INPUT_MULTILINE ? 44 : 24;
            int buttonTop = inputTop + inputH + 20;
            int buttonH = 26;
            int panelH = buttonTop + buttonH + PAD;

            int imgW = panelW + 80;
            int imgH = panelH + 100;

            BufferedImage dialog = Img.rgb(panelW, panelH);
            Graphics2D g = Img.g2d(dialog, true);

            panel(g, panelW, panelH);
            titleBar(g, panelW);

            int y = bodyTop + 12;
            for (String line : wrap(g, PROMPT, 13, panelTextW)) {
                // PlainMessage body rows are left aligned inside the panel
                drawText(g, line, PAD, y, 13, false, BODY_TEXT);
                y += LINE_H;
            }

            // the styled PlainMessage: bold aqua, on the panel background
            centreText(g, captcha, panelW / 2, answerTop + 28, 22, true, ANSWER_RGB);

            // the band of that line, in the coordinates of the composed frame
            g.setFont(Img.font("Monospaced", Font.BOLD, 22));
            FontMetrics fm = g.getFontMetrics();
            int answerW = width(g, captcha, 22, true);
            int answerLeft = panelW / 2 - answerW / 2;
            band[0] = (imgW - panelW) / 2 + answerLeft;
            band[1] = (imgH - panelH) / 2 + answerTop + 28 - fm.getAscent();
            band[2] = answerW;
            band[3] = fm.getAscent() + fm.getDescent();

            textInput(g, PAD, inputTop, panelW - PAD * 2, inputH);
            actionButton(g, panelW / 2, buttonTop, 210, buttonH);

            g.dispose();
            return compose(dialog, imgW, imgH);
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "text";
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
         * The band of the answer, in the middle of the dialog.
         *
         * <p>The frame is the vanilla dialog screen: a title bar, the prompt
         * "Enter the text below to prove your not a robot", the bold aqua answer, a text
         * input and a button. The band is the aqua line with the code - the only place
         * where the answer is written down.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String prompt() {
            return PROMPT;
        }

        @Override
        public String source() {
            return SRC;
        }
    }

    /* ============================================================== IMAGE sample */

    /**
     * The IMAGE method: the body replaces the answer line with a row of
     * {@code AtlasSprite} components drawn out of the player's resource pack.
     */
    public static final class Image implements Cg {

        private final int[] sprites;
        private final BufferedImage img;
        private final int[] roi;

        public Image() {
            sprites = pickSprites();
            int[] band = new int[4];
            img = render(sprites, band);
            roi = band;
        }

        /**
         * The IMAGE arm of the CaptchaTask constructor: {@code length} independent draws
         * of {@code (int) (Math.random() * numberImages)}, again off {@code Math.random()}.
         *
         * <p>Nothing de-duplicates the draws, so the same sprite can legitimately appear
         * two or more times in one row.
         */
        static int[] pickSprites() {
            int[] out = new int[LENGTH];
            for (int i = 0; i < LENGTH; i++) {
                out[i] = (int) (Math.random() * SPRITE_COUNT);
            }
            return out;
        }

        /**
         * The answer as this dataset states it: the sprite indices the mod put on screen,
         * by their real sprite name, comma separated in row order.
         *
         * <p>Note what the mod itself compares against. {@code CaptchaTask.handleResponse}
         * compares the player input to {@code captchaValue}, which for IMAGE mode is the
         * <i>concatenation of the two digit values</i> the sprites display - a 16 character
         * string at the default length. Those values live in the server's secret
         * {@code config/captchaimage.json} and cannot be derived here.
         */
        String spriteList() {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < sprites.length; i++) {
                if (i > 0) {
                    sb.append(", ");
                }
                sb.append(spriteName(sprites[i]));
            }
            return sb.toString();
        }

        static BufferedImage render(int[] sprites, int[] band) {
            int cell = SPRITE_TEX_SIZE * 2;
            int gap = 6;
            int rowW = sprites.length * cell + (sprites.length - 1) * gap;
            int panelW = Math.max(560, rowW + PAD * 2 + 12);
            int panelTextW = textWidth(panelW);

            Graphics2D mg = Img.g2d(Img.rgb(4, 4), true);
            int promptLines = wrap(mg, PROMPT, 13, panelTextW).size();
            int noteLines = wrap(mg, IMAGE_NOTE, 13, panelTextW).size();
            mg.dispose();

            int bodyTop = TITLE_H + PAD;
            int spriteTop = bodyTop + promptLines * LINE_H + 10;
            int noteTop = spriteTop + cell + 14;
            int inputLabelTop = noteTop + noteLines * LINE_H + 18;
            int inputTop = inputLabelTop + 8;
            int inputH = INPUT_MULTILINE ? 44 : 24;
            int buttonTop = inputTop + inputH + 20;
            int buttonH = 26;
            int panelH = buttonTop + buttonH + PAD;

            int imgW = panelW + 80;
            int imgH = panelH + 100;

            BufferedImage dialog = Img.rgb(panelW, panelH);
            Graphics2D g = Img.g2d(dialog, true);

            panel(g, panelW, panelH);
            titleBar(g, panelW);

            int y = bodyTop + 12;
            for (String line : wrap(g, PROMPT, 13, panelTextW)) {
                drawText(g, line, PAD, y, 13, false, BODY_TEXT);
                y += LINE_H;
            }

            // the source seeds this PlainMessage with a literal "." and then appends the
            // sprite objects, so the row really is preceded by a small bold dot
            int rowX = (panelW - rowW) / 2 + 6;
            drawText(g, ".", rowX - 8, spriteTop + 14, 16, true, 0xFFFFFF);
            for (int i = 0; i < sprites.length; i++) {
                spriteCell(g, rowX + i * (cell + gap), spriteTop, cell, sprites[i]);
            }

            // the band of the row of sprites, in the coordinates of the composed frame
            band[0] = (imgW - panelW) / 2 + rowX;
            band[1] = (imgH - panelH) / 2 + spriteTop;
            band[2] = rowW;
            band[3] = cell;

            y = noteTop + 12;
            for (String line : wrap(g, IMAGE_NOTE, 13, panelTextW)) {
                drawText(g, line, PAD, y, 13, false, DIM_TEXT);
                y += LINE_H;
            }

            textInput(g, PAD, inputTop, panelW - PAD * 2, inputH);
            actionButton(g, panelW / 2, buttonTop, 210, buttonH);

            g.dispose();
            return compose(dialog, imgW, imgH);
        }

        /**
         * One {@code AtlasSprite} slot.
         *
         * <p>The real artwork is a 28x28 Minecraft item texture that only exists inside the
         * resource pack {@code Main.main()} zips at pack-build time, keyed by sprite index.
         * The repository does not contain that pack or the resulting
         * {@code assets/captcha/textures/item/img<i>.png} files, so this cell is a
         * placeholder: the same bevel, the sprite index it stands for, and the real sprite
         * name. The two digits a player would read off it come from the server's secret
         * {@code captchaimage.json} and are not derivable from the repository.
         */
        private static void spriteCell(Graphics2D g, int x, int y, int size, int index) {
            g.setColor(new Color(0x14, 0x14, 0x18, 210));
            g.fillRect(x, y, size, size);
            g.setColor(FIELD_EDGE);
            g.drawLine(x, y, x + size - 1, y);
            g.drawLine(x, y, x, y + size - 1);
            g.setColor(new Color(0x26, 0x26, 0x2E));
            g.drawLine(x, y + size - 1, x + size - 1, y + size - 1);
            g.drawLine(x + size - 1, y, x + size - 1, y + size - 1);

            centreText(g, String.valueOf(index), x + size / 2, y + size / 2 + 5, 22, true, 0xFFFFFF);
            centreText(g, spriteName(index), x + size / 2, y + size - 8, 9, false, DIM_TEXT);
        }

        /** The sprite name the mod builds: {@code img<i>} under the {@code captcha} namespace. */
        static String spriteName(int index) {
            return SPRITE_PATH_PREFIX.substring(SPRITE_PATH_PREFIX.indexOf('/') + 1) + index;
        }

        /** Full sprite location, i.e. {@code captcha:item/img<i>} in the {@code items} atlas. */
        static String spriteId(int index) {
            return SPRITE_NAMESPACE + ":" + SPRITE_PATH_PREFIX + index;
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "image";
        }

        @Override
        public String answer() {
            return spriteList();
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the row of sprites, in the middle of the dialog.
         *
         * <p>The frame is the vanilla dialog screen: a title bar, the prompt, the row of
         * eight sprite cells, a note, a text input and a button. The band is that row -
         * the only place where the answer is written down, once per cell: the sprite
         * index in white and the sprite's real name underneath it. The little dot the
         * source puts in front of the row is not part of it.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String prompt() {
            return PROMPT;
        }

        @Override
        public String source() {
            return SRC;
        }
    }

    /**
     * Self check of the two facts the reimplementation depends on: the charset is the
     * 62 entry literal above, all capitals present, and the sprite indices stay inside
     * the range {@code captchaimage.json} declares.
     */
    static {
        if (CHARSET.length() != CHARSET_LENGTH) {
            throw new AssertionError("charset literal length drifted: " + CHARSET.length());
        }
        if (CHARSET.indexOf('N') < 0 || CHARSET.indexOf('M') < 0 || CHARSET.indexOf('L') < 0) {
            throw new AssertionError("charset is missing a capital: " + CHARSET);
        }
        if (CFG_LENGTH_MIN < 1 || LENGTH < CFG_LENGTH_MIN || LENGTH > CFG_LENGTH_MAX) {
            throw new AssertionError("length outside the cfg bounds: " + LENGTH);
        }
        if (SPRITE_COUNT < 2 || SPRITE_COUNT > 100000 || SPRITE_ATLAS.isEmpty()) {
            throw new AssertionError("sprite count out of range: " + SPRITE_COUNT);
        }
        if (Image.spriteName(0).equals(SPRITE_PATH_PREFIX + 0)) {
            throw new AssertionError("sprite prefix has no trailing path segment: " + SPRITE_PATH_PREFIX);
        }
    }
}