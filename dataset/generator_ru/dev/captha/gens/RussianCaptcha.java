package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;

import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.font.FontRenderContext;
import java.awt.font.GlyphVector;
import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;
import java.util.Random;

/**
 * The Russian-language number-word and symbol families of the gallery catalogue,
 * rendered the way the gallery presents them: as a <b>gallery composite</b> of a
 * LimboFilter map.
 *
 * <h2>What a catalogue sample really is</h2>
 * The 250x150 PNGs of the gallery's number-word and symbol sections are <b>not</b>
 * renderer output. They are the gallery operator's presentation of a
 * captcha: the plugin's 128x128 Minecraft map, scaled up to 250x150, with the plugin's
 * chat/title string drawn on top of it. The two halves have very different origins:
 * <ul>
 *   <li>the <b>map</b> is the real output of <b>Elytrium/LimboFilter</b> (AGPL-3.0), a
 *       Velocity anti-bot plugin - the number spelled out in Russian words, one word per
 *       row, clipped at the right edge, in gradient colours, with thin black curves over
 *       it. That part is rendered by {@link LimboFilter}, a clean-room reimplementation
 *       of the upstream renderer, and it is the same renderer that produces the
 *       {@code LimboFilter/map}, {@code LimboFilter/symbols},
 *       {@code LimboFilter/framed3x3} and {@code LimboFilter/framed2x2} types;</li>
 *   <li>the <b>caption</b> is <b>not</b> drawn by the renderer at all. Upstream
 *       {@code drawText()} only ever draws the answer; the caption is the plugin's
 *       {@code CHECKING_CAPTCHA_CHAT} / {@code CHECKING_CAPTCHA_TITLE} string, and the
 *       gallery operator composited it onto the picture so that the catalogue sample
 *       shows the whole challenge. It is therefore part of the <b>gallery's</b>
 *       presentation, not part of the plugin's output.</li>
 * </ul>
 *
 * <h2>Provenance</h2>
 * The upstream renderer is {@code net.elytrium.limbofilter.captcha.painter.CaptchaPainter}
 * of <a href="https://github.com/Elytrium/LimboFilter">Elytrium/LimboFilter</a>; the
 * identification and the measurements are written up in
 * {@code reports/LIMBOFILTER_IDENTIFICATION.md}. The plugin is AGPL-3.0, so nothing of it
 * is carried over - {@link LimboFilter} is a clean-room reimplementation.
 *
 * <p>What is <b>not</b> reproduced here, and why:
 * <ul>
 *   <li><b>The backplates.</b> Upstream paints the captcha onto an image the server owner
 *       supplies ({@code BACKPLATE_PATHS}); the captured servers' backplates (the Shrek,
 *       the beach, the moire textures) are not recoverable, so the map carries the
 *       procedural backdrop of {@link LimboFilter} instead.</li>
 *   <li><b>The type size.</b> The captured servers ran the plugin with a much smaller
 *       type and a much tighter advance than the upstream defaults - their number
 *       samples carry about eleven characters per line and three lines. The type
 *       configuration of {@link LimboFilter} is that one (it was measured off the
 *       reference samples), so the words fit the map here as they do there: three
 *       lines, the last word clipped at the right edge. Their symbol samples are a
 *       different server with the upstream's default type, and that is what the symbol
 *       family uses. The face itself is not the same - the captured servers used their
 *       own TTF, which was not recovered, so the three standard AWT faces are used
 *       instead of the marker face of the samples.</li>
 *   <li><b>The caption's face.</b> The gallery operator's exact font is not recoverable;
 *       a heavy condensed face is squeezed to the width of the canvas, which is what the
 *       reference samples show - the long caption is squeezed the hardest, the short one
 *       is stretched instead.</li>
 *   <li><b>The watermarks.</b> Some of the gallery's samples carry the operator's own
 *       credit line. Those are the gallery's business and are not reproduced here.</li>
 *   <li><b>The red title.</b> The catalogue also has samples with the red
 *       {@code НАПИШИ ЦИФРАМИ} at the <b>top</b> - that is the plugin's
 *       {@code CHECKING_CAPTCHA_TITLE} rather than its chat line, and it is not one of
 *       the three captions reproduced here.</li>
 * </ul>
 *
 * <p>The other two families of the catalogue that have no plugin behind them stay in
 * {@code WebCaptcha.java} ({@code ru-web}) and {@code ObjectCaptcha.java}
 * ({@code ru-object-swatch}); both are labelled {@code Reconstructed}.
 *
 * <h2>The answer and the text</h2>
 * The answer is the number in digits and the text is the number in Russian words, exactly
 * as the underlying {@link LimboFilter.Map} reports them - the map shows the words, the
 * player has to type the digits. The {@code ru-symbols} type carries the symbol string
 * as both answer and text, because there the answer is what is drawn.
 *
 * <h2>Legibility</h2>
 * The map is rendered with the type configuration of the <b>captured servers</b> (see
 * the javadoc of {@link LimboFilter}), which is the one the reference samples of the
 * catalogue show: three lines of about eleven characters, the letters about ten map
 * pixels wide and fifteen high, an advance of twelve map pixels and a line advance of
 * twenty-three. Measured over 400 generated maps:
 *
 * <ul>
 *   <li>100 % of the words have visible ink, and 94.7 % of them are shown completely;</li>
 *   <li>100 % of the samples show <b>every</b> word of their number, and all of their
 *       lines fit on the map;</li>
 *   <li>a word shows on average 99.5 % of its layout cell - the rest is the clipping
 *       at the right edge, which is the signature of the plugin.</li>
 * </ul>
 *
 * <p>The number can therefore be read off the picture, and the text band of a number
 * sample is a real band: it is the tight rectangle around the words, scaled into the
 * composite and cut off above the caption - the caption is a <b>different</b> string
 * and must never be part of the band a recogniser is handed.
 */
