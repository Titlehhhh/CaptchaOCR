package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;

import java.awt.AlphaComposite;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.GradientPaint;
import java.awt.Graphics2D;
import java.awt.GraphicsEnvironment;
import java.awt.MultipleGradientPaint;
import java.awt.Paint;
import java.awt.RadialGradientPaint;
import java.awt.RenderingHints;
import java.awt.Shape;
import java.awt.font.FontRenderContext;
import java.awt.font.GlyphVector;
import java.awt.font.TextLayout;
import java.awt.geom.AffineTransform;
import java.awt.geom.CubicCurve2D;
import java.awt.geom.QuadCurve2D;
import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;

/**
 * Clean-room reimplementation of the three map-captcha styles of <b>jonesdevelopment/sonar</b>.
 *
 * <p>Sonar draws every challenge into a 128x128 image which is then shipped to the client
 * as a Minecraft map item. Three styles exist, selected by {@code verification.checks.
 * map-captcha.style}: {@code modern} (the default - oversized swashy glyphs over a fractal
 * noise plate), {@code legacy} (monospaced glyphs on an underwater-caustics plate, then
 * four per-pixel filters over the text layer) and {@code complex} (an auto-fitted technical
 * font with noise lines and dots).
 *
 * <pre>
 *   xyz.jonesdev.sonar.captcha.StandardCaptchaGenerator#createImage
 *   xyz.jonesdev.sonar.captcha.complex.ComplexCaptchaGenerator#createImage
 *   xyz.jonesdev.sonar.captcha.legacy.LegacyCaptchaGenerator#createImage
 *   xyz.jonesdev.sonar.common.protocol.CaptchaPreparer#prepare   (answer alphabet + length)
 *   xyz.jonesdev.sonar.common.resources.assets.config.en.yml     (map-captcha settings)
 * </pre>
 *
 * <p>Everything here is written from scratch: no upstream code, no comments and no
 * identifiers are carried over. The per-pixel image filters the plugin borrows from a
 * third-party library are re-derived here as well.
 */
public final class Sonar {

    public static final String PLUGIN = "jonesdevelopment/sonar";

    /** Default {@code verification.checks.map-captcha.alphabet}: lowercase only, with
     *  the letters that look like digits or like each other left out. */
    private static final String ALPHABET = "abcdefhjkmnoprstuxyz";

    /** Every Sonar map is square and exactly this size. */
    private static final int SIZE = 128;

    /**
     * {@code captcha.enter} from {@code assets/messages/en.yml}, with that file's own
     * {@code <prefix>} ({@code <b><yellow>Sonar</b> <gray>» <white>}) and {@code <green>}
     * placeholders resolved. Sonar styles its messages with MiniMessage tags rather than
     * section-sign codes, so there is no colour code left for {@code McUi.strip} to drop.
     */
    private static final String INSTRUCTION =
            "Sonar » Please enter the text in chat that is displayed on the map.";

    private Sonar() {
    }

    /** CaptchaPreparer.prepare(): {@code 3 + random(2)} characters from the alphabet. */
    private static char[] newAnswer(Random r) {
        char[] a = new char[3 + r.nextInt(2)];
        for (int i = 0; i < a.length; i++) {
            a[i] = ALPHABET.charAt(r.nextInt(ALPHABET.length()));
        }
        return a;
    }

    /* ================================================================ STANDARD */

    /**
     * The default ("modern") style. The plate is a fractal-brownian-motion texture pushed
     * through a black-to-white ramp; the glyphs are filled with a random four-stop radial
     * gradient anchored in the corner; three cubic Beziers are stroked over them, and
     * every pixel of the finished frame is then offset by gaussian noise.
     */
    public static final class Standard implements Cg {

        private static final String SRC =
                "xyz.jonesdev.sonar.captcha.StandardCaptchaGenerator#createImage";

        /** The decorative typeface is held at this nominal point size. */
        private static final int TYPEWRITER_SIZE = 25;
        private static final String TYPEWRITER_FILE = "Kingthings_Trypewriter_2.ttf";

        /** Four gradient stops, evenly spread over the gradient's radius. */
        private static final int GRADIENT_STOPS = 4;
        /** How many Bezier strokes are overlaid on the finished glyphs. */
        private static final int CURVE_COUNT = 3;

        private final String answer;
        private final BufferedImage image;

        public Standard() {
            Random r = new Random();
            answer = new String(newAnswer(r));
            image = render(answer.toCharArray(), r);
        }

        static BufferedImage render(char[] answer, Random r) {
            BufferedImage img = new BufferedImage(SIZE, SIZE, BufferedImage.TYPE_3BYTE_BGR);
            fractalTexture(img, 0.6f, 15f);

            Graphics2D g = img.createGraphics();
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g.setPaint(paintFill(r));
            glyphs(g, answer, r);
            beziers(g, CURVE_COUNT, r);
            grain(img, 1.0f, 20f, r);
            g.dispose();
            return img;
        }

        /**
         * Four saturated colours at 0.9-1.0 brightness, arranged as a reflected radial
         * gradient anchored in the top-left corner with a radius of one image width - so
         * the colours sweep across the frame and fold back on themselves.
         */
        private static Paint paintFill(Random r) {
            Color[] colors = new Color[GRADIENT_STOPS];
            float[] stops = new float[GRADIENT_STOPS];
            for (int i = 0; i < GRADIENT_STOPS; i++) {
                float brightness = 0.9f + r.nextFloat() * 0.1f;
                colors[i] = Color.getHSBColor(r.nextFloat(), brightness * 0.8f, brightness);
                stops[i] = (float) i / (GRADIENT_STOPS - 1);
            }
            return new RadialGradientPaint(0f, 0f, SIZE, stops, colors,
                    MultipleGradientPaint.CycleMethod.REFLECT);
        }

