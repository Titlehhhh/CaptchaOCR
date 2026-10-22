package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.Color;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/** Colour-picking inventory captchas shipped as open-source Bukkit plugins. */
public final class GuiPlugins {

    private GuiPlugins() {
    }

    /** Minecraft dyed-glass colours, with the name the plugin derives from the material. */
    static final class Dye {
        final String material;
        final String name;
        final int rgb;

        Dye(String material, String name, int rgb) {
            this.material = material;
            this.name = name;
            this.rgb = rgb;
        }
    }

    static int shade(int rgb, double k) {
        return new Color((int) (Math.min(255, ((rgb >> 16) & 0xFF) * k)),
                (int) (Math.min(255, ((rgb >> 8) & 0xFF) * k)),
                (int) (Math.min(255, (rgb & 0xFF) * k))).getRGB();
    }

    /* ======================================================== Z4OLLIEZ4/reCaptcha */
    /**
     * CaptchasX - "Please select &lt;colour&gt;". 36-slot GUI framed in grey panes, 14 dyed
     * panes, the correct one forced into one of the 14 inner slots. config: captcha-times: 4.
     *
     * <pre>src/main/olliez4/captcha/CaptchaGUI.java#send</pre>
     */
    public static final class CaptchasX implements Cg {
        /** Exactly the colours list from the constructor. */
        static final Dye[] COLOURS = {
                new Dye("WHITE_STAINED_GLASS_PANE", "white", 0xF9FFFE),
                new Dye("ORANGE_STAINED_GLASS_PANE", "orange", 0xF9801D),
                new Dye("MAGENTA_STAINED_GLASS_PANE", "magenta", 0xC74EBD),
                new Dye("LIGHT_BLUE_STAINED_GLASS_PANE", "light blue", 0x3AB3DA),
                new Dye("YELLOW_STAINED_GLASS_PANE", "yellow", 0xFED83D),
                new Dye("LIME_STAINED_GLASS_PANE", "lime", 0x80C71F),
                new Dye("PINK_STAINED_GLASS_PANE", "pink", 0xF38BAA),
                new Dye("CYAN_STAINED_GLASS_PANE", "cyan", 0x169C9C),
                new Dye("PURPLE_STAINED_GLASS_PANE", "purple", 0x8932B8),
                new Dye("BLUE_STAINED_GLASS_PANE", "blue", 0x3C44AA),
                new Dye("BROWN_STAINED_GLASS_PANE", "brown", 0x835432),
                new Dye("GREEN_STAINED_GLASS_PANE", "green", 0x5E7C16),
                new Dye("RED_STAINED_GLASS_PANE", "red", 0xB02E26)};

        private final Random r = new Random();
        private final Dye correct = COLOURS[r.nextInt(COLOURS.length)];
        private final BufferedImage img;
        private final int[] roi;

        public CaptchasX() {
            // 14 fill items land in the only 14 free inner slots, then the correct one is
            // forced onto slot 10+slot or 19+slot with slot in 0..5.
            List<Integer> inner = new ArrayList<>();
            for (int i = 10; i <= 16; i++) {
                inner.add(i);
            }
            for (int i = 19; i <= 25; i++) {
                inner.add(i);
            }
            List<Dye> fills = new ArrayList<>();
            for (int item = 0; item <= 13; item++) {
                fills.add(COLOURS[r.nextInt(COLOURS.length)]);
            }
            int slot = r.nextInt(6);
            int realSlot = r.nextBoolean() ? 10 + slot : 19 + slot;

            String title = "Please select " + correct.name;
            BufferedImage inv = McUi.inventory(9, 4, title);
            Graphics2D g = Img.g2d(inv, true);
            // Border of grey panes: 0-9, 17, 18, 26-35.
            for (int i : new int[]{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35}) {
                McUi.slotItem(g, 9, 4, i, new Color(0x80, 0x80, 0x80), "");
            }
            for (int i = 0; i < fills.size(); i++) {
                McUi.slotItem(g, 9, 4, inner.get(i), new Color(fills.get(i).rgb), "");
            }
            McUi.slotItem(g, 9, 4, realSlot, new Color(correct.rgb), "");
            g.dispose();
            img = inv;
            roi = titleBand(title, correct.name, inv);
        }

        /**
         * The band of the colour name in the title bar of the window.
         *
         * <p>The window carries no other text, and the title is the only place where the
         * answer - the name of the colour to click - is written down. The band is that
         * name, without the "Please select" in front of it.
         *
         * <p>The window is 186px wide and the titles the plugins use are longer than
         * that, so the title is written at the largest size that fits - which is what
         * {@link McUi#titleSize} computes, and the band is measured at that same size.
         */
        private static int[] titleBand(String title, String name, BufferedImage frame) {
            Graphics2D g = TextBand.measure();
            try {
                int size = Math.round(McUi.titleSize(g, title, frame.getWidth()));
                TextBand.Hit hit = TextBand.locate(g, title, name, size);
                if (hit == null) {
                    return null;
                }
                g.setFont(Img.font("Monospaced",
                        hit.bold() ? java.awt.Font.BOLD : java.awt.Font.PLAIN, size));
                FontMetrics fm = g.getFontMetrics();
                return TextBand.fits(
                        TextBand.box(12 + hit.x(), 16, fm.getAscent(), fm.getDescent(),
                                fm.stringWidth(name)),
                        frame.getWidth(), frame.getHeight());
            } finally {
                g.dispose();
            }
        }