public final class RussianCaptcha {

    private RussianCaptcha() {
    }

    /**
     * The gallery that presents the catalogue.
     *
     * <p>It is <b>not</b> the plugin: the plugin behind these pictures is LimboFilter,
     * and the real renderer output lives in {@code dataset/out_ru/LimboFilter/}. The
     * {@code GalleryCaptcha} folder is the gallery's own presentation of it, next to the two
     * families that have no plugin behind them at all.
     */
    public static final String PLUGIN = "GalleryCaptcha";

    /**
     * The source of the number family: the gallery composite of a LimboFilter map.
     *
     * <p>There is no upstream plugin behind the gallery presentation itself: it was
     * reconstructed from reference screenshots, and no assets of the original are
     * redistributed here.
     */
    public static final String SRC_NUMBER =
            "GalleryCaptcha/ru-numberword: clean-room reconstruction of a gallery-style captcha family, "
                    + "measured from reference screenshots; no vendor assets redistributed; "
                    + "renderer: " + LimboFilter.SRC + "; " + LimboFilter.SRC_ANSWER + "; "
                    + LimboFilter.SRC_SPELLING;

    /**
     * The source of the symbol family: the gallery composite of a LimboFilter map.
     *
     * <p>As with the number family: reconstructed from reference screenshots, no vendor
     * assets redistributed.
     */
    public static final String SRC_SYMBOLS =
            "GalleryCaptcha/ru-symbols: clean-room reconstruction of a gallery-style captcha family, "
                    + "measured from reference screenshots; no vendor assets redistributed; "
                    + "renderer: " + LimboFilter.SRC + "; " + LimboFilter.SRC_ANSWER;

    /** The canvas every sample in this family is presented at. */
    static final int W = 250;
    static final int H = 150;

    /* -------------------------------------------------------------- captions */

    /**
     * The caption of the number captcha, orange.
     *
     * <p>Measured from a reference sample of the gallery's number section: the fill
     * is exactly {@code (216, 127, 51)} and the caption sits in the rows 135..144.
     */
    public static final String CAPTION_DIGITS = "ВВЕДИТЕ ТОЛЬКО ЦИФРЫ";

