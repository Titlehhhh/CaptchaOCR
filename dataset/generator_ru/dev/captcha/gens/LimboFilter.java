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
import java.nio.file.Paths;
import java.util.BitSet;
import java.util.HashMap;
import java.util.Random;

import javax.imageio.ImageIO;

/** Clean-room reimplementation of the captchas of Elytrium/LimboFilter (upstream: net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha, AGPL-3.0, nothing carried over). Reconstruction notes live in agents/INDEX.md and the git history. */
public final class LimboFilter {

    private LimboFilter() {
    }

    public static final String PLUGIN = "LimboFilter";

    public static final String SRC = "net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha";

    public static final String SRC_ANSWER =
            "net.elytrium.limbofilter.captcha.CaptchaGenerator#randomAnswer";

    public static final String SRC_SPELLING =
            "net.elytrium.limbofilter.captcha.CaptchaGenerator#spellNumber";

    private static final int MAP_EDGE = 128;

    private record Type(double fontSize, int cellW, int cellH, int offsetX, int offsetY,
                        int spacingX, int spacingY, int outlineX, int outlineY,
                        double rippleW, double rippleH, int curves) {
    }

    private static final Type TYPE_DEFAULT =
            new Type(78.0, 44, 128, 12, 0, -14, 0, -4, 4, 100.0, 10.0, 3);

    private static final Type TYPE_SMALL =
            new Type(36.0, 20, 32, 0, 30, -8, 7, -1, 1, 309.0, 31.0, 3);

    private static final Type TYPE_DIGITS =
            new Type(57.0, 32, 128, 12, 0, -8, 0, -4, 4, 100.0, 10.0, 5);

    private static final double OUTLINE_RATE = 1.25;

    private static final int RIM_RADIUS = 1;

    private static final int CURVE_WIDTH = 2;

    private static final double FRAME_ROTATION_CHANCE = 0.33;

    private static final int NUMBER_LENGTH = 3;

    private static final int NUMBER_MIN = (int) Math.pow(10, NUMBER_LENGTH - 1);

    private static final int SYMBOL_LENGTH = 3;

    private static final double GLYPH_ZOOM = 1.35;

    private static final int CURVE_SLOT = 1;

    private static final Color[] GRADIENT_COLOURS = {
            new Color(0x000000), new Color(0xAA0000), new Color(0x00AA00), new Color(0x0000AA),
            new Color(0xAAAA00), new Color(0xAA00AA), new Color(0x00AAAA)};

    private static final float[] GRADIENT_FRACTIONS = {
            0f, 1f / 6f, 2f / 6f, 3f / 6f, 4f / 6f, 5f / 6f, 1f};

    private static final String[] FACES = {Font.SANS_SERIF, Font.SERIF, Font.MONOSPACED};

    private static final String SYMBOL_PATTERN =
            "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789";

    private static final String NUMBER_ALPHABET =
            "абвгдеёжзийклмнопрстуфхцчшщъыьэюя ";

    private static final String NUMBER_PROMPT = "ВВЕДИТЕ ТОЛЬКО ЦИФРЫ";

    private static final String SYMBOL_PROMPT = "ВВЕДИТЕ СИМВОЛЫ";

    private static final String PUZZLE_PROMPT = "НАПИШИ ЦИФРАМИ";

    private static final String DIGITS_PROMPT = "ВВЕДИТЕ ЦИФРЫ";

