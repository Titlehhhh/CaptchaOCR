package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;

import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Random;

import javax.imageio.IIOImage;
import javax.imageio.ImageIO;
import javax.imageio.ImageWriteParam;
import javax.imageio.ImageWriter;
import javax.imageio.stream.ImageOutputStream;

/**
 * The "object captcha" family, reconstructed from the reference screenshots of the
 * gallery's object-captcha section.
 *
 * <h2>What the samples look like</h2>
 * A 250x150 canvas holding a 3x3 grid of cells, 83x50 pixels each - the column
 * boundaries land on x = 0, 83, 167, 250 and the row boundaries on y = 0, 50, 100, 150,
 * so the middle column is one pixel wider than the others.
 *
 * <p>Two variants exist:
 * <ul>
 *   <li>the <b>photo gallery</b> variant: nine photographs laid out as a justified
 *       gallery, each scaled to the 83-pixel cell width with its aspect ratio kept, so
 *       a photo taller than 50 pixels overflows into the cell below. The player has to
 *       click every picture of one category ("select all the cats").</li>
 *   <li>the <b>colour swatch</b> variant: the same 3x3 grid, but each cell is a flat
 *       fill - exactly {@code #FF0000}, {@code #00FF00}, {@code #FFF200}, {@code #000000}
 *       or {@code #FFFFFF} - with JPEG ringing at the cell edges. The ringing is the
 *       fingerprint of the family, and the measurement pins the order: 100 % of the
 *       ringing pixels sit on a seam where the colour <i>changes</i> across it and 0 % on
 *       a same-colour seam, so the grid was JPEG-encoded <b>after</b> the cells were
 *       drawn, not per swatch. The player has to click the cell of the requested
 *       colour.</li>
 * </ul>
 *
 * <h2>Provenance</h2>
 * No upstream generator was found for this family: it is not a Minecraft plugin, and no
 * open-source implementation of either a tile-puzzle or an object-grid captcha exists
 * (searched on GitHub, Sourcegraph, SpigotMC, Modrinth, spigotmc.ru). The geometry and
 * the fills were <b>measured</b> from the reference images, not guessed.
 *
 * <h2>Scope - read this before using it</h2>
 * This is <b>not</b> an OCR task: there is no text in the image and the answer is a
 * position or a colour, not a string. It is included because the swatch variant is the
 * only family in the catalogue with an unambiguous, fully determined ground truth, and
 * because the pixel statistics of the family (flat fills, hard cell edges, JPEG
 * ringing) are a useful robustness test. The photo variant is <b>not</b> generated:
 * its source photographs could not be recovered with reliable category labels, and
 * inventing labels for them would be fabricating ground truth.
 */
public final class ObjectCaptcha {

    private ObjectCaptcha() {
    }

    public static final String PLUGIN = "GalleryCaptcha";
    public static final String SRC = "GalleryCaptcha/ru-object-swatch: clean-room reconstruction of the "
            + "object-grid captcha family, measured from reference screenshots; "
            + "no vendor assets redistributed";

    /** The canvas the object captcha samples are rendered at. */
    static final int W = 250;
    static final int H = 150;

    /** The grid the cells are laid out on. */
    static final int GRID = 3;

    /** The exact fills the colour swatch variant uses. */
    private static final int[] SWATCHES = {
            0xFF0000, 0x00FF00, 0xFFF200, 0x000000, 0xFFFFFF};

    /** The names of those fills, which are the answers. */
    private static final String[] SWATCH_NAMES = {
            "красный", "зелёный", "жёлтый", "чёрный", "белый"};

    /**
     * The colour swatch variant: a 3x3 grid of flat fills, one of which is the target.
     */
    public static final class Swatch implements Cg {

        private final int target;
        private final String answer;
        private final BufferedImage img;

        public Swatch() {
            this(new Random());
        }