        /**
         * Lays the characters out along one baseline. Each outline is sheared by an amount
         * derived from its own pen position and then uniformly scaled, so the answer fills
         * the frame; the zoom shrinks as the answer gets longer and the baseline wanders a
         * little after every glyph.
         */
        private static void glyphs(Graphics2D g, char[] answer, Random r) {
            FontRenderContext frc = g.getFontRenderContext();
            Font face = typeface();

            GlyphVector[] outlines = new GlyphVector[answer.length];
            for (int i = 0; i < answer.length; i++) {
                outlines[i] = face.createGlyphVector(frc, String.valueOf(answer[i]));
            }

            double zoom = 5 - Math.min(answer.length, 5) * 0.65;
            double run = 0;
            for (GlyphVector gv : outlines) {
                run += gv.getLogicalBounds().getWidth() * zoom - 1;
            }
            double penX = Math.max(Math.min(SIZE / 2.0 - run / 2.0, run), 0);
            double penY = (SIZE + TYPEWRITER_SIZE / 2.0) / 2.0 + zoom;

            for (GlyphVector gv : outlines) {
                AffineTransform t = AffineTransform.getTranslateInstance(penX, penY);
                double slant = Math.sin(penX + penY) / 6;
                t.shear(slant, slant);
                t.scale(zoom, zoom);
                Shape outline = t.createTransformedShape(gv.getOutline());
                g.fill(outline);

                // Roughly one glyph in four also gets a thickened, nudged copy of its own
                // outline filled behind it, fattening the stroke locally.
                if (r.nextFloat() < 0.25f) {
                    float nudge = 1.25f + r.nextFloat();
                    Shape fat = new BasicStroke(1f + r.nextFloat()).createStrokedShape(outline);
                    g.fill(AffineTransform.getTranslateInstance(nudge, nudge)
                            .createTransformedShape(fat));
                }

                penX += gv.getVisualBounds().getWidth() * zoom + 2;
                penY += -10 + r.nextFloat() * 20;
            }
        }

        /**
         * Long cubic Beziers across the frame. Each is a chord of length one image width
         * whose control points pull it towards and away from its midpoint, so it reads as
         * a shallow S rather than a straight line.
         */
        private static void beziers(Graphics2D g, int amount, Random r) {
            g.setStroke(new BasicStroke(1 + r.nextFloat()));
            float half = SIZE / 2f;
            for (int i = 0; i < amount; i++) {
                float cx = SIZE * r.nextFloat();
                float cy = SIZE * r.nextFloat();
                float angle = 6.2831855f * (r.nextFloat() - 0.5f);
                float sin = (float) Math.sin(angle) * half;
                float cos = (float) Math.cos(angle) * half;
                g.draw(new CubicCurve2D.Float(
                        cx - cos, cy - sin,
                        cx + sin / 2, cy - cos / 2,
                        cx - sin / 2, cy + cos / 2,
                        cx + cos, cy + sin));
            }
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "standard";
        }

        @Override
        public String answer() {
            return answer;
        }

        /** A Sonar map carries no text of its own - this is the whole challenge. */
        @Override
        public String prompt() {
            return INSTRUCTION;
        }

        @Override
        public BufferedImage image() {
            return image;
        }

        /**
         * No band: the answer fills the frame.
         *
         * <p>The glyphs are scaled up until the answer spans the whole 128x128 plate -
         * the zoom shrinks as the answer gets longer - so there is no smaller box that
         * holds them, and the plate carries no other text.
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

    /* ================================================================ COMPLEX */

    /**
     * The experimental ("complex") style. The first face is measured at a huge point size
     * and scaled down until the answer exactly fills the padded box; then every character
     * is drawn in a randomly chosen face, rotated about its own centre, filled with a short
     * radial gradient and dropped a little lower each time. Eight noise lines and a hundred
     * dots are scattered over the result.
     */
    public static final class Complex implements Cg {

        private static final String SRC =
                "xyz.jonesdev.sonar.captcha.complex.ComplexCaptchaGenerator#createImage";

        private static final int PADDING = 12;
        private static final double MAX_ROTATION = Math.toRadians(15);
        private static final int LINE_COUNT = 8;
        private static final int DOT_COUNT = 100;
        /** Text channels are capped so the answer stays dark against the white box. */
        private static final int MAX_TEXT_CHANNEL = 150;
        private static final int TEXT_ALPHA = 220;
        /** Interference is capped from below so it never hides the answer. */
        private static final int MIN_NOISE_CHANNEL = 100;
        private static final int MAX_NOISE_ALPHA = 200;
        /** The point size the faces are measured at before the answer is scaled to fit. */
        private static final float MEASURE_SIZE = 100f;

        /**
         * Upstream draws with two hand-made dot-matrix faces ("dotness.ttf" by
         * bythebutterfly.com and an unattributed "DotMatrix.ttf"). Neither carries a
         * licence that allows this project to ship them, so two close system monospaces
         * stand in; everything else about the layout is unchanged.
         */
        private static final String[] FACES = {"Lucida Console", "Courier New"};

        private final String answer;
        private final BufferedImage image;

        public Complex() {
            Random r = new Random();
            answer = new String(newAnswer(r));
            image = render(answer.toCharArray(), r);
        }