    private static final String[] UNIT_WORDS = {
            "", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"};

    private static final String[] TEEN_WORDS = {
            "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
            "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"};

    private static final String[] TEN_WORDS = {
            "", "десять", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
            "семьдесят", "восемьдесят", "девяносто"};

    private static final String[] HUNDRED_WORDS = {
            "", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
            "семьсот", "восемьсот", "девятьсот"};

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

    private record Rendered(BufferedImage image, int[] roi) {
    }

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
            Font face = new Font(FACES[rnd.nextInt(FACES.length)], Font.PLAIN, (int) TYPE_SMALL.fontSize());
            Rendered rendered = paint(1, 1, this.text, NUMBER_ALPHABET, TYPE_SMALL, rnd, face, null, null);
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

        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return SRC + "; " + SRC_ANSWER + "; " + SRC_SPELLING;
        }
    }

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
            Font face = new Font(FACES[rnd.nextInt(FACES.length)], Font.PLAIN, (int) TYPE_DEFAULT.fontSize());
            Rendered rendered = paint(1, 1, this.answer, SYMBOL_PATTERN, TYPE_DEFAULT, rnd, face, null, null);
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

        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return SRC + "; " + SRC_ANSWER;
        }
    }

    public static final class Digits implements Cg {

        private static final String DIGITS_PATTERN = "0123456789";

        private static final String DIGITS_PROMPT = "ВВЕДИТЕ ЦИФРЫ";

        private static final Font FONT = loadFont();

        private static Font loadFont() {
            try {
                return Font.createFont(Font.TRUETYPE_FONT, Paths.get("dataset", "generator_ru", "assets", "limbofilter", "font.ttf").toFile());
            } catch (Exception e) {
                return new Font(Font.SANS_SERIF, Font.PLAIN, 12);
            }
        }

        private final String answer;
        private final BufferedImage image;
        private final int[] roi;

        public Digits() {
            this(new Random());
        }

        public Digits(Random rnd) {
            StringBuilder sb = new StringBuilder(4);
            for (int i = 0; i < 4; i++) {
                sb.append((char) ('0' + rnd.nextInt(10)));
            }
            this.answer = sb.toString();
            int rgb = new int[]{0x00AA00, 0x0000AA, 0xAA00AA, 0x00AAAA}[rnd.nextInt(4)];
            Integer solidSlot = MapPalette.indexOf(0xFF000000 | rgb);
            Integer backplate = 1 + rnd.nextInt(4);
            Rendered rendered = paint(1, 1, this.answer, DIGITS_PATTERN, TYPE_DIGITS, rnd, FONT, solidSlot, backplate);
            this.image = rendered.image();
            this.roi = rendered.roi();
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "digits";
        }

        @Override
        public String answer() {
            return answer;
        }

        @Override
        public String prompt() {
            return DIGITS_PROMPT;
        }

        @Override
        public BufferedImage image() {
            return image;
        }

        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return SRC + "; " + SRC_ANSWER;
        }
    }

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
            Font face = new Font(FACES[rnd.nextInt(FACES.length)], Font.PLAIN, (int) TYPE_SMALL.fontSize());
            this.image = paint(3, 3, this.text, NUMBER_ALPHABET, TYPE_SMALL, rnd, face, null, null).image();
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
            Font face = new Font(FACES[rnd.nextInt(FACES.length)], Font.PLAIN, (int) TYPE_SMALL.fontSize());
            this.image = paint(2, 2, this.text, NUMBER_ALPHABET, TYPE_SMALL, rnd, face, null, null).image();
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

    private static Rendered paint(int framesW, int framesH, String text, String alphabet,
                                  Type type, Random rnd, Font face, Integer solidSlot, Integer backplate) {
        int width = MAP_EDGE * framesW;
        int height = MAP_EDGE * framesH;

        int scaleX = framesW;
        int scaleY = framesH;
        int cellW = type.cellW() * scaleX;
        int cellH = type.cellH() * scaleY;

        java.util.Map<Character, BitSet> glyphs =
                glyphs(face, framesW, framesH, cellW, cellH, alphabet, type, false, true);

        int[] field = solidSlot == null ? gradient(width, height, rnd) : solid(width, height, solidSlot);

        int[] ink = new int[width * height];
        drawText(ink, glyphs, cellW, cellH, text, field, width, height, scaleX, scaleY, type);

        wave(ink, width, height, type, rnd);
        rim(ink, width, height);

        int[] roi = band(ink, width, height);

        int[] pixels = backplate == null ? backdrop(width, height, rnd) : backdropImage(width, height, backplate);
        for (int i = 0; i < ink.length; i++) {
            if (ink[i] != 0) {
                pixels[i] = ink[i];
            }
        }

        curves(pixels, width, height, type.curves(), rnd);

        if (framesW > 1 || framesH > 1) {
            turnFrames(pixels, width, framesW, framesH, rnd);
        }

        return new Rendered(picture(pixels, width, height), roi);
    }

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

    private static final java.util.Map<String, java.util.Map<Character, BitSet>> GLYPH_CACHE = new HashMap<>();

    private static synchronized java.util.Map<Character, BitSet> glyphs(Font face, int scaleX, int scaleY,
                                                                       int cellW, int cellH, String alphabet,
                                                                       Type type, boolean strikethrough, boolean underline) {
        float size = (float) (type.fontSize() * Math.min(scaleX, scaleY));
        String key = face.getName() + "|" + size + "|" + cellW + "x" + cellH + "|" + alphabet
                + "|" + type.outlineX() + "x" + type.outlineY() + "|" + strikethrough + "|" + underline;
        java.util.Map<Character, BitSet> cached = GLYPH_CACHE.get(key);
        if (cached != null) {
            return cached;
        }

        Font font = face.deriveFont(java.util.Map.of(
                TextAttribute.SIZE, size,
                TextAttribute.STRIKETHROUGH, strikethrough,
                TextAttribute.UNDERLINE, underline));
        FontRenderContext ctx = new FontRenderContext(null, true, true);

        java.util.Map<Character, BitSet> sheet = new HashMap<>();
        Random rnd = new Random(0x1F2B3C4DL);
        for (char c : alphabet.toCharArray()) {
            GlyphVector vector = font.createGlyphVector(ctx, String.valueOf(c));

            vector.setGlyphTransform(0, AffineTransform.getRotateInstance(
                    (rnd.nextDouble() - 0.5) * Math.PI / 8));

            Point2D pos = vector.getGlyphPosition(0);
            Rectangle2D box = vector.getGlyphVisualBounds(0).getBounds2D();
            vector.setGlyphPosition(0, new Point2D.Double(pos.getX() - box.getX(), pos.getY()));

            BitSet bits = new BitSet(cellW * cellH);
            Shape outline = vector.getGlyphOutline(0, -(float) cellW * 1.25f, -(float) cellH * 0.3125f);
            stamp(outline, bits, cellW, cellH, 0, 0);

            Stroke stroke = new BasicStroke((float) OUTLINE_RATE);
            stamp(stroke.createStrokedShape(outline), bits, cellW, cellH,
                    type.outlineX() * scaleX, type.outlineY() * scaleY);

            sheet.put(c, bits);
        }

        GLYPH_CACHE.put(key, sheet);
        return sheet;
    }

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

    private static int[] solid(int width, int height, int slot) {
        int[] field = new int[width * height];
        java.util.Arrays.fill(field, slot);
        return field;
    }

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

    private static double fold(double value, int multiples) {
        double bound = multiples * Math.PI;
        double magnitude = Math.abs(value);
        return magnitude - Math.floor(magnitude / bound) * bound;
    }

    private static void rim(int[] ink, int width, int height) {
        for (int x = RIM_RADIUS; x < width - RIM_RADIUS; x++) {
            for (int y = RIM_RADIUS; y < height - RIM_RADIUS; y++) {
                int value = ink[y * width + x];
                if (value == 0) {
                    continue;
                }
                boolean edge = false;
                for (int bx = x - RIM_RADIUS; bx <= x + RIM_RADIUS && !edge; bx++) {
                    for (int by = y - RIM_RADIUS; by <= y + RIM_RADIUS && !edge; by++) {
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

    private static final int[] BACKDROP_SLOTS = {
            32, 33, 35, 12, 13, 84, 87, 116, 118, 119, 8, 24, 100, 104, 60, 40};

    private static int[] backdropImage(int width, int height, int index) {
        try {
            BufferedImage img = ImageIO.read(Paths.get("dataset", "generator_ru", "assets", "limbofilter", "bg" + index + ".png").toFile());
            if (img == null) {
                return backdrop(width, height, new Random());
            }
            BufferedImage scaled = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
            Graphics2D g = scaled.createGraphics();
            g.drawImage(img, 0, 0, width, height, null);
            g.dispose();
            int[] pixels = new int[width * height];
            for (int y = 0; y < height; y++) {
                for (int x = 0; x < width; x++) {
                    pixels[y * width + x] = MapPalette.indexOf(scaled.getRGB(x, y));
                }
            }
            return pixels;
        } catch (Exception e) {
            return backdrop(width, height, new Random());
        }
    }

    private static void curves(int[] pixels, int width, int height, int curves, Random rnd) {
        BufferedImage layer = new BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = layer.createGraphics();
        g.setColor(Color.BLACK);
        for (int i = 0; i < curves; i++) {
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