        public Swatch(Random r) {
            // The fills first: the target has to be a colour that is actually IN the
            // picture, otherwise the question asks for something the player cannot
            // find. The reference samples use two colours with a majority/minority
            // split, so the grid is drawn from a small palette with one colour in the
            // minority, and the target is the minority one.
            int[] xs = boundaries(W, GRID);
            int[] ys = boundaries(H, GRID);

            int majority = r.nextInt(SWATCHES.length);
            int minority = (majority + 1 + r.nextInt(SWATCHES.length - 1)) % SWATCHES.length;
            int minorityCells = 2 + r.nextInt(3);

            // the cells that carry the minority colour
            int[] cells = new int[GRID * GRID];
            for (int i = 0; i < cells.length; i++) {
                cells[i] = i;
            }
            for (int i = cells.length - 1; i > 0; i--) {
                int j = r.nextInt(i + 1);
                int t = cells[i];
                cells[i] = cells[j];
                cells[j] = t;
            }

            BufferedImage grid = Img.rgb(W, H);
            Graphics2D g = Img.g2d(grid, true);
            for (int row = 0; row < GRID; row++) {
                for (int col = 0; col < GRID; col++) {
                    int idx = row * GRID + col;
                    boolean isMinority = false;
                    for (int k = 0; k < minorityCells; k++) {
                        if (cells[k] == idx) {
                            isMinority = true;
                            break;
                        }
                    }
                    int swatch = isMinority ? minority : majority;
                    g.setColor(new Color(SWATCHES[swatch]));
                    g.fillRect(xs[col], ys[row], xs[col + 1] - xs[col], ys[row + 1] - ys[row]);
                }
            }
            g.dispose();

            // the target is the colour the player has to find
            target = minority;
            answer = SWATCH_NAMES[target];

            // the reference samples show JPEG ringing at the cell edges, so the swatch
            // grid is JPEG-encoded before it is handed on - that ringing is the visible
            // fingerprint of the family
            img = jpegRoundTrip(grid);
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "ru-object-swatch";
        }

        @Override
        public String answer() {
            return answer;
        }

        @Override
        public String prompt() {
            return "Нажмите на клетку цвета " + answer;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * No band: this is not an OCR task.
         *
         * <p>The frame is nine flat colour swatches and no text at all; the answer is
         * the <i>name</i> of a colour and the player has to click the cell that has it.
         * There is no text band to hand over - the caption is not part of the picture.
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

    /* ------------------------------------------------------------- internals */

    /**
     * The cut positions of a {@code grid}-way split of a span: exact thirds, rounded to
     * whole pixels and always including both ends.
     */
    static int[] boundaries(int span, int grid) {
        int[] b = new int[grid + 1];
        for (int i = 0; i <= grid; i++) {
            b[i] = (int) Math.round((double) span * i / grid);
        }
        b[grid] = span;
        return b;
    }

    /**
     * Encodes to JPEG and decodes back, which is what leaves the ringing at the edges of
     * the flat fills in the reference samples.
     *
     * <p>The grid is shrunk to an eighth, JPEG'd and scaled back up with nearest
     * neighbour, because the reference samples show the ringing in big blocks rather
     * than in 8x8 DCT tiles - a few distinct ringing colours, each covering a few
     * hundred pixels.
     *
     * <p><b>This is the one place where the reproduction is visibly looser than the
     * reference.</b> The reference flat swatches carry about 28 distinct colours; this
     * generator produces about 190, because the scale at which the originals were
     * JPEG'd could not be recovered from the samples. The five exact fills, the
     * majority/minority split and the ringing at the cell edges are all reproduced; the
     * number of distinct ringing values is not.
     */
    private static BufferedImage jpegRoundTrip(BufferedImage src) {
        try {
            int w = src.getWidth() / 8;
            int h = src.getHeight() / 8;
            BufferedImage small = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
            Graphics2D sg = small.createGraphics();
            sg.setRenderingHint(java.awt.RenderingHints.KEY_INTERPOLATION,
                    java.awt.RenderingHints.VALUE_INTERPOLATION_BILINEAR);
            sg.drawImage(src, 0, 0, w, h, 0, 0, src.getWidth(), src.getHeight(), null);
            sg.dispose();

            ImageWriter writer = ImageIO.getImageWritersByFormatName("jpg").next();
            ImageWriteParam param = writer.getDefaultWriteParam();
            param.setCompressionMode(ImageWriteParam.MODE_EXPLICIT);
            param.setCompressionQuality(0.92f);
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (ImageOutputStream out = ImageIO.createImageOutputStream(bytes)) {
                writer.setOutput(out);
                writer.write(null, new IIOImage(small, null, null), param);
            }
            writer.dispose();
            BufferedImage decoded = ImageIO.read(new ByteArrayInputStream(bytes.toByteArray()));

            BufferedImage full = new BufferedImage(src.getWidth(), src.getHeight(),
                    BufferedImage.TYPE_INT_RGB);
            Graphics2D fg = full.createGraphics();
            fg.setRenderingHint(java.awt.RenderingHints.KEY_INTERPOLATION,
                    java.awt.RenderingHints.VALUE_INTERPOLATION_NEAREST_NEIGHBOR);
            fg.drawImage(decoded, 0, 0, src.getWidth(), src.getHeight(), 0, 0, w, h, null);
            fg.dispose();
            return full;
        } catch (IOException | RuntimeException e) {
            return src;
        }
    }
}