    /**
     * The second caption of the number captcha, black.
     *
     * <p>Seen in {@code s02…/011.png} and {@code s02…/012.png}, where it is squeezed
     * over the whole width of the canvas.
     */
    public static final String CAPTION_DIGITS_CHAT = "ВВЕДИТЕ ЦИФРЫ С КАРТИНКИ В ЧАТ";

    /** The caption of the symbol captcha, white. Seen in {@code s03…/009.png}. */
    public static final String CAPTION_SYMBOLS = "ВВЕДИТЕ СИМВОЛЫ";

    /**
     * The orange the first caption is drawn in.
     *
     * <p>{@code (216, 127, 51)} - the exact colour of the reference sample, and by
     * coincidence also a slot of the Minecraft map palette.
     */
    private static final Color ORANGE = new Color(0xD8, 0x7F, 0x33);

    /** The face the captions are set in: a heavy condensed sans, as the references use. */
    private static final String CAPTION_FACE = "Impact";

    /** The face the captions fall back to when the heavy one is not installed. */
    private static final String CAPTION_FACE_FALLBACK = "Arial";

    /** The size of the caption face, before the horizontal squeeze. */
    private static final int CAPTION_SIZE = 20;

    /** The width the caption is squeezed to, in canvas pixels. */
    private static final int CAPTION_WIDTH = 235;

    /** How far the horizontal squeeze may go, so that the face stays readable. */
    private static final double CAPTION_MIN_SQUEEZE = 0.55;
    private static final double CAPTION_MAX_SQUEEZE = 1.5;

    /** The thickness of the outline the captions carry. */
    private static final float CAPTION_OUTLINE = 2.5f;

    /* ============================================================== variants */

    /**
     * The number captcha, without a caption: the LimboFilter map, scaled up to the size
     * the gallery presents it at.
     *
     * <p>The answer is the number in digits, the text that is drawn is the number in
     * Russian words.
     */
    public static final class NumberWord implements Cg {

        private final String answer;
        private final String text;
        private final BufferedImage img;
        private final int[] roi;

        public NumberWord() {
            this(new Random());
        }

        public NumberWord(Random r) {
            LimboFilter.Map map = new LimboFilter.Map(r);
            this.answer = map.answer();
            this.text = map.text();
            this.img = composite(map.image(), null).image();
            this.roi = scaleBand(map.roi(), map.image().getWidth(), map.image().getHeight(), H);
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "ru-numberword";
        }

        @Override
        public String answer() {
            return answer;
        }

        /** The number as it is drawn: in words, not in digits. */
        @Override
        public String text() {
            return text;
        }

        /**
         * The challenge the player is shown.
         *
         * <p>Same string as the plugin's own chat line for this mode, and the same
         * string the gallery bakes into the captcha in the samples that carry a caption.
         */
        @Override
        public String prompt() {
            return CAPTION_DIGITS;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return SRC_NUMBER;
        }
    }

    /**
     * The number captcha with one of the gallery's captions drawn onto the canvas.
     *
     * <p>The caption is the plugin's chat string, composited by the gallery operator -
     * it is not part of the renderer, and the renderer never draws it.
     */
    public static final class NumberWordCaption implements Cg {

        /** The captions the reference samples carry for the number family. */
        private static final String[] CAPTIONS = {CAPTION_DIGITS, CAPTION_DIGITS_CHAT};

        private final String answer;
        private final String text;
        private final String caption;
        private final BufferedImage img;
        private final int[] roi;

        public NumberWordCaption() {
            this(new Random());
        }

        public NumberWordCaption(Random r) {
            LimboFilter.Map map = new LimboFilter.Map(r);
            this.answer = map.answer();
            this.text = map.text();
            this.caption = CAPTIONS[r.nextInt(CAPTIONS.length)];
            Composite built = composite(map.image(), caption);
            this.img = built.image();
            this.roi = scaleBand(map.roi(), map.image().getWidth(), map.image().getHeight(),
                    built.captionTop());
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "ru-numberword-caption";
        }