        @Override
        public String plugin() {
            return "Z4OLLIEZ4/reCaptcha";
        }

        @Override
        public String id() {
            return "captchasx";
        }

        @Override
        public String answer() {
            return correct.name;
        }

        /** The window title the constructor gives {@code McUi.inventory}, colour-free. */
        @Override
        public String prompt() {
            return McUi.strip("Please select " + correct.name);
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the colour name in the title bar of the window.
         *
         * <p>The window carries no other text; the title is the only place where the
         * answer - the name of the colour to click - is written down.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return "main.olliez4.captcha.CaptchaGUI#send";
        }
    }

    /* ============================================================ Joey61021/captcha */
    /**
     * A 27-slot "Click on the colour X" GUI. The correct pane is placed first, then every
     * other colour is dropped at a random slot, so they can overwrite one another.
     *
     * <pre>com.captcha.plugin.services.CaptchaService#gui</pre>
     */
    public static final class JoeyCaptcha implements Cg {
        static final Dye[] ITEMS = {
                new Dye("ORANGE_STAINED_GLASS_PANE", "Orange", 0xF9801D),
                new Dye("MAGENTA_STAINED_GLASS_PANE", "Pink", 0xC74EBD),
                new Dye("LIGHT_BLUE_STAINED_GLASS_PANE", "Blue", 0x3AB3DA),
                new Dye("YELLOW_STAINED_GLASS_PANE", "Yellow", 0xFED83D),
                new Dye("LIME_STAINED_GLASS_PANE", "Lime", 0x80C71F),
                new Dye("RED_STAINED_GLASS_PANE", "Red", 0xB02E26)};

        private final Random r = new Random();
        private final Dye correct;
        private final BufferedImage img;
        private final int[] roi;

        public JoeyCaptcha() {
            correct = ITEMS[r.nextInt(ITEMS.length)];
            int size = 27;
            // The source overwrites by index, so later writes can clobber earlier ones.
            Integer[] slots = new Integer[size];
            Dye[] items = new Dye[size];
            int correctSlot = r.nextInt(size);
            slots[correctSlot] = correctSlot;
            items[correctSlot] = correct;
            for (int i = 0; i < ITEMS.length; i++) {
                Dye c = ITEMS[i];
                if (!c.material.equals(correct.material)) {
                    int s = r.nextInt(size);
                    slots[s] = s;
                    items[s] = c;
                }
            }

            String title = "Click on the color " + correct.name;
            BufferedImage inv = McUi.inventory(9, 3, title);
            Graphics2D g = Img.g2d(inv, true);
            for (int i = 0; i < size; i++) {
                if (slots[i] != null) {
                    McUi.slotItem(g, 9, 3, i, new Color(items[i].rgb), "");
                }
            }
            g.dispose();
            img = inv;
            roi = titleBand(title, correct.name, inv);
        }

        /**
         * The band of the colour name in the title bar of the window.
         *
         * <p>Same frame as {@link CaptchasX}: the title is the only place where the name
         * of the colour to click is written down, and the band is that name alone, at
         * the size the title is fitted to.
         */
        private static int[] titleBand(String title, String name, BufferedImage frame) {
            Graphics2D g = TextBand.measure();
            try {
                int size = Math.round(McUi.titleSize(g, title, frame.getWidth()));
                TextBand.Hit hit = TextBand.locate(g, title, name, size);
                if (hit == null) {
                    return null;
                }
                g.setFont(Img.font("Monospaced",
                        hit.bold() ? java.awt.Font.BOLD : java.awt.Font.PLAIN, size));
                FontMetrics fm = g.getFontMetrics();
                return TextBand.fits(
                        TextBand.box(12 + hit.x(), 16, fm.getAscent(), fm.getDescent(),
                                fm.stringWidth(name)),
                        frame.getWidth(), frame.getHeight());
            } finally {
                g.dispose();
            }
        }

        @Override
        public String plugin() {
            return "Joey61021/captcha";
        }

        @Override
        public String id() {
            return "colorgui";
        }

        @Override
        public String answer() {
            return correct.name;
        }

        /** The window title the constructor gives {@code McUi.inventory}, colour-free. */
        @Override
        public String prompt() {
            return McUi.strip("Click on the color " + correct.name);
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the colour name in the title bar of the window.
         *
         * <p>Same frame as {@link CaptchasX}: the title is the only place where the name
         * of the colour to click is written down, and the band is that name alone.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return "com.captcha.plugin.services.CaptchaService#gui";
        }
    }
}