        static BufferedImage render(char[] answer, Random r) {
            BufferedImage img = new BufferedImage(SIZE, SIZE, BufferedImage.TYPE_3BYTE_BGR);
            Graphics2D g = img.createGraphics();
            g.setBackground(Color.WHITE);
            g.clearRect(0, 0, img.getWidth(), img.getHeight());

            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING,
                    RenderingHints.VALUE_TEXT_ANTIALIAS_ON);

            FontRenderContext frc = g.getFontRenderContext();
            String text = new String(answer);
            double boxWidth = SIZE - 2D * PADDING;
            double boxHeight = SIZE - 2D * PADDING;

            // Measure with the first face at a huge size, then shrink until the whole
            // answer fits the padded box in both directions at once.
            float size = 24f;
            Rectangle2D trial = Img.font(FACES[0], Font.PLAIN, Math.round(MEASURE_SIZE))
                    .getStringBounds(text, frc);
            if (trial.getWidth() > 0 && trial.getHeight() > 0) {
                double byWidth = boxWidth / trial.getWidth();
                double byHeight = boxHeight / trial.getHeight();
                size = (float) (MEASURE_SIZE * Math.min(byWidth, byHeight));
            }
            if (size < 1f) {
                size = 1f;
            }

            g.setFont(Img.font(FACES[0], Font.PLAIN, Math.round(size)));
            Rectangle2D run = g.getFont().getStringBounds(text, frc);
            double penX = (SIZE - run.getWidth()) / 2D;
            double baseline = SIZE / 2D - run.getHeight() / 2D - run.getY();
            double penY = baseline;

            for (char c : answer) {
                String character = String.valueOf(c);
                Font face = Img.font(FACES[r.nextInt(FACES.length)], Font.PLAIN, Math.round(size));
                g.setFont(face);
                Rectangle2D box = face.getStringBounds(character, frc);
                double w = box.getWidth();
                double h = box.getHeight();
                double cx = penX + w / 2D;
                double cy = baseline + box.getY() + h / 2D;

                g.setPaint(charGradient(penX, penY, w, r));
                AffineTransform saved = g.getTransform();
                g.rotate(r.nextDouble() * 2 * MAX_ROTATION - MAX_ROTATION, cx, cy);
                Shape outline = new TextLayout(character, face, frc)
                        .getOutline(AffineTransform.getTranslateInstance(penX, penY));
                g.fill(outline);
                g.setTransform(saved);

                penX += w;
                penY += r.nextDouble(h / 4) - h / 8;
            }

            noiseLines(g, r);
            noiseDots(g, r);
            g.dispose();
            return img;
        }

        /** Two or three dark colours around one character, blended radially. */
        private static Paint charGradient(double x, double y, double w, Random r) {
            int n = 2 + r.nextInt(2);
            Color[] colors = new Color[n];
            float[] stops = new float[n];
            for (int i = 0; i < n; i++) {
                int rr = Math.min(r.nextInt(256), MAX_TEXT_CHANNEL);
                int gg = Math.min(r.nextInt(256), MAX_TEXT_CHANNEL);
                int bb = Math.min(r.nextInt(256), MAX_TEXT_CHANNEL);
                colors[i] = new Color(rr, gg, bb, TEXT_ALPHA);
                stops[i] = i / (float) n;
            }
            return new RadialGradientPaint((float) x, (float) y, (float) w, stops, colors,
                    MultipleGradientPaint.CycleMethod.REFLECT);
        }