        @Override
        public String answer() {
            return answer;
        }

        /** The number as it is drawn: in words, not in digits. */
        @Override
        public String text() {
            return text;
        }

        /** The caption that is drawn onto the canvas. */
        @Override
        public String prompt() {
            return caption;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return SRC_NUMBER;
        }
    }

    /**
     * The symbol captcha: the LimboFilter map in its symbol mode, scaled up, with the
     * gallery's white caption on top of it.
     *
     * <p>The answer is the character string, and it is also what is drawn, so
     * {@link #text()} is the same string.
     */
    public static final class Symbols implements Cg {

        private final String answer;
        private final String text;
        private final BufferedImage img;
        private final int[] roi;

        public Symbols() {
            this(new Random());
        }

        public Symbols(Random r) {
            LimboFilter.Symbols map = new LimboFilter.Symbols(r);
            this.answer = map.answer();
            this.text = map.text();
            Composite built = composite(map.image(), CAPTION_SYMBOLS);
            this.img = built.image();
            this.roi = scaleBand(map.roi(), map.image().getWidth(), map.image().getHeight(),
                    built.captionTop());
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "ru-symbols";
        }

        @Override
        public String answer() {
            return answer;
        }

        @Override
        public String text() {
            return text;
        }

        @Override
        public String prompt() {
            return CAPTION_SYMBOLS;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return SRC_SYMBOLS;
        }
    }

    /* ------------------------------------------------------------- internals */

