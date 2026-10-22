package dev.captcha.gens;

import dev.captcha.Cg;

import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.LinearGradientPaint;
import java.awt.Shape;
import java.awt.Stroke;
import java.awt.font.FontRenderContext;
import java.awt.font.GlyphVector;
import java.awt.font.TextAttribute;
import java.awt.geom.AffineTransform;
import java.awt.geom.CubicCurve2D;
import java.awt.geom.PathIterator;
import java.awt.geom.Point2D;
import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;
import java.awt.image.DataBufferInt;
import java.util.BitSet;
import java.util.HashMap;
import java.util.Random;

/**
 * Clean-room reimplementation of the map captcha of <b>Elytrium/LimboFilter</b>, the
 * Velocity-proxy anti-bot plugin that renders the Russian number-word family of the
 * gallery catalogue (the number-word, symbol, framed 3x3 and framed 2x2 sections).
 *
 * <h2>What the player sees</h2>
 * A Minecraft map item. The canvas is 128x128 for a plain captcha and
 * {@code 128*W} x {@code 128*H} for the framed one, and the finished picture is reduced
 * to the 144 slots of the Minecraft map palette - the player only ever sees the map,
 * so the quantisation is part of the rendering and not a post-process.
 * <ul>
 *   <li>the text is painted in <b>palette indices</b>, and in the gradient mode every
 *       pixel takes the colour the gradient has <i>at that pixel</i>, so a single word
 *       changes colour as it runs across the canvas - that is where the multi-coloured
 *       words of the catalogue come from;</li>
 *   <li>every glyph is turned into an outline, tilted by up to a quarter of a radian
 *       and stamped into a 44x128 cell, with a second, offset stamp of the stroked
 *       outline on top of it;</li>
 *   <li>the words are laid out one per line and a word that does not fit is
 *       <b>clipped at the right edge</b> - never wrapped, never shrunk. That clipping
 *       is the signature that identified the plugin;</li>
 *   <li>the finished text is bent by a two-axis wave and its rim is darkened;</li>
 *   <li>three black bezier curves are drawn <b>over</b> the text.</li>
 * </ul>
 *
 * <h2>Provenance</h2>
 * The upstream is <a href="https://github.com/Elytrium/LimboFilter">Elytrium/LimboFilter</a>
 * and it is licensed <b>AGPL-3.0</b>, so nothing of it is carried over here. The
 * algorithm was read from the upstream sources and written again from scratch: the
 * canvas sizes, the settings defaults, the draw order and the arithmetic are the
 * upstream values, the code, the comments and the names are not.
 *
 * <p>Upstream renderer: {@code net.elytrium.limbofilter.captcha.painter.CaptchaPainter}
 * - methods {@code drawCaptcha}, {@code drawText}, {@code drawCurves} and
 * {@code addCurve}; the glyph rasteriser is
 * {@code net.elytrium.limbofilter.captcha.painter.RenderedFont} (its constructor and
 * its private {@code drawShape}); the two effects are
 * {@code net.elytrium.limbofilter.captcha.painter.RippleEffect#filter} and
 * {@code net.elytrium.limbofilter.captcha.painter.OutlineEffect#filter}; the answer
 * and the spelling come from
 * {@code net.elytrium.limbofilter.captcha.CaptchaGenerator} - methods
 * {@code randomAnswer}, {@code spellNumber}, {@code genNewPacket} and
 * {@code initializeGenerator}; every default quoted below is from
 * {@code net.elytrium.limbofilter.Settings}.
 *
 * <h2>What had to be reconstructed</h2>
 * <ul>
 *   <li><b>The Russian word lists.</b> The upstream ships English words; the Russian
 *       ones are per-server configuration and were not recovered. The tables below are
 *       a reconstruction of the correct Russian for 1..999 - units, the irregular
 *       teens, the round tens and the hundreds. They are lower case, like most of the
 *       catalogue's number samples; the symbol samples of the catalogue are upper
 *       case, and so is the charset used for them.</li>
 *   <li><b>The background.</b> The upstream paints the captcha onto a backplate image
 *       that the server owner supplies ({@code BACKPLATE_PATHS}); the upstream ships no
 *       assets, and the backplates of the captured servers (the Shrek, the beach, the
 *       sunset, the moire textures of the catalogue) are not recoverable either. This
 *       generator therefore draws a <b>procedural backdrop</b> - a smooth two-colour
 *       field - and quantises it to the map palette like everything else. It does not
 *       pretend to reproduce a backplate it does not have.</li>
 *   <li><b>The colour of the symbols.</b> The upstream draws them from its
 *       {@code PATTERN} setting, a Latin charset. The catalogue is Russian and its
 *       samples show upper case Cyrillic letters mixed with digits, so the Cyrillic
 *       alphabet is used here.</li>
 *   <li><b>The size of the type.</b> The upstream's defaults (a 78 point face in a
 *       44x128 cell) are far too large for a 128 pixel map: with them a line holds
 *       about four characters, a word like "восемьдесят" is cut after four letters
 *       and a three word number does not fit on the canvas at all - the answer could
 *       not be read off the picture in 73 % of the samples. The servers behind the
 *       catalogue ran the plugin with a much smaller type and a much tighter advance:
 *       their number samples carry about eleven characters per line and three lines,
 *       with letters about ten map pixels wide and fifteen high, an advance of about
 *       twelve map pixels and a line advance of about twenty-three. <b>That is the
 *       configuration used for the number family</b> - measured off the reference
 *       samples of the catalogue, not off a formula. Their <b>symbol</b> samples are a
 *       different server with the upstream's defaults, and those are used for the
 *       symbol family; see {@link Type}. The drawing algorithm is the upstream's and is
 *       the same for both: the same per-glyph rotation, the same outline stamp, the
 *       same ripple, the same curves, the same gradient fill and the same quantisation
 *       to the map palette. Only the numbers of the type are different from the
 *       upstream defaults, and they are the numbers a server of that kind would have
 *       had in its configuration file. The outline offset and the ripple amplitude are
 *       absolute map pixels in the upstream, so they are scaled with the type as
 *       well - with the upstream's values the outline would sit four pixels away
 *       from a ten pixel letter and the wave would tilt the whole line diagonally,
 *       and the reference samples show neither.</li>
 * </ul>
 *
 * <h2>Upstream quirks, reproduced on purpose</h2>
 * <ul>
 *   <li><b>The curve width is ignored.</b> The upstream sets a stroke of
 *       {@code CURVE_SIZE} (2) and then draws the curve with {@code drawLine}, which
 *       is always one pixel wide. The curves are therefore one pixel wide here too,
 *       exactly as they are on the server.</li>
 *   <li><b>The line break looks at the space, not at the word.</b> A new line starts
 *       after a space, and the pen jumps back to the left margin - so a word is never
 *       split, and a word that is too long runs off the canvas and is cut.</li>
 *   <li><b>The gradient axis is not scaled with the canvas.</b> The upstream's
 *       gradient start and end points are absolute values, so on the 384x384 framed
 *       canvas the gradient only covers the left third.</li>
 *   <li><b>The shipped gradient cannot run.</b> The upstream's default fraction list
 *       has ten entries and its default colour list has seven, and its gradient code
 *       refuses to start when the two differ - a server that only switched the
 *       gradient on would not come up. The distribution used here is the upstream's
 *       own fallback, the one it computes for an empty fraction list.</li>
 *   <li><b>The framed captcha is one picture cut into a grid.</b> The upstream paints
 *       the whole text on one canvas of {@code 128*W} by {@code 128*H}, hands that
 *       canvas to the map canvas, which cuts it into maps of 128x128, and then turns
 *       each of those maps on its own. The nine maps of the 3x3 captcha are therefore
 *       nine <b>pieces of one picture</b>, not nine copies of the captcha - which is
 *       what the catalogue samples show: different fragments of one text, each in a
 *       different orientation.</li>
 *   <li><b>The answer is the digits, not the words.</b> With the number spelling
 *       enabled the map shows the number in words and the player has to type the
 *       digits. The upstream compares the answer case-insensitively and strips a
 *       leading slash, so {@code /298} is accepted as well as {@code 298}.</li>
 *   <li><b>Black text.</b> The upstream's map code treats the first palette slot as
 *       "nothing here", so a glyph that happens to land on pure black would vanish.
 *       The palette helper this repository shares between the map captchas never
 *       returns the transparent slots, so black comes out as the darkest grey of the
 *       palette and the glyph stays visible.</li>
 * </ul>
 */