        /** Eight long lines, half of them bowed into a quadratic curve. */
        private static void noiseLines(Graphics2D g, Random r) {
            for (int i = 0; i < LINE_COUNT; i++) {
                g.setColor(noiseColor(r));
                g.setStroke(new BasicStroke(1f + r.nextFloat() * 2f,
                        BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
                if (r.nextBoolean()) {
                    g.draw(new QuadCurve2D.Float(
                            r.nextInt(SIZE), r.nextInt(SIZE),
                            r.nextInt(SIZE), r.nextInt(SIZE),
                            r.nextInt(SIZE), r.nextInt(SIZE)));
                } else {
                    g.drawLine(r.nextInt(SIZE), r.nextInt(SIZE),
                            r.nextInt(SIZE), r.nextInt(SIZE));
                }
            }
        }

        /** A hundred small filled discs scattered over the frame. */
        private static void noiseDots(Graphics2D g, Random r) {
            for (int i = 0; i < DOT_COUNT; i++) {
                g.setColor(noiseColor(r));
                int radius = 1 + r.nextInt(5);
                g.fillOval(r.nextInt(SIZE), r.nextInt(SIZE), radius, radius);
            }
        }

        /** Light channels, translucent alpha: the interference stays behind the answer. */
        private static Color noiseColor(Random r) {
            int rr = Math.max(r.nextInt(256), MIN_NOISE_CHANNEL);
            int gg = Math.max(r.nextInt(256), MIN_NOISE_CHANNEL);
            int bb = Math.max(r.nextInt(256), MIN_NOISE_CHANNEL);
            int a = Math.max(Math.min(r.nextInt(256), MAX_NOISE_ALPHA), MIN_NOISE_CHANNEL);
            return new Color(rr, gg, bb, a);
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "complex";
        }

        @Override
        public String answer() {
            return answer;
        }

        /** A Sonar map carries no text of its own - this is the whole challenge. */
        @Override
        public String prompt() {
            return INSTRUCTION;
        }

        @Override
        public BufferedImage image() {
            return image;
        }

        /**
         * No band: the answer fills the frame.
         *
         * <p>The face is measured at a huge point size and scaled down until the answer
         * exactly fills the padded box, so the text covers nearly the whole 128x128
         * plate and the noise is scattered over the same area. There is no smaller band
         * that holds the answer alone.
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

    /* ================================================================= LEGACY */

    /**
     * The old ("legacy") design. Monospaced glyphs are drawn into a transparent layer with
     * a bright two-stop gradient, then embossed, smeared, rippled and scratched before
     * being composited over an underwater-caustics plate.
     */
    public static final class Legacy implements Cg {

        private static final String SRC =
                "xyz.jonesdev.sonar.captcha.legacy.LegacyCaptchaGenerator#createImage";

        private static final int SCRATCH_COUNT = 4;
        private static final float TEXT_SQUASH = 1.25f;

        /**
         * Upstream picks the ripple amplitude in a static initialiser, so one server
         * process ripples every legacy captcha in exactly the same way.
         */
        private static final float RIPPLE_AMPLITUDE = rippleAmplitude();

        private final String answer;
        private final BufferedImage image;

        public Legacy() {
            Random r = new Random();
            answer = new String(newAnswer(r));
            image = render(answer.toCharArray(), r);
        }

        static BufferedImage render(char[] answer, Random r) {
            GradientPaint gradient = gradientPaint(r);
            BufferedImage text = new BufferedImage(SIZE, SIZE, BufferedImage.TYPE_INT_ARGB);
            Graphics2D g = text.createGraphics();
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            drawText(g, g.getFontRenderContext(), answer, gradient, r);
            g.dispose();

            emboss(text);
            smear(text);
            ripple(text, RIPPLE_AMPLITUDE);
            scratch(text, SCRATCH_COUNT, r);

            BufferedImage merged = new BufferedImage(SIZE, SIZE, BufferedImage.TYPE_3BYTE_BGR);
            Graphics2D mg = merged.createGraphics();
            mg.drawImage(background(r), 0, 0, null);
            mg.setComposite(AlphaComposite.SrcOver);
            mg.drawImage(text, 0, 0, null);
            mg.dispose();

            grain(merged, 1.0f, 7f, r);
            return merged;
        }

        /** A random bright hue paired with a half-brightness version of another. */
        private static GradientPaint gradientPaint(Random r) {
            Color from = Color.getHSBColor(r.nextFloat(), 1f, 1f);
            Color to = Color.getHSBColor(r.nextFloat(), 1f, 0.5f);
            return new GradientPaint(0, 0, from, SIZE, SIZE, to);
        }

        /**
         * One glyph at a time. The rotation accumulates, so the answer curves away from the
         * baseline over its length, and each glyph is stretched vertically a quarter again
         * to fill the frame.
         */
        private static void drawText(Graphics2D g, FontRenderContext frc, char[] answer,
                                     GradientPaint gradient, Random r) {
            int size = 62 - answer.length * 2;
            Font face = Img.font("Monospaced", Font.PLAIN, size);

            double run = face.getStringBounds(answer, 0, answer.length, frc).getWidth();
            int penX = (int) ((SIZE - run) / 2D + run / (answer.length * 2.5D));
            int penY = (int) ((SIZE + size / 2D) / 2D);
            double rotation = 0;

            g.setPaint(gradient);
            for (char c : answer) {
                GlyphVector gv = face.createGlyphVector(frc, String.valueOf(c));
                int advance = (int) gv.getVisualBounds().getWidth();

                AffineTransform t = AffineTransform.getTranslateInstance(penX, penY);
                rotation += Math.toRadians(6 - r.nextInt(12));
                t.rotate(rotation);
                t.scale(1, TEXT_SQUASH);
                Shape outline = t.createTransformedShape(gv.getOutline());
                g.fill(outline);

                // A hairline copy of the same outline shifted by about a pixel fattens
                // every stroke and drops a soft shadow around the letter.
                Shape halo = new BasicStroke().createStrokedShape(outline);
                g.fill(AffineTransform.getTranslateInstance(
                        0.5 + r.nextDouble(), 0.5 + r.nextDouble())
                        .createTransformedShape(halo));

                penX += advance + 2;
            }
        }

        /** The plate under the legacy text: a fixed pool-blue texture, saturated and sharpened. */
        private static BufferedImage background(Random r) {
            BufferedImage plate = caustics(SIZE, SIZE);
            saturate(plate, 0.4f + r.nextFloat() * 0.2f);
            unsharp(plate, 2, 0.5f, 1);
            return plate;
        }

        private static float rippleAmplitude() {
            float a = 10 - new Random().nextInt(20);
            if (Math.abs(a) < 5) {
                a = a >= 0 ? 5 : -5;
            }
            return a;
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "legacy";
        }

        @Override
        public String answer() {
            return answer;
        }

        /** A Sonar map carries no text of its own - this is the whole challenge. */
        @Override
        public String prompt() {
            return INSTRUCTION;
        }

        @Override
        public BufferedImage image() {
            return image;
        }

        /**
         * No band: the answer fills the frame.
         *
         * <p>The legacy style sets the answer in a 56 to 62pt face, squashes it by a
         * quarter and turns it as it goes, so the glyphs cover most of the 128x128
         * plate - and the plate carries no other text.
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

    /* ================================================================== FONTS */

    private static Font typeface;

    /**
     * The decorative face the modern style is drawn in. Its author publishes the whole
     * Kingthings family free for any purpose provided the .ttf is shipped unmodified, so a
     * copy lives in {@code src/main/resources/fonts}. If it cannot be found the renderer
     * degrades to a serif rather than failing.
     */
    private static synchronized Font typeface() {
        if (typeface == null) {
            typeface = loadTrueType(Standard.TYPEWRITER_FILE, Standard.TYPEWRITER_SIZE);
        }
        return typeface;
    }

    private static Font loadTrueType(String file, int size) {
        try (InputStream in = openFont(file)) {
            if (in != null) {
                Font face = Font.createFont(Font.TRUETYPE_FONT, in).deriveFont(Font.PLAIN, size);
                try {
                    GraphicsEnvironment.getLocalGraphicsEnvironment().registerFont(face);
                } catch (RuntimeException ignored) {
                    // already registered, or no font registry in this environment
                }
                return face;
            }
        } catch (Exception ignored) {
            // fall through to the substitute below
        }
        return Img.font("Serif", Font.PLAIN, size);
    }

    /**
     * Looks for the font on the classpath first, then in {@code src/main/resources} beside
     * the working directory and beside the compiled classes - so the dataset can be
     * generated from a plain checkout without a build step having to copy resources.
     */
    private static InputStream openFont(String file) throws Exception {
        InputStream in = Sonar.class.getResourceAsStream("/fonts/" + file);
        if (in != null) {
            return in;
        }
        List<File> candidates = new ArrayList<>();
        candidates.add(new File("src/main/resources/fonts", file));
        for (File dir = new File(".").getAbsoluteFile(); dir != null; dir = dir.getParentFile()) {
            candidates.add(new File(new File(dir, "src/main/resources/fonts"), file));
        }
        String where = Sonar.class.getProtectionDomain() == null
                || Sonar.class.getProtectionDomain().getCodeSource() == null
                ? null : Sonar.class.getProtectionDomain().getCodeSource().getLocation().getPath();
        if (where != null) {
            for (File dir = new File(where).getAbsoluteFile(); dir != null; dir = dir.getParentFile()) {
                candidates.add(new File(new File(dir, "src/main/resources/fonts"), file));
            }
        }
        for (File f : candidates) {
            if (f.isFile()) {
                return new FileInputStream(f);
            }
        }
        return null;
    }

    /* ============================================================ PIXEL TOOLBOX */

    private static int clamp(int v, int lo, int hi) {
        return v < lo ? lo : (v > hi ? hi : v);
    }

    private static float clamp(float v, float lo, float hi) {
        return v < lo ? lo : (v > hi ? hi : v);
    }

    /** Linear interpolation towards {@code to}, in every channel including alpha. */
    private static int blend(int from, int to, float t) {
        return (lerp8(from >>> 24, to >>> 24, t) << 24)
                | (lerp8(from >> 16 & 0xFF, to >> 16 & 0xFF, t) << 16)
                | (lerp8(from >> 8 & 0xFF, to >> 8 & 0xFF, t) << 8)
                | lerp8(from & 0xFF, to & 0xFF, t);
    }

    private static int lerp8(int a, int b, float t) {
        return clamp((int) (a + t * (b - a)), 0, 0xFF);
    }

    private static float lerp(float t, float a, float b) {
        return a + t * (b - a);
    }

    /** The usual 0..1 ease, used by the noise colormap ramp. */
    private static float smoothStep(float edge0, float edge1, float x) {
        float t = clamp((x - edge0) / (edge1 - edge0), 0f, 1f);
        return t * t * (3f - 2f * t);
    }

    private static int fade(int channel, float amount, Random r) {
        return clamp(channel + (int) (r.nextGaussian() * amount), 0, 0xFF);
    }

    /**
     * Adds a gaussian offset to a random subset of the pixels. Both Sonar styles run this
     * with density 1.0, i.e. over the whole frame - it is what gives the modern captcha its
     * heavy grain and the legacy one its light dusting.
     */
    private static void grain(BufferedImage img, float density, float amount, Random r) {
        int w = img.getWidth();
        int h = img.getHeight();
        int[] row = new int[w];
        for (int y = 0; y < h; y++) {
            img.getRGB(0, y, w, 1, row, 0, w);
            for (int x = 0; x < w; x++) {
                if (r.nextFloat() <= density) {
                    int rgb = row[x];
                    row[x] = (fade((rgb >> 16) & 0xFF, amount, r) << 16)
                            | (fade((rgb >> 8) & 0xFF, amount, r) << 8)
                            | fade(rgb & 0xFF, amount, r);
                }
            }
            img.setRGB(0, y, w, 1, row, 0, w);
        }
    }

    /* ------------------------------------------------------------ fractal noise */

    /**
     * Gradient ("Perlin") noise over a shuffled table of unit vectors. The table is built
     * once per process, which is what the upstream library does too - so every captcha a
     * server hands out shares the same background texture.
     */
    private static final class Noise {

        private static final int LATTICE = 256;
        private static final int[] SHUFFLE = new int[LATTICE * 2];
        private static final float[] GX = new float[LATTICE * 2];
        private static final float[] GY = new float[LATTICE * 2];

        static {
            Random r = new Random();
            for (int i = 0; i < LATTICE; i++) {
                SHUFFLE[i] = i;
                double a = r.nextDouble() * Math.PI * 2;
                GX[i] = (float) Math.cos(a);
                GY[i] = (float) Math.sin(a);
            }
            for (int i = LATTICE - 1; i > 0; i--) {
                int j = r.nextInt(i + 1);
                int t = SHUFFLE[i];
                SHUFFLE[i] = SHUFFLE[j];
                SHUFFLE[j] = t;
            }
            System.arraycopy(SHUFFLE, 0, SHUFFLE, LATTICE, LATTICE);
            for (int i = 0; i < LATTICE; i++) {
                GX[i + LATTICE] = GX[i];
                GY[i + LATTICE] = GY[i];
            }
        }

        /** Smoothly interpolated gradient noise, roughly -1..1. */
        static float at(float x, float y) {
            int xi = (int) Math.floor(x);
            int yi = (int) Math.floor(y);
            float dx = x - xi;
            float dy = y - yi;
            float u = ease(dx);
            float v = ease(dy);
            int x0 = xi & 255;
            int x1 = (x0 + 1) & 255;
            int y0 = yi & 255;
            int y1 = (y0 + 1) & 255;
            float top = lerp(u, dot(x0, y0, dx, dy), dot(x1, y0, dx - 1, dy));
            float bottom = lerp(u, dot(x0, y1, dx, dy - 1), dot(x1, y1, dx - 1, dy - 1));
            return lerp(v, top, bottom);
        }

        private static float dot(int gx, int gy, float dx, float dy) {
            int g = SHUFFLE[SHUFFLE[gx] + gy];
            return GX[g] * dx + GY[g] * dy;
        }

        private static float ease(float t) {
            return t * t * (3 - 2 * t);
        }
    }

    /** Four octaves of {@link Noise}: the amplitude halves and the frequency doubles each time. */
    private static float fractal(float x, float y) {
        // The offset decorrelates neighbouring tiles of the noise lattice.
        float px = x + 371;
        float py = y + 529;
        float amp = 1f;
        float sum = 0f;
        for (int i = 0; i < 4; i++) {
            sum += Noise.at(px, py) * amp;
            px *= 2;
            py *= 2;
            amp *= 0.5f;
        }
        return sum;
    }

    /**
     * Replaces the frame with a cloudy greyscale texture. The four-octave noise field is
     * first stretched across 0..1 by measuring its own extremes over a wide sample grid,
     * then scaled by {@code amount} and pushed through a black-to-white ramp that stays
     * black for the lowest seventh and reaches white at 0.85.
     */
    private static void fractalTexture(BufferedImage img, float amount, float scale) {
        float lo = 0;
        float hi = 0;
        for (float y = -100f; y < 100f; y += 10.35173f) {
            for (float x = -100f; x < 100f; x += 10.77139f) {
                float n = fractal(x / scale, y / scale);
                lo = Math.min(lo, n);
                hi = Math.max(hi, n);
            }
        }
        float span = hi - lo;
        int w = img.getWidth();
        int h = img.getHeight();
        int[] row = new int[w];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int grey = ramp(((fractal(x / scale, y / scale) - lo) / span) * amount);
                row[x] = (grey << 16) | (grey << 8) | grey;
            }
            img.setRGB(0, y, w, 1, row, 0, w);
        }
    }

    /** Black-to-white colormap lookup: index the ramp, then ease across its middle. */
    private static int ramp(float t) {
        int i = clamp((int) (t * 255f), 0, 255);
        return clamp((int) (255 * smoothStep(0.15f, 0.85f, i / 255f)), 0, 255);
    }

    /**
     * The plate under the legacy text: a pool-blue sheet brightened wherever the gradient
     * of a smooth noise field converges, which is how caustic light-lines form. The sample
     * offsets use a fixed seed, so this is one constant texture rather than a fresh plate
     * per captcha.
     */
    private static BufferedImage caustics(int w, int h) {
        int[] px = new int[w * h];
        Arrays.fill(px, 0xff799fff);

        Random r = new Random(0);
        float step = 1f / 32f;
        float probe = 0.95f;
        float focus = 1.1f;
        int lift = 10 / 2;

        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                for (int s = 0; s < 2; s++) {
                    float sx = x + r.nextFloat();
                    float sy = y + r.nextFloat();
                    float nx = sx * step;
                    float ny = sy * step;
                    float dx = field(nx - probe, ny) - field(nx + probe, ny);
                    float dy = field(nx, ny + probe) - field(nx, ny - probe);

                    float tx = sx + 32 * focus * dx;
                    float ty = sy + 32 * focus * dy;
                    if (tx < 0 || tx >= w - 1 || ty < 0 || ty >= h - 1) {
                        continue;
                    }
                    int at = (int) ty * w + (int) tx;
                    int rgb = px[at];
                    px[at] = 0xff000000
                            | (Math.min((rgb >> 16 & 0xFF) + lift, 255) << 16)
                            | (Math.min((rgb >> 8 & 0xFF) + lift, 255) << 8)
                            | Math.min((rgb & 0xFF) + lift, 255);
                }
            }
        }
        BufferedImage img = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
        img.setRGB(0, 0, w, h, px, 0, w);
        return img;
    }