    /**
     * The gallery's presentation of a map: the map scaled up to the canvas the gallery
     * presents the catalogue at, and the caption drawn on top of it.
     *
     * <p>The scale is <b>bilinear</b>, the way the gallery's own
     * {@code getScaledInstance(250, 150)} is: the rescaled picture therefore carries
     * colours that are not in the map palette, and a sample has a few thousand distinct
     * colours - the same order as the reference samples (1372..23291 in the V2 section).
     * A nearest-neighbour scale would keep the palette and would be wrong.
     *
     * @param map the map to present
     * @param caption the chat string to draw on top, or {@code null} for none
     * @return the composite and the first row the caption's ink is on
     */
    private static Composite composite(BufferedImage map, String caption) {
        BufferedImage out = Img.rgb(W, H);
        Graphics2D g = Img.g2d(out, true);
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION,
                RenderingHints.VALUE_INTERPOLATION_BILINEAR);
        g.setRenderingHint(RenderingHints.KEY_RENDERING,
                RenderingHints.VALUE_RENDER_QUALITY);
        g.drawImage(map, 0, 0, W, H, null);
        int captionTop = H;
        if (caption != null) {
            captionTop = drawCaption(g, caption);
        }
        g.dispose();
        return new Composite(out, captionTop);
    }

    /**
     * A finished composite and the first row the caption's ink is on.
     *
     * <p>The second number is what keeps the caption out of the text band: the caption
     * is a <b>different</b> string, and a recogniser that is handed it would learn to
     * read it instead of the words.
     *
     * @param image the composite
     * @param captionTop the first row the caption's ink is on, {@link #H} when there is
     *                   no caption
     */
    private record Composite(BufferedImage image, int captionTop) {
    }

    /**
     * The band of the map that carries the text, in the coordinates of the composite.
     *
     * <p>The band is the tightest rectangle around the ink of the map, so it is scaled
     * with the map. It is then cut off at the caption, so that the caption is never
     * part of the band a recogniser is handed.
     *
     * <p>The words of a number fill the map from the left margin to the right edge and
     * over the three lines, so the band of a number sample is a wide rectangle over
     * the upper two thirds of the picture - which is where the words are.
     *
     * @param band the band of the map, in the map's own coordinates
     * @param srcW the width of the map the band belongs to
     * @param srcH the height of that map
     * @param maxBottom the last row the band may use, {@link #H} for no limit
     */
    static int[] scaleBand(int[] band, int srcW, int srcH, int maxBottom) {
        if (band == null || band.length != 4 || srcW <= 0 || srcH <= 0) {
            return null;
        }
        int x = Math.round(band[0] * (float) W / srcW);
        int y = Math.round(band[1] * (float) H / srcH);
        int w = Math.round(band[2] * (float) W / srcW);
        int h = Math.round(band[3] * (float) H / srcH);

        x = Math.max(0, Math.min(W - 1, x));
        y = Math.max(0, Math.min(H - 1, y));
        w = Math.max(1, Math.min(W - x, w));
        h = Math.max(1, Math.min(H - y, h));

        int bottom = y + h;
        if (maxBottom >= 0 && maxBottom < bottom) {
            h = Math.max(1, maxBottom - y);
        }
        return new int[]{x, y, w, h};
    }

    /**
     * The caption, in the heavy condensed face the reference samples use, at the bottom
     * of the canvas, in the colour the reference samples use.
     *
     * <p>The face is a heavy condensed sans, squeezed horizontally so that the caption spans
     * the canvas - the reference samples do the same, and the long caption
     * ({@code ВВЕДИТЕ ЦИФРЫ С КАРТИНКИ В ЧАТ}) is squeezed the hardest, exactly as in
     * {@code s02…/011.png}. The short caption
     * ({@code ВВЕДИТЕ СИМВОЛЫ}) is stretched instead, which is also what
     * {@code s03…/009.png} shows.
     *
     * <p>The outline is the gallery operator's: the orange caption carries a black
     * outline in the reference sample. The black and the white caption get an outline of
     * the opposite colour, because the field of a map is a colour of the map palette and
     * a black caption would disappear into the dark slots of it.
     *
     * @return the first row the caption's ink is on
     */
    private static int drawCaption(Graphics2D g, String caption) {
        Color fill;
        Color outline;
        if (CAPTION_DIGITS.equals(caption)) {
            fill = ORANGE;
            outline = Color.BLACK;
        } else if (CAPTION_SYMBOLS.equals(caption)) {
            fill = Color.WHITE;
            outline = Color.BLACK;
        } else {
            fill = Color.BLACK;
            outline = Color.WHITE;
        }

        Graphics2D cg = (Graphics2D) g.create();
        Font font = captionFont();
        cg.setFont(font);
        int natural = cg.getFontMetrics(font).stringWidth(caption);
        double squeeze = (double) CAPTION_WIDTH / Math.max(1, natural);
        squeeze = Math.max(CAPTION_MIN_SQUEEZE, Math.min(CAPTION_MAX_SQUEEZE, squeeze));

        cg.scale(squeeze, 1.0);
        int x = (int) Math.round(4.0 / squeeze);
        int y = H - 6;

        cg.setStroke(new BasicStroke(CAPTION_OUTLINE));
        cg.setColor(outline);
        cg.drawString(caption, x, y);
        cg.setColor(fill);
        cg.drawString(caption, x, y);
        cg.dispose();

        // the first row the ink of the caption is on, so that the text band can be cut
        // off above it
        FontRenderContext frc = g.getFontRenderContext();
        GlyphVector vector = font.createGlyphVector(frc, caption);
        Rectangle2D ink = vector.getVisualBounds();
        int top = y + (int) Math.floor(ink.getY());
        return Math.max(0, Math.min(H, top));
    }

    /**
     * The heavy condensed face, or a plain bold one when it is not installed.
     *
     * <p>{@code new Font} never fails - it falls back to the default logical face - so
     * the family of the result is checked instead of the exception.
     */
    private static Font captionFont() {
        Font f = Img.font(CAPTION_FACE, Font.BOLD, CAPTION_SIZE);
        if (!f.getFamily().equalsIgnoreCase(CAPTION_FACE)) {
            f = Img.font(CAPTION_FACE_FALLBACK, Font.BOLD, CAPTION_SIZE);
        }
        return f;
    }
}