public final class LimboFilter {

    private LimboFilter() {
    }

    /** Plugin name, flat, as the {@code dataset/out_ru/} layout expects it. */
    public static final String PLUGIN = "LimboFilter";

    /** The upstream renderer this file reproduces. */
    public static final String SRC = "net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha";

    /** The upstream answer generator, for the two types whose answer is a number. */
    public static final String SRC_ANSWER =
            "net.elytrium.limbofilter.captcha.CaptchaGenerator#randomAnswer";

    /** The upstream spelling routine, for the two types whose answer is a number. */
    public static final String SRC_SPELLING =
            "net.elytrium.limbofilter.captcha.CaptchaGenerator#spellNumber";

    /* ------------------------------------------------------------------ settings */

    /** Edge length of one Minecraft map. */
    private static final int MAP_EDGE = 128;

    /**
     * One <b>type configuration</b>: the numbers a server would have had in its
     * configuration file.
     *
     * <p>The upstream ships one set of them ({@code FONT_LETTER_WIDTH},
     * {@code FONT_LETTER_HEIGHT}, {@code RENDER_FONT_SIZE}, {@code LETTER_SPACING_X},
     * {@code LETTER_SPACING_Y}, {@code LETTER_OFFSET_X/Y}, {@code FONT_OUTLINE_OFFSET_X/Y}
     * and {@code FONT_RIPPLE_AMPLITUDE_WIDTH/HEIGHT}), and a server may change any of
     * them. The catalogue was shot on <b>more than one</b> server, and the two families
     * of it were rendered with <b>two different configurations</b> - measured off the
     * reference samples:
     *
     * <ul>
     *   <li>{@link #TYPE_DEFAULT} is the upstream's own default. The symbol samples of
     *       the gallery catalogue are exactly that: three characters
     *       every 30 map pixels, the first one starting at map row 32, the letters
     *       about 55 map pixels high.</li>
     *   <li>{@link #TYPE_SMALL} is the configuration of the server behind the Russian
     *       number samples (the number-word and the framed-puzzle sections): about eleven
     *       characters per line, three lines, letters about ten map pixels wide and
     *       fifteen high, an advance of twelve map pixels and a line advance of
     *       twenty-three. With the upstream's default a three word number does not fit
     *       on a 128 pixel map at all - the third word falls off the bottom and the
     *       long words are cut after four letters, so the answer could not be read off
     *       the picture in 73 % of the samples.</li>
     * </ul>
     *
     * <p>The <b>drawing algorithm is the upstream's and is the same for both</b>: the
     * same per-glyph rotation, the same outline stamp, the same ripple, the same
     * curves, the same gradient fill and the same quantisation to the map palette.
     * Only these numbers differ.
     *
     * @param fontSize  the size of the face the glyphs are cut from
     * @param cellW     the width of one glyph cell, in map pixels
     * @param cellH     the height of one glyph cell, in map pixels
     * @param offsetX   the distance of the first glyph from the left edge
     * @param offsetY   the distance of the first glyph from the top edge
     * @param spacingX  the extra advance between two glyphs
     * @param spacingY  the extra advance between two lines
     * @param outlineX  the horizontal offset of the outline stamp
     * @param outlineY  the vertical offset of the outline stamp
     * @param rippleW   the divisor of the horizontal wave amplitude
     * @param rippleH   the divisor of the vertical wave amplitude
     */
    private record Type(double fontSize, int cellW, int cellH, int offsetX, int offsetY,
                        int spacingX, int spacingY, int outlineX, int outlineY,
                        double rippleW, double rippleH) {
    }

