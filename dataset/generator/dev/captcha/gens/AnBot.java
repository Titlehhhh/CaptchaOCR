package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;

import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.font.TextAttribute;
import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;
import java.text.AttributedCharacterIterator;
import java.text.AttributedString;
import java.util.Random;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * <b>irootdev/AnBot</b> (GPL-3.0) - "AnBotCore" v0.1, a BungeeCord anti-bot plugin that
 * parks a joining player on an embedded fake vanilla server listening on 127.0.0.1:1512,
 * asks for a captcha in chat and hands out a filled map item.
 *
 * <p>The picture is produced by JCaptcha (com.octo.captcha) with every parameter
 * hard-coded, wrapped in {@code Main#getCaptcha}:
 *
 * <pre>
 *   new RandomFontGenerator(20, 40, new Font[]{ new Font("Arial", Font.BOLD, 12) })
 *   new RandomListColorGenerator(new Color[]{ RED, GREEN, BLUE, BLACK })
 *   new UniColorBackgroundGenerator(128, 128, Color.WHITE)
 *   new SimpleTextPaster(captcha_length, captcha_length, colorGen)
 *   new ComposedWordToImage(fontGen, bgGen, textPaster).getImage(code)
 * </pre>
 *
 * <p>{@code SimpleTextPaster} is the one non-distorting paster in the library: no ripple,
 * no wave, no rotation, no shear, and - this is what makes the challenge so weak - no
 * random placement either. The text band is pinned to {@code width/20, height/2}, the
 * glyphs are advanced one logical box at a time with a single 1px gap, and the whole word
 * is painted in a <i>single</i> colour because {@code manageColorPerGlyph} stays false.
 * The only thing that varies between two challenges is the family-wide font style/size
 * (4 styles x 20 sizes) and that one colour. Everything else is fixed geometry.
 *
 * <p>Verified against the library itself (the repository ships the compiled
 * {@code com/octo/captcha} classes) rather than against its documentation, which is where
 * the two corrections in {@link #FONT_MIN} and {@link #STYLES} come from.
 *
 * <pre>
 *   src/iroot/Main.java#getCaptcha        - the JCaptcha composition
 *   src/iroot/Main.java#random            - the strong_captcha=false digit branch
 *   src/iroot/Main.java#rc                - the strong_captcha=true alphabet branch
 *   src/iroot/BungeePlugin.java#onEnable  - the config.yml defaults
 *   src/iroot/BungeePlugin.java#onPlayerChat - the substring verification
 * </pre>
 *
 * <p>Both {@code strong_captcha} modes are represented: the plugin's own default is
 * {@code false}, and the {@link Captcha} samples alternate between the two branches so a
 * generated dataset covers digits-only and alphanumeric codes alike.
 *
 * <p>What the client really receives is a little more degraded than this image: the plugin
 * hand-serialises it into a map payload by keeping rows 25..127 and then appending 25
 * blank rows, while mapping every non-white pixel onto a single map colour. {@link #image}
 * is the render itself, i.e. what JCaptcha produced.
 */
public final class AnBot {

    private AnBot() {
    }

    public static final String PLUGIN = "irootdev/AnBot";
    public static final String SRC = "iroot.Main#getCaptcha";

    /* --------------------------------------------------------------- constants */

    /** UniColorBackgroundGenerator(128, 128, Color.WHITE) - a flat, opaque white field. */
    private static final int SIZE = 128;

    private static final Color BACKGROUND = Color.WHITE;

    /** The RandomListColorGenerator array, in source order: opaque red, green, blue, black. */
    private static final Color[] INKS = {Color.RED, Color.GREEN, Color.BLUE, Color.BLACK};

    /** The base font the plugin builds once and hands to the font generator. */
    private static final Font BASE_FONT = new Font("Arial", Font.BOLD, 12);

    /** config.yml font_min. */
    private static final int FONT_MIN = 20;

    /** config.yml font_max. Note this is exclusive in practice, see {@link #font}. */
    private static final int FONT_MAX = 40;

    /**
     * The font generator mixes styles by default and derives the whole 3000-entry font pool
     * from {@link #BASE_FAMILY}, so the glyphs are not reliably bold - they are one of the
     * four AWT styles, uniformly.
     */
    private static final int[] STYLES = {Font.PLAIN, Font.ITALIC, Font.BOLD, Font.BOLD | Font.ITALIC};

    /** config.yml captcha_length; also the paster's word length, so both are 3. */
    private static final int LENGTH = 3;

    /** The alphabet literal from rc(), for strong_captcha = true. */
    private static final String ALPHABET = "qwertyuiopasdfghjklzxcvbnm0123456789";

    /** The paster's text band: {@code image.getWidth() / 20}, i.e. 6px in from the left. */
    private static final double BAND_X = SIZE / 20;

    /** ... and {@code image.getHeight() / 2}, which is the baseline every glyph is drawn on. */
    private static final float BAND_BASELINE = SIZE / 2f;

    /** useMinimumSpacing(1.0) - the gap inserted between two adjacent glyph boxes. */
    private static final double GAP = 1.0d;

    /**
     * The chat line the joining player is asked to answer. Upstream sends it as the
     * {@code TextMessage} {@code §8§l[§f§lAn§b§lBot§8§l]: §6§l} + this sentence, i.e. a
     * dark-grey bold prefix, a bold gold request; {@link #prompt()} drops the formatting.
     *
     * <p>The plugin asks for "digits" even in strong mode, where the code may well contain
     * letters; that mismatch is upstream's, kept as-is.
     */
    private static final String PROMPT = "Пожалуйста, введите цифры которые вы видите в чат!";

    /**
     * Stands in for {@code BungeePlugin.strong_captcha}, which is fixed for the lifetime of
     * a server. A single dataset run would therefore only ever contain one of the two
     * branches, so the flag alternates instead, guaranteeing both are represented.
     */
    private static final AtomicInteger STRONG_TOGGLE = new AtomicInteger();

    /* ================================================================ CAPTCHA */

    /**
     * One 128x128 map captcha, in one of the plugin's two code-generation modes.
     *
     * <p>{@code strong_captcha = false} (the shipped default) yields {@link #LENGTH} digits
     * drawn via {@code (int)(Math.random() * 10)}; {@code strong_captcha = true} yields
     * {@link #LENGTH} characters drawn uniformly from {@link #ALPHABET}, each from its own
     * freshly seeded {@link Random}, exactly as {@code rc()} does.
     */
    public static final class Captcha implements Cg {

        private final String captcha;
        private final BufferedImage img;

        public Captcha() {
            Random random = new Random();
            boolean strong = STRONG_TOGGLE.getAndIncrement() % 2 == 1;
            captcha = strong ? strongCode() : digits();
            img = render(captcha, font(random), INKS[random.nextInt(INKS.length)]);
        }

        /**
         * The {@code strong_captcha = false} branch: {@code code + random(0, 9)}, where
         * {@code random(min,max)} is {@code min + (int)(Math.random() * ((max-min)+1))}.
         * The plugin deliberately calls {@code Math.random()} rather than a seeded Random.
         */
        private static String digits() {
            StringBuilder sb = new StringBuilder(LENGTH);
            for (int i = 0; i < LENGTH; i++) {
                sb.append((char) ('0' + (int) (Math.random() * 10)));
            }
            return sb.toString();
        }

        /**
         * The {@code strong_captcha = true} branch: {@link #ALPHABET}{@code .charAt(r.nextInt(...))}
         * - and the plugin builds a new {@link Random} for every single character.
         */
        private static String strongCode() {
            StringBuilder sb = new StringBuilder(LENGTH);
            for (int i = 0; i < LENGTH; i++) {
                sb.append(ALPHABET.charAt(new Random().nextInt(ALPHABET.length())));
            }
            return sb.toString();
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "captcha";
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
         * No band: the frame is nothing but the code.
         *
         * <p>The JCaptcha surface is a flat white field with the three glyphs of the code
         * on it and nothing else - no title, no counter, no instruction - and the face
         * and the size of the glyphs are drawn at random, so there is no single tight
         * box around them.
         */
        @Override
        public int[] roi() {
            return null;
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

    /* ============================================================ composition */

    /**
     * One RandomFontGenerator pick. The pool it serves is 3000 independently derived fonts,
     * each {@code base.deriveFont(style, minFontSize + abs(random.nextInt(max - min)))} over
     * the one supplied family, and {@code getFont()} picks one of them uniformly.
     *
     * <p>Two consequences that are easy to get wrong: because the size offset is
     * {@code nextInt(max - min)} and not {@code nextInt(max - min + 1)}, the reachable
     * sizes are 20..39 and a 40px glyph is never produced; and because the plugin uses the
     * three-argument constructor, style mixing stays on and the derived style is one of
     * {@link #STYLES} rather than always BOLD.
     */
    private static Font font(Random random) {
        int size = FONT_MIN + Math.abs(random.nextInt(FONT_MAX - FONT_MIN));
        int style = STYLES[random.nextInt(STYLES.length)];
        return BASE_FONT.deriveFont(style, (float) size);
    }

    /**
     * The 128x128 render: a white field, one colour, one font, glyphs stepped one logical
     * box apart with a 1px gap and drawn on a single fixed baseline.
     *
     * <p>Package-private and parameterised so the layout can be compared against the
     * library's own output with the font and colour pinned.
     */
    static BufferedImage render(String code, Font font, Color ink) {
        BufferedImage background = Img.rgb(SIZE, SIZE);
        Graphics2D bg = (Graphics2D) background.getGraphics();
        bg.setColor(BACKGROUND);
        bg.fillRect(0, 0, SIZE, SIZE);
        bg.dispose();

        AttributedString attributed = new AttributedString(code);
        for (int i = 0; i < code.length(); i++) {
            attributed.addAttribute(TextAttribute.FONT, font, i, i + 1);
        }

        BufferedImage img = Img.rgb(SIZE, SIZE);
        // A plain getGraphics(), as the paster uses: nothing is hinted, so the glyphs come
        // out aliased and hinted. Saying so explicitly keeps it true on any JDK.
        Graphics2D g = (Graphics2D) img.getGraphics();
        hardEdges(g);
        g.drawImage(background, 0, 0, SIZE, SIZE, null);
        // One colour for the whole word: manageColorPerGlyph is never switched on, so the
        // generator is consulted exactly once, here.
        g.setColor(ink);

        AttributedCharacterIterator all = attributed.getIterator();
        int n = all.getEndIndex();
        Rectangle2D[] box = new Rectangle2D[n];
        AttributedString[] glyphs = new AttributedString[n];
        for (int i = 0; i < n; i++) {
            all.setIndex(i);
            g.setFont(font);
            box[i] = font.getStringBounds(all, i, i + 1, g.getFontRenderContext());
            glyphs[i] = new AttributedString(all, i, i + 1);
        }

        double[] x = new double[n];
        for (int i = 0; i < n; i++) {
            x[i] = box[i].getX();
        }
        // First layout pass: a running pen that leaves GAP between consecutive glyph boxes.
        for (int i = 1; i < n; i++) {
            x[i] = x[i - 1] + box[i - 1].getWidth() + GAP;
        }
        // Second layout pass: the run is moved into the text band. The move is applied as
        // an absolute offset to the first glyph and an addition to the rest, which drops
        // the first glyph's own side bearing - reproduced because it is visible.
        x[0] = BAND_X;
        for (int i = 1; i < n; i++) {
            x[i] += BAND_X;
        }

        for (int i = 0; i < n; i++) {
            g.drawString(glyphs[i].getIterator(), (float) x[i], BAND_BASELINE);
        }
        g.dispose();
        return img;
    }

    /** The un-hinted defaults a {@code BufferedImage} hands out. */
    private static void hardEdges(Graphics2D g) {
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_OFF);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING,
                RenderingHints.VALUE_TEXT_ANTIALIAS_OFF);
        g.setRenderingHint(RenderingHints.KEY_FRACTIONALMETRICS,
                RenderingHints.VALUE_FRACTIONALMETRICS_OFF);
    }
}