    /** The scalar field whose gradient steers the caustics. */
    private static float field(float x, float y) {
        return Noise.at(0.09983f * x + 371f, y + 529f);
    }

    /** Pushes every channel away from (or towards) its own grey, keeping the luma fixed. */
    private static void saturate(BufferedImage img, float amount) {
        int w = img.getWidth();
        int h = img.getHeight();
        int[] px = new int[w * h];
        img.getRGB(0, 0, w, h, px, 0, w);
        for (int i = 0; i < px.length; i++) {
            int r = px[i] >> 16 & 0xFF;
            int g = px[i] >> 8 & 0xFF;
            int b = px[i] & 0xFF;
            int v = (r + g + b) / 3;
            px[i] = 0xff000000
                    | (clamp((int) (v + amount * (r - v)), 0, 255) << 16)
                    | (clamp((int) (v + amount * (g - v)), 0, 255) << 8)
                    | clamp((int) (v + amount * (b - v)), 0, 255);
        }
        img.setRGB(0, 0, w, h, px, 0, w);
    }

    /** Unsharp mask: subtract a small gaussian blur and amplify the difference. */
    private static void unsharp(BufferedImage img, int radius, float amount, int threshold) {
        int w = img.getWidth();
        int h = img.getHeight();
        int[] px = new int[w * h];
        img.getRGB(0, 0, w, h, px, 0, w);
        int[] blur = gaussian(px, w, h, radius);
        float gain = 4 * amount;
        for (int i = 0; i < px.length; i++) {
            int r = px[i] >> 16 & 0xFF;
            int g = px[i] >> 8 & 0xFF;
            int b = px[i] & 0xFF;
            int br = blur[i] >> 16 & 0xFF;
            int bg = blur[i] >> 8 & 0xFF;
            int bb = blur[i] & 0xFF;
            if (Math.abs(r - br) >= threshold) {
                r = clamp((int) ((gain + 1) * (r - br) + br), 0, 255);
            }
            if (Math.abs(g - bg) >= threshold) {
                g = clamp((int) ((gain + 1) * (g - bg) + bg), 0, 255);
            }
            if (Math.abs(b - bb) >= threshold) {
                b = clamp((int) ((gain + 1) * (b - bb) + bb), 0, 255);
            }
            px[i] = 0xff000000 | (r << 16) | (g << 8) | b;
        }
        img.setRGB(0, 0, w, h, px, 0, w);
    }