    /**
     * The upstream's own defaults - the configuration of the catalogue's symbol samples.
     *
     * <p>With them a line of the 128 pixel map holds about four characters, which is
     * why a three word number does not fit on the map - but the symbol captcha is one
     * row of three characters, and it fits perfectly.
     */
    private static final Type TYPE_DEFAULT =
            new Type(78.0, 44, 128, 12, 0, -14, 0, -4, 4, 100.0, 10.0);

    /**
     * The configuration of the server behind the catalogue's Russian number samples.
     *
     * <p>Measured off the reference samples of the "API V2" section: the letters are
     * about ten map pixels wide and fifteen high, they sit every twelve map pixels, the
     * lines every twenty-three, the first row of the first word starts at map row 37
     * and the left margin is at map column 3. The outline offset and the ripple
     * amplitude are absolute map pixels in the upstream, so they are scaled with the
     * type as well - with the upstream's values the outline would sit four pixels away
     * from a ten pixel letter and the wave would tilt the whole line diagonally, and
     * the reference samples show neither.
     */
    private static final Type TYPE_SMALL =
            new Type(36.0, 20, 32, 0, 30, -8, 7, -1, 1, 309.0, 31.0);

    /** Thickness of the stroke that is stamped around every glyph. */
    private static final double OUTLINE_RATE = 1.25;

    /** Radius of the neighbourhood the rim effect looks at, in pixels. */
    private static final int RIM_RADIUS = 1;

    /** How many curves are drawn over the text. */
    private static final int CURVE_COUNT = 3;

    /**
     * The width the upstream asks for. It never reaches the picture: the curves are
     * drawn with {@code drawLine}, which is one pixel wide whatever the stroke says.
     */
    private static final int CURVE_WIDTH = 2;

    /** How many of the frames of a framed captcha are turned, from 0 to 1. */
    private static final double FRAME_ROTATION_CHANCE = 0.33;

    /** Number of digits of the spelled-out number. */
    private static final int NUMBER_LENGTH = 3;

    /** The first number the number captcha can show - the upstream draws from 10^(L-1). */
    private static final int NUMBER_MIN = (int) Math.pow(10, NUMBER_LENGTH - 1);

    /** Number of characters of the symbol captcha. */
    private static final int SYMBOL_LENGTH = 3;

    /** The zoom the upstream applies to the glyph outline before it is rasterised. */
    private static final double GLYPH_ZOOM = 1.35;

    /** The palette index the curves are painted with - one of the black map slots. */
    private static final int CURVE_SLOT = 1;

    /** The upstream colour list the gradient is built from. */
    private static final Color[] GRADIENT_COLOURS = {
            new Color(0x000000), new Color(0xAA0000), new Color(0x00AA00), new Color(0x0000AA),
            new Color(0xAAAA00), new Color(0xAA00AA), new Color(0x00AAAA)};

    /**
     * The distribution of the gradient colours along the axis.
     *
     * <p>The upstream ships a list of ten fractions for its seven colours, and its
     * gradient code refuses to run when the two do not have the same length - so the
     * gradient of a server that only flipped {@code GRADIENT_ENABLED} on would throw
     * and the plugin would not start. The distribution used here is the upstream's own
     * fallback, the one it computes for an empty fraction list: the colours are spread
     * evenly over the axis.
     */
    private static final float[] GRADIENT_FRACTIONS = {
            0f, 1f / 6f, 2f / 6f, 3f / 6f, 4f / 6f, 5f / 6f, 1f};

    /** The three logical faces the upstream cycles through. */
    private static final String[] FACES = {Font.SANS_SERIF, Font.SERIF, Font.MONOSPACED};

    /** The characters the symbol captcha is drawn from. */
    private static final String SYMBOL_PATTERN =
            "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789";

    /**
     * The characters the number captcha needs: the lower case Russian alphabet and the
     * space that separates the words. The catalogue's number samples are mostly lower
     * case ("триста пятьдесят"), the exception being the ones that spell the number in
     * capitals.
     */
    private static final String NUMBER_ALPHABET =
            "абвгдеёжзийклмнопрстуфхцчшщъыьэюя ";

    /** The catalogue's caption for the number captcha. */
    private static final String NUMBER_PROMPT = "ВВЕДИТЕ ТОЛЬКО ЦИФРЫ";

    /** The catalogue's caption for the symbol captcha. */
    private static final String SYMBOL_PROMPT = "ВВЕДИТЕ СИМВОЛЫ";

    /** The catalogue's caption for the framed puzzle. */
    private static final String PUZZLE_PROMPT = "НАПИШИ ЦИФРАМИ";

    /* --------------------------------------------------------------------- words */

    /**
     * The Russian units, <b>one based</b>: the slot 0 is empty because a number that
     * ends in zero contributes no unit word at all.
     */
    private static final String[] UNIT_WORDS = {
            "", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"};

    /**
     * The Russian teens, 10..19. They are irregular - they are <b>not</b> a round ten
     * plus a unit, which is why they get a table of their own.
     */
    private static final String[] TEEN_WORDS = {
            "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
            "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"};

    /** The Russian round tens, indexed by the tens digit. */
    private static final String[] TEN_WORDS = {
            "", "десять", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
            "семьдесят", "восемьдесят", "девяносто"};

    /** The Russian hundreds, indexed by the hundreds digit. */
    private static final String[] HUNDRED_WORDS = {
            "", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
            "семьсот", "восемьсот", "девятьсот"};

    /**
     * Spells {@code n} (1..999) out in Russian, lower case, without the {@code и}
     * connector.
     *
     * <p>The hundreds, the round tens and the units are joined with a single space and
     * the empty parts are dropped, so a round hundred or a round ten contributes no
     * word of its own. The teens are looked up in their own table.
     */
    static String spellNumber(int n) {
        StringBuilder sb = new StringBuilder();
        int hundreds = n / 100;
        int rest = n % 100;

        if (hundreds > 0) {
            sb.append(HUNDRED_WORDS[hundreds]);
        }

        if (rest >= 10 && rest < 20) {
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append(TEEN_WORDS[rest - 10]);
        } else {
            int tens = rest / 10;
            int units = rest % 10;
            if (tens > 0) {
                if (sb.length() > 0) {
                    sb.append(' ');
                }
                sb.append(TEN_WORDS[tens]);
            }
            if (units > 0) {
                if (sb.length() > 0) {
                    sb.append(' ');
                }
                sb.append(UNIT_WORDS[units]);
            }
        }

        return sb.toString();
    }

    /* ================================================================ generators */

    /** A finished captcha: the picture and the band of the canvas that carries the text. */
    private record Rendered(BufferedImage image, int[] roi) {
    }

    /**
     * The plain captcha: the number spelled out in Russian words, one word per line,
     * on a single 128x128 map. The answer is the number in digits, the text that is
     * drawn is the number in words.
     */
    public static final class Map implements Cg {

        private final String answer;
        private final String text;
        private final BufferedImage image;
        private final int[] roi;

        public Map() {
            this(new Random());
        }

        public Map(Random rnd) {
            int value = NUMBER_MIN + rnd.nextInt(NUMBER_MIN * 9);
            this.answer = Integer.toString(value);
            this.text = spellNumber(value);
            Rendered rendered = paint(1, 1, this.text, NUMBER_ALPHABET, TYPE_SMALL, rnd);
            this.image = rendered.image();
            this.roi = rendered.roi();
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
            return answer;
        }

        /** The number as it is drawn: in words, not in digits. */
        @Override
        public String text() {
            return text;
        }

        @Override
        public String prompt() {
            return NUMBER_PROMPT;
        }

        @Override
        public BufferedImage image() {
            return image;
        }

        /** The band of the canvas the words are drawn in. */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return SRC + "; " + SRC_ANSWER + "; " + SRC_SPELLING;
        }
    }

    /**
     * The symbol captcha: a random string of characters, the upstream's
     * {@code PATTERN} mode with the number spelling switched off. The answer is that
     * string, and it is also what is drawn, so {@link #text()} needs no override.
     */
    public static final class Symbols implements Cg {

        private final String answer;
        private final BufferedImage image;
        private final int[] roi;

        public Symbols() {
            this(new Random());
        }

        public Symbols(Random rnd) {
            StringBuilder sb = new StringBuilder(SYMBOL_LENGTH);
            for (int i = 0; i < SYMBOL_LENGTH; i++) {
                sb.append(SYMBOL_PATTERN.charAt(rnd.nextInt(SYMBOL_PATTERN.length())));
            }
            this.answer = sb.toString();
            Rendered rendered = paint(1, 1, this.answer, SYMBOL_PATTERN, TYPE_DEFAULT, rnd);
            this.image = rendered.image();
            this.roi = rendered.roi();
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "symbols";
        }

        @Override
        public String answer() {
            return answer;
        }

        @Override
        public String prompt() {
            return SYMBOL_PROMPT;
        }

        @Override
        public BufferedImage image() {
            return image;
        }