    /** Separable gaussian blur with clamped edges; the kernel weights sum to one. */
    private static int[] gaussian(int[] px, int w, int h, int radius) {
        float sigma = 1.4f * radius;
        float[] k = new float[2 * radius + 1];
        float sum = 0;
        for (int i = -radius; i <= radius; i++) {
            k[i + radius] = (float) Math.exp(-(i * i) / (2f * sigma * sigma));
            sum += k[i + radius];
        }
        for (int i = 0; i < k.length; i++) {
            k[i] /= sum;
        }

        int[] tmp = new int[px.length];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int r = 0, g = 0, b = 0;
                for (int i = -radius; i <= radius; i++) {
                    int rgb = px[y * w + clamp(x + i, 0, w - 1)];
                    r += k[i + radius] * (rgb >> 16 & 0xFF);
                    g += k[i + radius] * (rgb >> 8 & 0xFF);
                    b += k[i + radius] * (rgb & 0xFF);
                }
                tmp[y * w + x] = 0xff000000 | ((int) r << 16) | ((int) g << 8) | (int) b;
            }
        }
        int[] out = new int[px.length];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int r = 0, g = 0, b = 0;
                for (int i = -radius; i <= radius; i++) {
                    int rgb = tmp[clamp(y + i, 0, h - 1) * w + x];
                    r += k[i + radius] * (rgb >> 16 & 0xFF);
                    g += k[i + radius] * (rgb >> 8 & 0xFF);
                    b += k[i + radius] * (rgb & 0xFF);
                }
                out[y * w + x] = 0xff000000 | ((int) r << 16) | ((int) g << 8) | (int) b;
            }
        }
        return out;
    }

    /* ----------------------------------------------------------- text filters */

    private static int premultiply(int argb) {
        int a = argb >>> 24;
        return (a << 24)
                | (((argb >> 16) & 0xFF) * a / 255 << 16)
                | (((argb >> 8) & 0xFF) * a / 255 << 8)
                | ((argb & 0xFF) * a / 255);
    }

    private static int unpremultiply(int argb) {
        int a = argb >>> 24;
        if (a == 0) {
            return 0;
        }
        return (a << 24)
                | (clamp(((argb >> 16) & 0xFF) * 255 / a, 0, 255) << 16)
                | (clamp(((argb >> 8) & 0xFF) * 255 / a, 0, 255) << 8)
                | clamp((argb & 0xFF) * 255 / a, 0, 255);
    }

    /**
     * A 3x3 directional relief applied to the premultiplied text layer. The kernel sums to
     * one, so flat areas survive untouched while the lit side of every stroke brightens
     * and the shaded side darkens.
     */
    private static void emboss(BufferedImage img) {
        final float[] k = {-1, -1, 0, -1, 1, 1, 0, 1, 1};
        int w = img.getWidth();
        int h = img.getHeight();
        int[] src = new int[w * h];
        int[] dst = new int[w * h];
        img.getRGB(0, 0, w, h, src, 0, w);
        for (int i = 0; i < src.length; i++) {
            src[i] = premultiply(src[i]);
        }
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                float a = 0, r = 0, g = 0, b = 0;
                for (int row = -1; row <= 1; row++) {
                    int sy = clamp(y + row, 0, h - 1) * w;
                    for (int col = -1; col <= 1; col++) {
                        int rgb = src[sy + clamp(x + col, 0, w - 1)];
                        float f = k[(row + 1) * 3 + col + 1];
                        a += f * (rgb >>> 24);
                        r += f * (rgb >> 16 & 0xFF);
                        g += f * (rgb >> 8 & 0xFF);
                        b += f * (rgb & 0xFF);
                    }
                }
                dst[y * w + x] = (clamp((int) (a + 0.5f), 0, 255) << 24)
                        | (clamp((int) (r + 0.5f), 0, 255) << 16)
                        | (clamp((int) (g + 0.5f), 0, 255) << 8)
                        | clamp((int) (b + 0.5f), 0, 255);
            }
        }
        for (int i = 0; i < dst.length; i++) {
            dst[i] = unpremultiply(dst[i]);
        }
        img.setRGB(0, 0, w, h, dst, 0, w);
    }

    /**
     * Scatters small discs that drag a fraction of their source pixel over the destination,
     * softening neighbouring strokes into each other and bleeding a faint halo into the
     * surrounding transparency. The disc positions come off a fixed seed, so every legacy
     * captcha is smeared along the same set of stamps.
     */
    private static void smear(BufferedImage img) {
        final float density = 0.1f;
        final float mix = 0.15f;
        final int radius = 5 + 1;
        final int radiusSq = radius * radius;

        int w = img.getWidth();
        int h = img.getHeight();
        int[] src = new int[w * h];
        int[] dst = new int[w * h];
        img.getRGB(0, 0, w, h, src, 0, w);
        System.arraycopy(src, 0, dst, 0, src.length);

        Random r = new Random(567);
        int stamps = (int) (2 * density * w * h / radius);
        for (int i = 0; i < stamps; i++) {
            int cx = (r.nextInt() & 0x7fffffff) % w;
            int cy = (r.nextInt() & 0x7fffffff) % h;
            int pick = src[cy * w + cx];
            for (int y = cy - radius; y <= cy + radius; y++) {
                if (y < 0 || y >= h) {
                    continue;
                }
                int dy = y - cy;
                for (int x = cx - radius; x <= cx + radius; x++) {
                    int dx = x - cx;
                    if (dx * dx + dy * dy > radiusSq || x < 0 || x >= w) {
                        continue;
                    }
                    int at = y * w + x;
                    dst[at] = blend(dst[at], pick, mix);
                }
            }
        }
        img.setRGB(0, 0, w, h, dst, 0, w);
    }

    /** Displaces every pixel vertically by a sine of its column - a standing wave. */
    private static void ripple(BufferedImage img, float amplitude) {
        int w = img.getWidth();
        int h = img.getHeight();
        int[] src = new int[w * h];
        int[] dst = new int[w * h];
        img.getRGB(0, 0, w, h, src, 0, w);

        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                float fy = y + amplitude * (float) Math.sin(x / 13f);
                int sx = x;
                int sy = (int) Math.floor(fy);
                float wx = 0f;
                float wy = fy - sy;
                dst[y * w + x] = blend4(
                        sample(src, w, h, sx, sy),
                        sample(src, w, h, sx + 1, sy),
                        sample(src, w, h, sx, sy + 1),
                        sample(src, w, h, sx + 1, sy + 1), wx, wy);
            }
        }
        img.setRGB(0, 0, w, h, dst, 0, w);
    }

    /** Off-image samples clamp to the border and lose their alpha. */
    private static int sample(int[] px, int w, int h, int x, int y) {
        if (x < 0 || x >= w || y < 0 || y >= h) {
            return px[clamp(y, 0, h - 1) * w + clamp(x, 0, w - 1)] & 0x00ffffff;
        }
        return px[y * w + x];
    }

    private static int blend4(int nw, int ne, int sw, int se, float x, float y) {
        float top = lerp(x, nw >>> 24, ne >>> 24);
        float bottom = lerp(x, sw >>> 24, se >>> 24);
        int a = clamp((int) lerp(y, top, bottom), 0, 255);
        top = lerp(x, nw >> 16 & 0xFF, ne >> 16 & 0xFF);
        bottom = lerp(x, sw >> 16 & 0xFF, se >> 16 & 0xFF);
        int r = clamp((int) lerp(y, top, bottom), 0, 255);
        top = lerp(x, nw >> 8 & 0xFF, ne >> 8 & 0xFF);
        bottom = lerp(x, sw >> 8 & 0xFF, se >> 8 & 0xFF);
        int g = clamp((int) lerp(y, top, bottom), 0, 255);
        top = lerp(x, nw & 0xFF, ne & 0xFF);
        bottom = lerp(x, sw & 0xFF, se & 0xFF);
        int b = clamp((int) lerp(y, top, bottom), 0, 255);
        return (a << 24) | (r << 16) | (g << 8) | b;
    }

    /**
     * Four full-width strokes drawn straight into the text layer with a gradient paint that
     * fades to fully transparent at the far corner, so the scratches dissolve towards one
     * end instead of stopping abruptly.
     */
    private static void scratch(BufferedImage img, int amount, Random r) {
        Graphics2D g = img.createGraphics();
        Color from = Color.getHSBColor(r.nextFloat(), r.nextFloat(), 1f);
        // The bitwise inverse of an opaque ARGB value read as ARGB is transparent, and
        // that accident is what makes the strokes fade out.
        Color to = new Color(~from.getRGB());
        g.setPaint(new GradientPaint(0, 0, from, img.getWidth(), img.getHeight(), to));

        float half = img.getWidth() * 0.5f;
        for (int i = 0; i < amount; i++) {
            float cx = img.getWidth() * r.nextFloat();
            float cy = img.getHeight() * r.nextFloat();
            float angle = 6.2831855f * (r.nextFloat() - 0.5f);
            float sin = (float) Math.sin(angle) * half;
            float cos = (float) Math.cos(angle) * half;
            g.drawLine((int) (cx - cos), (int) (cy - sin), (int) (cx + cos), (int) (cy + sin));
        }
        g.dispose();
    }
}