        /** The band of the canvas the characters are drawn in. */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return SRC + "; " + SRC_ANSWER;
        }
    }

    /**
     * The framed captcha, three by three: one 384x384 picture that is cut into nine
     * maps of 128x128, and every one of those maps is turned by a random multiple of
     * ninety degrees. The answer is the number in digits, the same as for
     * {@link Map}.
     *
     * <h2>There is no single text band</h2>
     * The words are spread over the nine maps, and every map carries its own piece of
     * the text and is turned on its own, so there is no rectangle of the picture that
     * holds the answer - {@link #roi()} stays {@code null}. A solver has to solve the
     * frames first: turn every map back, put the pieces together and only then read
     * the number. The frames keep their place in the grid here (the upstream cuts one
     * picture into a grid and turns the frames in place), so the text is recoverable
     * in principle - but it is not a recogniser's training target, it is a
     * reconstruction aid and a solver-side transformation.
     */
    public static final class Framed3x3 implements Cg {

        private final String answer;
        private final String text;
        private final BufferedImage image;

        public Framed3x3() {
            this(new Random());
        }

        public Framed3x3(Random rnd) {
            int value = NUMBER_MIN + rnd.nextInt(NUMBER_MIN * 9);
            this.answer = Integer.toString(value);
            this.text = spellNumber(value);
            this.image = paint(3, 3, this.text, NUMBER_ALPHABET, TYPE_SMALL, rnd).image();
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "framed3x3";
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

        @Override
        public String prompt() {
            return PUZZLE_PROMPT;
        }

        @Override
        public BufferedImage image() {
            return image;
        }

        @Override
        public String source() {
            return SRC + "; " + SRC_ANSWER + "; " + SRC_SPELLING;
        }
    }

    /**
     * The framed captcha, two by two: the same, on a 256x256 picture that is cut into
     * four maps of 128x128. The answer is the number in digits.
     *
     * <h2>There is no single text band</h2>
     * As with {@link Framed3x3}, the words are spread over the four maps, every map
     * carries its own piece of the text and is turned on its own, so there is no
     * rectangle of the picture that holds the answer and {@link #roi()} stays
     * {@code null}. A solver has to turn the frames back and put the pieces together
     * before it can read the number.
     */
    public static final class Framed2x2 implements Cg {

        private final String answer;
        private final String text;
        private final BufferedImage image;

        public Framed2x2() {
            this(new Random());
        }

        public Framed2x2(Random rnd) {
            int value = NUMBER_MIN + rnd.nextInt(NUMBER_MIN * 9);
            this.answer = Integer.toString(value);
            this.text = spellNumber(value);
            this.image = paint(2, 2, this.text, NUMBER_ALPHABET, TYPE_SMALL, rnd).image();
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "framed2x2";
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

        @Override
        public String prompt() {
            return PUZZLE_PROMPT;
        }

        @Override
        public BufferedImage image() {
            return image;
        }

        @Override
        public String source() {
            return SRC + "; " + SRC_ANSWER + "; " + SRC_SPELLING;
        }
    }

    /* ================================================================ rendering */

    /**
    /**
     * The whole upstream pipeline, in the order the upstream applies it.
     *
     * @param framesW how many maps wide the picture is
     * @param framesH how many maps high the picture is
     * @param text    the text to draw
     * @param alphabet the characters the text may consist of
     * @param type    the type configuration of the server the picture comes from
     */
    private static Rendered paint(int framesW, int framesH, String text, String alphabet,
                                  Type type, Random rnd) {
        int width = MAP_EDGE * framesW;
        int height = MAP_EDGE * framesH;

        // The framed captcha scales the face and the layout with the frame.
        int scaleX = framesW;
        int scaleY = framesH;
        int cellW = type.cellW() * scaleX;
        int cellH = type.cellH() * scaleY;

        Font face = new Font(FACES[rnd.nextInt(FACES.length)], Font.PLAIN, (int) type.fontSize());
        java.util.Map<Character, BitSet> glyphs =
                glyphs(face, framesW, framesH, cellW, cellH, alphabet, type);

        // The colour field the text is painted with: one palette index per pixel.
        int[] field = gradient(width, height, rnd);

        // The text itself, in palette indices.
        int[] ink = new int[width * height];
        drawText(ink, glyphs, cellW, cellH, text, field, width, height, scaleX, scaleY, type);

        // The wave, then the rim.
        wave(ink, width, height, type, rnd);
        rim(ink, width, height);

        // The band of the canvas the words ended up in.
        int[] roi = band(ink, width, height);

        // The backdrop, then the text on top of it.
        int[] pixels = backdrop(width, height, rnd);
        for (int i = 0; i < ink.length; i++) {
            if (ink[i] != 0) {
                pixels[i] = ink[i];
            }
        }

        // The curves go over everything.
        curves(pixels, width, height, rnd);

        // And the frames of a framed captcha are turned independently.
        if (framesW > 1 || framesH > 1) {
            turnFrames(pixels, width, framesW, framesH, rnd);
        }

        return new Rendered(picture(pixels, width, height), roi);
    }

    /**
     * The tightest rectangle around the ink, as {@code [x, y, w, h]}.
     *
     * <p>The words are laid out one per line and a word that does not fit is cut off at
     * the right edge, so the band never reaches past the canvas.
     */
    private static int[] band(int[] ink, int width, int height) {
        int minX = width;
        int minY = height;
        int maxX = -1;
        int maxY = -1;
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                if (ink[y * width + x] == 0) {
                    continue;
                }
                minX = Math.min(minX, x);
                minY = Math.min(minY, y);
                maxX = Math.max(maxX, x);
                maxY = Math.max(maxY, y);
            }
        }
        if (maxX < 0) {
            return null;
        }
        return new int[]{minX, minY, maxX - minX + 1, maxY - minY + 1};
    }

    /* -------------------------------------------------------------------- glyphs */

    /** The rasterised glyph cells, cached because they never change. */
    private static final java.util.Map<String, java.util.Map<Character, BitSet>> GLYPH_CACHE = new HashMap<>();

    /**
     * The rasterised cells of every character of the alphabet.
     *
     * <p>The upstream builds its three faces once, when the plugin starts, and every
     * captcha then takes the next face from the list. The tilt of a glyph is therefore
     * fixed for the whole run of the server - the same is true here, so the cells are
     * built once and kept.
     */
    private static synchronized java.util.Map<Character, BitSet> glyphs(Font face, int scaleX, int scaleY,
                                                                      int cellW, int cellH, String alphabet,
                                                                      Type type) {
        float size = (float) (type.fontSize() * Math.min(scaleX, scaleY));
        String key = face.getName() + "|" + size + "|" + cellW + "x" + cellH + "|" + alphabet
                + "|" + type.outlineX() + "x" + type.outlineY();
        java.util.Map<Character, BitSet> cached = GLYPH_CACHE.get(key);
        if (cached != null) {
            return cached;
        }

        Font font = face.deriveFont(java.util.Map.of(
                TextAttribute.SIZE, size,
                TextAttribute.STRIKETHROUGH, Boolean.FALSE,
                TextAttribute.UNDERLINE, Boolean.TRUE));
        FontRenderContext ctx = new FontRenderContext(null, true, true);

        java.util.Map<Character, BitSet> sheet = new HashMap<>();
        Random rnd = new Random(0x1F2B3C4DL);
        for (char c : alphabet.toCharArray()) {
            GlyphVector vector = font.createGlyphVector(ctx, String.valueOf(c));

            // Every glyph is tilted a little, and the tilt never changes afterwards.
            vector.setGlyphTransform(0, AffineTransform.getRotateInstance(
                    (rnd.nextDouble() - 0.5) * Math.PI / 8));

            // The cell is moved so that the visible box of the glyph starts at zero.
            Point2D pos = vector.getGlyphPosition(0);
            Rectangle2D box = vector.getGlyphVisualBounds(0).getBounds2D();
            vector.setGlyphPosition(0, new Point2D.Double(pos.getX() - box.getX(), pos.getY()));

            BitSet bits = new BitSet(cellW * cellH);
            Shape outline = vector.getGlyphOutline(0, -(float) cellW * 1.25f, -(float) cellH * 0.3125f);
            stamp(outline, bits, cellW, cellH, 0, 0);

            // The second stamp is the same outline, stroked and pushed aside: that is
            // the ragged border the catalogue samples show around every word.
            Stroke stroke = new BasicStroke((float) OUTLINE_RATE);
            stamp(stroke.createStrokedShape(outline), bits, cellW, cellH,
                    type.outlineX() * scaleX, type.outlineY() * scaleY);

            sheet.put(c, bits);
        }

        GLYPH_CACHE.put(key, sheet);
        return sheet;
    }

    /**
     * Rasterises a shape into a cell.
     *
     * <p>The shape is sampled at a point per pixel, the point being the pixel scaled
     * by a factor that is derived from the position of the shape's own bounding box -
     * which is what puts the glyph into the lower right corner of its cell. The rows
     * of the cell are counted from the bottom, so the cell is stored upside down.
     */
    private static void stamp(Shape shape, BitSet bits, int cellW, int cellH, int offsetX, int offsetY) {
        Rectangle2D box = shape.getBounds2D();
        double stepX = box.getX() / cellW * GLYPH_ZOOM;
        double stepY = box.getY() / cellH * GLYPH_ZOOM;

        for (int x = 0; x < cellW; x++) {
            for (int y = 0; y < cellH; y++) {
                if (shape.contains(stepX * x, stepY * y)) {
                    int index = (cellH - y - 1 + offsetY) * cellW + (cellW - x - 1 + offsetX);
                    if (index >= 0 && index < bits.size()) {
                        bits.set(index);
                    }
                }
            }
        }
    }

    /* ---------------------------------------------------------------------- text */

    /**
     * Lays the text out and paints it into the index array.
     *
     * <p>The pen starts at the left margin, every glyph is stamped at the pen and the
     * pen then moves on by the spacing plus the width of the cell. A new line starts
     * when the pen ran past the right margin, or - because every word goes on a line of
     * its own - right after a space. A word that is too long for the canvas is not
     * wrapped and not shrunk: it is cut off at the edge.
     */
    private static void drawText(int[] ink, java.util.Map<Character, BitSet> glyphs, int cellW, int cellH,
                                 String text, int[] field, int width, int height,
                                 int scaleX, int scaleY, Type type) {
        int offsetX = type.offsetX() * scaleX;
        int offsetY = type.offsetY() * scaleY;
        int spacingX = type.spacingX() * scaleX;
        int spacingY = type.spacingY() * scaleY;

        int x = offsetX;
        int y = offsetY;

        for (char c : text.toCharArray()) {
            BitSet data = glyphs.get(c);
            if (data == null) {
                continue;
            }

            for (int i = 0; i < cellW; i++) {
                for (int j = 0; j < cellH; j++) {
                    if (!data.get(j * cellW + i)) {
                        continue;
                    }
                    int localX = i + x;
                    int localY = j + y;
                    if (localX >= 0 && localY >= y && localX < width && localY < height) {
                        ink[localY * width + localX] = field[(localY * width + localX) % field.length];
                    }
                }
            }

            x += spacingX + cellW;
            if (x > width - offsetX || c == ' ') {
                x = offsetX;
                y += spacingY + cellH / 2;
            }
        }
    }

    /* ------------------------------------------------------------------ gradient */

    /**
     * The colour field of the text: one palette index per pixel of the canvas.
     *
     * <p>The gradient runs from a point whose vertical position is drawn at random to
     * a second one, and the horizontal ends are the upstream's absolute values - so on
     * the framed canvas the gradient only covers the left third of the picture.
     */
    private static int[] gradient(int width, int height, Random rnd) {
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = image.createGraphics();
        LinearGradientPaint paint = new LinearGradientPaint(
                0f,
                (float) (40.0 + rnd.nextFloat() * 2.0 * height),
                128f,
                (float) (80.0 - rnd.nextFloat() * 2.0 * height),
                GRADIENT_FRACTIONS,
                GRADIENT_COLOURS);
        g.setPaint(paint);
        g.fillRect(0, 0, width, height);
        g.dispose();

        int[] data = ((DataBufferInt) image.getRaster().getDataBuffer()).getData();
        int[] field = new int[width * height];
        for (int i = 0; i < field.length; i++) {
            field[i] = MapPalette.indexOf(data[i]);
        }
        return field;
    }

    /* ----------------------------------------------------------------- effects */

    /**
     * The wave: the picture is bent along both axes, the vertical one by up to a tenth
     * of its height and the horizontal one by up to a hundredth of its width. A pixel
     * of the source ends up at the displaced position, so the wave moves the ink
     * instead of only smearing it.
     */
    private static void wave(int[] ink, int width, int height, Type type, Random rnd) {
        int[] vertical = offsets(rnd.nextDouble() * 2 * Math.PI,
                (1 + rnd.nextDouble() * 2) * Math.PI, height / type.rippleH(), width);
        int[] horizontal = offsets(rnd.nextDouble() * 2 * Math.PI,
                (2 + rnd.nextDouble() * 2) * Math.PI, width / type.rippleW(), height);

        int[] dest = new int[ink.length];
        for (int x = 0; x < width; x++) {
            for (int y = 0; y < height; y++) {
                int ny = (y + vertical[x] + height) % height;
                int nx = (x + horizontal[ny] + width) % width;
                dest[ny * width + nx] = ink[y * width + x];
            }
        }
        System.arraycopy(dest, 0, ink, 0, ink.length);
    }

    /** The samples of one wave axis: a sine, folded into one period range. */
    private static int[] offsets(double phase, double span, double amplitude, int points) {
        double start = fold(phase, 2);
        double length = fold(span, 4);
        double step = length / points;

        int[] delta = new int[points];
        for (int i = 0; i < points; i++) {
            delta[i] = (int) Math.round(amplitude * Math.sin(start + i * step));
        }
        return delta;
    }

    /** Folds a value into {@code [0, multiples * PI)}. */
    private static double fold(double value, int multiples) {
        double bound = multiples * Math.PI;
        double magnitude = Math.abs(value);
        return magnitude - Math.floor(magnitude / bound) * bound;
    }

    /**
     * The rim: a pixel that touches empty space is darkened by clearing the two low
     * bits of its palette index, which moves it to the darker slot of its own colour
     * family. The outermost ring of the canvas is left alone.
     */
    private static void rim(int[] ink, int width, int height) {
        for (int x = RIM_RADIUS; x < width - RIM_RADIUS; x++) {
            for (int y = RIM_RADIUS; y < height - RIM_RADIUS; y++) {
                int value = ink[y * width + x];
                if (value == 0) {
                    continue;
                }
                boolean edge = false;
                for (int bx = x - RIM_RADIUS; bx <= x + RIM_RADIUS && !edge; bx++) {
                    for (int by = y - RIM_RADIUS; by <= y + RIM_RADIUS; by++) {
                        if (ink[by * width + bx] == 0) {
                            edge = true;
                            break;
                        }
                    }
                }
                if (edge) {
                    ink[y * width + x] = value & ~0b11;
                }
            }
        }
    }

    /* ----------------------------------------------------------------- backdrop */

    /**
     * The procedural backdrop that replaces the backplate image the server owner would
     * supply. It is a smooth field between two colours of the map palette, with a low
     * frequency ripple over it, and it is quantised to the palette like the rest.
     */
    private static int[] backdrop(int width, int height, Random rnd) {
        int a = rnd.nextInt(BACKDROP_SLOTS.length);
        int b = rnd.nextInt(BACKDROP_SLOTS.length - 1);
        if (b >= a) {
            b++;
        }
        int from = BACKDROP_SLOTS[a];
        int to = BACKDROP_SLOTS[b];

        double angle = rnd.nextDouble() * 2 * Math.PI;
        double dx = Math.cos(angle);
        double dy = Math.sin(angle);
        double phase = rnd.nextDouble() * 2 * Math.PI;
        double span = Math.max(width, height);

        int[] pixels = new int[width * height];
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                double t = (x * dx + y * dy) / span + 0.5;
                t += 0.12 * Math.sin(x * 0.07 + phase) * Math.sin(y * 0.09 - phase);
                t = Math.max(0.0, Math.min(1.0, t));

                int c0 = MapPalette.COLOURS[from];
                int c1 = MapPalette.COLOURS[to];
                int r = (int) Math.round(((c0 >> 16) & 0xFF) * (1 - t) + ((c1 >> 16) & 0xFF) * t);
                int g = (int) Math.round(((c0 >> 8) & 0xFF) * (1 - t) + ((c1 >> 8) & 0xFF) * t);
                int bl = (int) Math.round((c0 & 0xFF) * (1 - t) + (c1 & 0xFF) * t);
                pixels[y * width + x] = MapPalette.indexOf(0xFF000000 | (r << 16) | (g << 8) | bl);
            }
        }
        return pixels;
    }

    /** The palette slots the backdrop is built from - greys, dark tones and a few muted ones. */
    private static final int[] BACKDROP_SLOTS = {
            32, 33, 35, 12, 13, 84, 87, 116, 118, 119, 8, 24, 100, 104, 60, 40};

    /* ------------------------------------------------------------------- curves */

    /**
     * The interference curves, drawn over the text.
     *
     * <p>Three cubic beziers with random control points; one end of every curve is
     * always near the top or near the bottom edge of the canvas. The curve is flattened
     * into a polyline and drawn with {@code drawLine} - one pixel wide, whatever the
     * stroke says.
     */
    private static void curves(int[] pixels, int width, int height, Random rnd) {
        BufferedImage layer = new BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = layer.createGraphics();
        g.setColor(Color.BLACK);
        for (int i = 0; i < CURVE_COUNT; i++) {
            curve(g, width, height, rnd);
        }
        g.dispose();

        int[] data = ((DataBufferInt) layer.getRaster().getDataBuffer()).getData();
        for (int i = 0; i < data.length; i++) {
            if (((data[i] >>> 24) & 0xFF) != 0) {
                pixels[i] = CURVE_SLOT;
            }
        }
    }

    /** One cubic bezier, flattened and drawn as a polyline. */
    private static void curve(Graphics2D g, int width, int height, Random rnd) {
        CubicCurve2D cubic;
        if (rnd.nextBoolean()) {
            cubic = new CubicCurve2D.Double(
                    rnd.nextDouble() * width, rnd.nextDouble() * 0.1 * height,
                    rnd.nextDouble() * width, rnd.nextDouble() * height,
                    rnd.nextDouble() * width, rnd.nextDouble() * height,
                    rnd.nextDouble() * width, (0.8 + 0.1 * rnd.nextDouble()) * height);
        } else {
            cubic = new CubicCurve2D.Double(
                    rnd.nextDouble() * 0.1 * width, rnd.nextDouble() * height,
                    rnd.nextDouble() * width, rnd.nextDouble() * height,
                    rnd.nextDouble() * width, rnd.nextDouble() * height,
                    (0.8 + 0.1 * rnd.nextDouble()) * width, rnd.nextDouble() * height);
        }

        double[] coords = new double[6];
        PathIterator it = cubic.getPathIterator(null, 0.1);
        it.currentSegment(coords);
        Point2D.Double previous = new Point2D.Double(coords[0], coords[1]);
        it.next();

        g.setStroke(new BasicStroke(CURVE_WIDTH));

        while (!it.isDone()) {
            int segment = it.currentSegment(coords);
            if (segment == PathIterator.SEG_MOVETO || segment == PathIterator.SEG_LINETO) {
                Point2D.Double point = new Point2D.Double(coords[0], coords[1]);
                g.drawLine((int) previous.x, (int) previous.y, (int) point.x, (int) point.y);
                previous = point;
            }
            it.next();
        }
    }

    /* ------------------------------------------------------------------- frames */

    /**
     * Turns the frames of a framed captcha: each map of the grid is turned by a
     * random multiple of ninety degrees, and the chance of a frame being turned at all
     * is the upstream's one in three.
     */
    private static void turnFrames(int[] pixels, int width, int framesW, int framesH, Random rnd) {
        for (int fy = 0; fy < framesH; fy++) {
            for (int fx = 0; fx < framesW; fx++) {
                if (rnd.nextDouble() > FRAME_ROTATION_CHANCE) {
                    continue;
                }
                int turns = rnd.nextInt(4);
                turn(pixels, width, fx * MAP_EDGE, fy * MAP_EDGE, turns);
            }
        }
    }

    /**
     * Turns one map of the grid by a quarter turn, a half turn or three quarter
     * turns. The turn is the upstream's index shuffle: the new row is the old column
     * and the new column is the old row counted from the other end.
     */
    private static void turn(int[] pixels, int width, int originX, int originY, int turns) {
        int[] tile = new int[MAP_EDGE * MAP_EDGE];
        for (int y = 0; y < MAP_EDGE; y++) {
            System.arraycopy(pixels, (originY + y) * width + originX, tile, y * MAP_EDGE, MAP_EDGE);
        }

        for (int t = 0; t < turns; t++) {
            int[] turned = new int[tile.length];
            for (int y = 0; y < MAP_EDGE; y++) {
                for (int x = 0; x < MAP_EDGE; x++) {
                    turned[y * MAP_EDGE + x] = tile[x * MAP_EDGE + (MAP_EDGE - y - 1)];
                }
            }
            tile = turned;
        }

        for (int y = 0; y < MAP_EDGE; y++) {
            System.arraycopy(tile, y * MAP_EDGE, pixels, (originY + y) * width + originX, MAP_EDGE);
        }
    }

    /* ------------------------------------------------------------------ picture */

    /** The finished picture: every pixel is one slot of the map palette. */
    private static BufferedImage picture(int[] pixels, int width, int height) {
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                image.setRGB(x, y, 0xFF000000 | MapPalette.COLOURS[pixels[y * width + x]]);
            }
        }
        return image;
    }
}
