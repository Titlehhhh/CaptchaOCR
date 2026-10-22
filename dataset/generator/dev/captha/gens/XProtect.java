package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * Faithful reimplementation of every captcha in <b>LagBug/XProtect</b>
 * (github.com/LagBug/XProtect), file by file.
 *
 * <pre>
 *   src/main/java/me/lagbug/xprotect/spigot/captchas/*.java
 *   src/main/java/me/lagbug/xprotect/spigot/common/utils/util/CommonUtils.java
 *   src/main/resources/captchas.yml
 *   src/main/resources/lang/en_US.yml
 * </pre>
 */
public final class XProtect {

    private XProtect() {
    }

    public static final String PLUGIN = "LagBug/XProtect";
    public static final String SRC = "me.lagbug.xprotect.spigot.captchas";

    /** CommonUtils.alphabet - exact string from the source. */
    private static final String ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

    /** CommonUtils.randomString(int). */
    static String randomString(int length, Random r) {
        StringBuilder sb = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            sb.append(ALPHABET.charAt(r.nextInt(ALPHABET.length())));
        }
        return sb.toString();
    }

    /** CommonUtils.randomInteger(min,max) - inclusive both ends. */
    static int randomInteger(int min, int max, Random r) {
        return r.nextInt(max - min + 1) + min;
    }

    /* ================================================================== bands */

    /** A rendered frame and the band of it that carries the answer. */
    private record Rendered(BufferedImage image, int[] roi) {
    }

    /**
     * The band of the challenge line inside a chat scene.
     *
     * <p>{@link McUi#scene} draws two to four lines of ordinary server chat and the
     * challenge line last, always 22px below the one before it; the frame is 48px plus
     * 22px per chat line tall, so the baseline of the challenge line is the height of
     * the scene minus 24. The line itself starts at x=6 and is drawn in the chat font at
     * 14pt, and the piece of it that carries the answer is located inside the coloured
     * string exactly the way the renderer walks it - see {@link TextBand#locate}.
     *
     * @param scene the chat scene the line is drawn in
     * @param coded the challenge line, with its colour codes, as it is drawn
     * @param needle the piece of the line that carries the answer
     */
    private static int[] chatBand(BufferedImage scene, String coded, String needle) {
        Graphics2D g = TextBand.measure();
        try {
            int size = 14;
            TextBand.Hit hit = TextBand.locate(g, coded, needle, size);
            if (hit == null) {
                return null;
            }
            g.setFont(Img.font("Monospaced", hit.bold() ? Font.BOLD : Font.PLAIN, size));
            FontMetrics fm = g.getFontMetrics();
            // the challenge line is longer than the chat window, so the answer can run
            // off the right edge of the frame - and a cut band is no band at all
            return TextBand.fits(
                    TextBand.box(6 + hit.x(), scene.getHeight() - 24, fm.getAscent(), fm.getDescent(),
                            fm.stringWidth(needle)),
                    scene.getWidth(), scene.getHeight());
        } finally {
            g.dispose();
        }
    }

    /* =================================================================== MAP */
    /**
     * Map.generateCaptcha(String) - the plugin's image captcha, rendered onto a
     * Minecraft map item. 130x130 TYPE_INT_BGR, black fill, Fixedsys 17 with
     * CENTER_BASELINE, per-character random translate, then 51 interference lines.
     */
    public static final class MapCaptcha implements Cg {
        private final Random r = new Random();
        private final String code = randomString(6, r);
        private BufferedImage img;

        public MapCaptcha() {
            img = generate(code, r);
        }

        static BufferedImage generate(String code, Random r) {
            BufferedImage image = new BufferedImage(130, 130, BufferedImage.TYPE_INT_BGR);
            Graphics2D g = (Graphics2D) image.getGraphics();
            // g.fillRect with no setColor first -> the default BLACK fill.
            g.fillRect(0, 0, 130, 130);
            g.setColor(Color.RED); // captchas.map.textColor

            int margin = 130 / code.length();
            for (int i = 0; i < code.length(); ++i) {
                g.setFont(Img.font("Fixedsys", Font.CENTER_BASELINE, 17));
                // The original calls translate() cumulatively and never resets it.
                g.translate(r.nextInt(3), r.nextInt(3));
                g.drawString(String.valueOf(code.charAt(i)), margin * i, randomInteger(40, 90, r));
            }

            g.setColor(Color.BLACK); // captchas.map.linesColor
            for (int i = 0; i <= 50; i++) { // captchas.map.lines: 50, loop is i <= lines
                int x = r.nextInt(130);
                int y = r.nextInt(130);
                int xl = r.nextInt(13);
                int yl = r.nextInt(15);
                g.drawLine(x, y, x + xl, y + yl);
            }
            g.dispose();
            return image;
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
            return code;
        }

        /**
         * {@code instructions.map} from {@code lang/en_US.yml}, verbatim. The map captcha
         * draws nothing but the code, so this chat line is the whole of what the player is
         * asked to do; it is the only place the challenge is ever worded.
         */
        @Override
        public String prompt() {
            return McUi.strip("&6&lXProtect &8» &7Type the &ccode &7that is displayed in the map.");
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * No band: the map carries nothing but the code.
         *
         * <p>There is no title, no counter and no instruction on the sheet - the six
         * characters <i>are</i> the frame - and their baselines are drawn at random
         * between y=40 and y=90, so there is no single tight box around them either.
         */
        @Override
        public int[] roi() {
            return null;
        }

        @Override
        public String source() {
            return SRC + ".Map#generateCaptcha";
        }
    }

    /* =============================================================== EQUATION */
    /** Equation.execute - operands in [1,15]; subtract when the 2nd is smaller, else add. */
    public static final class Equation implements Cg {
        private final Random r = new Random();
        private final int min = 1;
        private final int max = 15;
        private final int a = randomInteger(min, max, r);
        private final int b = randomInteger(min, max, r);
        private final boolean subtract = b < a;
        private final int sum = subtract ? a - b : a + b;
        private final String text = a + (subtract ? " - " : " + ") + b;
        private final Rendered rendered;

        public Equation() {
            rendered = renderChat("&6&lXProtect &8» &7Please solve the following equation: &c"
                    + text + "&7.", text, r);
        }

        static Rendered renderChat(String instruction, String needle, Random r) {
            BufferedImage scene = McUi.scene(instruction, r, 420);
            return new Rendered(scene, chatBand(scene, instruction, needle));
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "equation";
        }

        @Override
        public String answer() {
            return String.valueOf(sum);
        }

        /**
         * What is actually written in the picture: the expression, not its value. The
         * sum is worked out by the solver, so the recogniser is trained on the
         * expression the player reads.
         */
        @Override
        public String text() {
            return text;
        }

        @Override
        public String prompt() {
            return text + " = ?";
        }

        @Override
        public BufferedImage image() {
            return rendered.image();
        }

        /**
         * The band of the equation, in the challenge line of the chat scene.
         *
         * <p>The frame is a chat log: two to four lines of ordinary server chat and the
         * challenge line last. The line reads {@code XProtect » Please solve the
         * following equation: 7 + 4.}, and the band is exactly the {@code 7 + 4} - the
         * operands the player has to add up, without the plugin prefix, without the
         * trailing dot and without the chat above it. The sum itself is never drawn.
         */
        @Override
        public int[] roi() {
            return rendered.roi();
        }

        @Override
        public String source() {
            return SRC + ".Equation#execute";
        }
    }

    /* =================================================================== CODE */
    /** Code.execute - "Type the code that is displayed in the map" (the in-map captcha). */
    public static final class Code implements Cg {
        private final Random r = new Random();
        private final String code = randomString(6, r);
        private final BufferedImage img = MapCaptcha.generate(code, new Random());

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "code";
        }

        @Override
        public String answer() {
            return code;
        }

        /**
         * The chat line the plugin pairs with the in-map code, i.e.
         * {@code instructions.map} from {@code lang/en_US.yml}. Upstream also ships an
         * {@code instructions.code} key, but it interpolates {@code %code%} and therefore
         * spells the answer out; the map wording is the one that asks a question.
         */
        @Override
        public String prompt() {
            return McUi.strip("&6&lXProtect &8» &7Type the &ccode &7that is displayed in the map.");
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * No band: the map carries nothing but the code.
         *
         * <p>Same sheet as {@link MapCaptcha} - the six characters are the whole frame,
         * there is no other text on it, and their baselines are random.
         */
        @Override
        public int[] roi() {
            return null;
        }

        @Override
        public String source() {
            return SRC + ".Code#execute";
        }
    }

    /* =============================================================== REVERSE */
    /** Reverse.execute - shows a 6 char code, the answer is the reversed string. */
    public static final class Reverse implements Cg {
        private final Random r = new Random();
        private final String code = randomString(6, r);
        private final String reversed = new StringBuilder(code).reverse().toString();
        private final Rendered rendered;

        public Reverse() {
            rendered = Equation.renderChat("&6&lXProtect &8» &7Please reverse the letters of the "
                    + "following code: &c" + code + "&7.", code, r);
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "reverse";
        }

        @Override
        public String answer() {
            return reversed;
        }

        /**
         * What is written in the picture: the code as drawn, not the reversed string the
         * player has to type. The band carries the drawn code, so the recogniser is
         * trained on it and the reversal is the solver's step.
         */
        @Override
        public String text() {
            return code;
        }

        /** The challenge line the constructor hands to {@code McUi.scene}, stripped. */
        @Override
        public String prompt() {
            return McUi.strip("&6&lXProtect &8» &7Please reverse the letters of the following code: &c"
                    + code + "&7.");
        }

        @Override
        public BufferedImage image() {
            return rendered.image();
        }

        /**
         * The band of the code, in the challenge line of the chat scene.
         *
         * <p>The line reads {@code XProtect » Please reverse the letters of the following
         * code: sPfg1B.}; the band is exactly the six characters, without the plugin
         * prefix and without the chat above. Note that the band carries the code as
         * drawn - the answer is the same six characters in the other order.
         */
        @Override
        public int[] roi() {
            return rendered.roi();
        }

        @Override
        public String source() {
            return SRC + ".Reverse#execute";
        }
    }

    /* ================================================================== SLOT */
    /** Slot.execute - asks for hotbar slot 1..8. */
    public static final class Slot implements Cg {
        private final Random r = new Random();
        private final int slot = randomInteger(1, 8, r);
        private final Rendered rendered = renderHotbar(slot, r);

        static Rendered renderHotbar(int slot, Random r) {
            String line = "&6&lXProtect &8» &7Please move to the &c" + slot
                    + "th &7slot of your hotbar.";
            BufferedImage scene = McUi.scene(line, r, 300);
            int bw = 19;
            int w = 14 + 9 * bw;
            int h = bw + 8;
            BufferedImage hotbar = Img.rgb(w, h);
            Graphics2D g = Img.g2d(hotbar, true);
            for (int i = 0; i < 9; i++) {
                int x = i * bw;
                boolean hit = (i + 1) == slot;
                g.setColor(hit ? new Color(0xFF, 0xFF, 0xFF, 235) : new Color(0x8B, 0x8B, 0x8B));
                g.fillRect(x, 4, bw, bw);
                g.setColor(hit ? new Color(0x55, 0xFF, 0x55) : new Color(0x37, 0x37, 0x37));
                g.drawRect(x, 4, bw, bw);
                if (hit) {
                    g.setStroke(new java.awt.BasicStroke(2f));
                    g.drawRect(x, 4, bw, bw);
                    g.setStroke(new java.awt.BasicStroke(1f));
                }
            }
            g.dispose();
            // the chat scene is the base of the frame, so the band keeps its coordinates
            return new Rendered(McUi.over(scene, hotbar),
                    chatBand(scene, line, String.valueOf(slot)));
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "slot";
        }

        @Override
        public String answer() {
            return String.valueOf(slot);
        }

        /** The challenge line {@code renderHotbar} hands to {@code McUi.scene}, stripped. */
        @Override
        public String prompt() {
            return McUi.strip("&6&lXProtect &8» &7Please move to the &c" + slot
                    + "th &7slot of your hotbar.");
        }

        @Override
        public BufferedImage image() {
            return rendered.image();
        }

        /**
         * The band of the slot number, in the challenge line of the chat scene.
         *
         * <p>The line reads {@code XProtect » Please move to the 5th slot of your
         * hotbar.}; the band is the single digit the plugin prints in red, without the
         * words around it. The hotbar strip below the chat shows the same slot, but as
         * a highlighted cell, not as text.
         */
        @Override
        public int[] roi() {
            return rendered.roi();
        }

        @Override
        public String source() {
            return SRC + ".Slot#execute";
        }
    }

    /* ================================================================= COLOR */
    /** Color.execute - the colour name is replaced by the colour itself. */
    public static final class ColorCaptcha implements Cg {
        private final Random r = new Random();
        private final String name;
        private final int rgb;
        private BufferedImage img;

        public ColorCaptcha() {
            List<int[]> colors = new ArrayList<>();
            List<String> names = new ArrayList<>();
            // ChatColor.values() where isColor(), with the source's name rewrite rules.
            add(colors, names, McUi.Mc.BLACK, "black");
            add(colors, names, McUi.Mc.DARK_BLUE, "dark blue");
            add(colors, names, McUi.Mc.DARK_GREEN, "green");
            add(colors, names, McUi.Mc.DARK_AQUA, "dark aqua");
            add(colors, names, McUi.Mc.DARK_RED, "red");
            add(colors, names, McUi.Mc.DARK_PURPLE, "purple");
            add(colors, names, McUi.Mc.GOLD, "orange");
            add(colors, names, McUi.Mc.GRAY, "gray");
            add(colors, names, McUi.Mc.DARK_GRAY, "gray");
            add(colors, names, McUi.Mc.BLUE, "blue");
            add(colors, names, McUi.Mc.GREEN, "green");
            add(colors, names, McUi.Mc.AQUA, "blue");
            add(colors, names, McUi.Mc.RED, "red");
            add(colors, names, McUi.Mc.LIGHT_PURPLE, "purple");
            add(colors, names, McUi.Mc.YELLOW, "yellow");
            add(colors, names, McUi.Mc.WHITE, "white");
            int i = r.nextInt(colors.size());
            name = names.get(i);
            rgb = colors.get(i)[0];
            img = render(name, rgb, r);
        }

        private static void add(List<int[]> colors, List<String> names, McUi.Mc m, String n) {
            colors.add(new int[]{m.rgb});
            names.add(n);
        }

        static BufferedImage render(String name, int rgb, Random r) {
            return McUi.sceneSplit("&6&lXProtect &8» &7Type what (&r", "THIS",
                    new Color(rgb), "&r&7) color's name is.", r, 420);
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "color";
        }

        @Override
        public String answer() {
            return name;
        }

        /**
         * The three pieces {@code sceneSplit} draws - the {@code before} prefix, the word
         * "THIS" painted in the colour itself, and the {@code after} suffix - as one line.
         */
        @Override
        public String prompt() {
            return McUi.strip("&6&lXProtect &8» &7Type what (&rTHIS&r&7) color's name is.");
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * No band: the answer is a colour <i>name</i> and the picture carries the colour,
         * not its name.
         *
         * <p>The challenge line reads {@code XProtect » Type what (THIS) color's name
         * is.}, where the word THIS is painted in the colour itself. A recogniser that
         * reads the line would read "THIS", which is not the answer - the answer is
         * whatever the name of that colour is - so there is no band that carries it.
         */
        @Override
        public int[] roi() {
            return null;
        }

        @Override
        public String source() {
            return SRC + ".Color#execute";
        }
    }

    /* =============================================================== MOVEMENT */
    /**
     * Sneak.execute / Jump.execute - keypress challenges. Base class for the two
     * no-arg subclasses below; {@code Keypress} itself is never registered because
     * {@code Gen} only picks up public no-arg constructors.
     */
    public static class Keypress implements Cg {
        private final String which;
        private final Rendered rendered;

        public Keypress(String which) {
            this.which = which;
            Random r = new Random();
            String msg = "sneak".equals(which)
                    ? "&6&lXProtect &8» &7Please &csneak &7(usually using SHIFT key)."
                    : "&6&lXProtect &8» &7Please &cjump &7(usually using SPACE key).";
            rendered = renderKey(msg, which, r);
        }

        static Rendered renderKey(String msg, String which, Random r) {
            BufferedImage scene = McUi.scene(msg, r, 400);
            int w = 70;
            int h = 26 + 8;
            BufferedImage key = Img.rgb(w, h);
            Graphics2D g = Img.g2d(key, true);
            g.setColor(new Color(0x55, 0x55, 0x55));
            g.fillRect(0, 4, w, 26);
            g.setColor(new Color(0x80, 0x80, 0x80));
            g.drawRect(0, 4, w, 26);
            g.setColor(new Color(0xFF, 0xFF, 0xFF));
            g.fillRect(3, 7, w - 6, 6);
            g.setFont(Img.font("Monospaced", Font.BOLD, 13));
            g.setColor(Color.WHITE);
            String label = "sneak".equals(which) ? "SHIFT" : "SPACE";
            int tw = g.getFontMetrics().stringWidth(label);
            g.drawString(label, (w - tw) / 2, 24);
            g.dispose();
            // the chat scene is the base of the frame, so the band keeps its coordinates
            return new Rendered(McUi.over(scene, key),
                    chatBand(scene, msg, which));
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return which;
        }

        @Override
        public String answer() {
            return which;
        }

        /** The same fixed chat line the constructor renders, colour codes removed. */
        @Override
        public String prompt() {
            return McUi.strip("sneak".equals(which)
                    ? "&6&lXProtect &8» &7Please &csneak &7(usually using SHIFT key)."
                    : "&6&lXProtect &8» &7Please &cjump &7(usually using SPACE key).");
        }

        @Override
        public BufferedImage image() {
            return rendered.image();
        }

        /**
         * The band of the key word, in the challenge line of the chat scene.
         *
         * <p>The line reads {@code XProtect » Please sneak (usually using SHIFT key).};
         * the band is the word {@code sneak} (or {@code jump}) alone. The key graphic
         * below the chat carries the key's own name - "SHIFT", "SPACE" - which is a
         * different word and is not part of the answer.
         */
        @Override
        public int[] roi() {
            return rendered.roi();
        }

        @Override
        public String source() {
            return SRC + "." + (which.equals("sneak") ? "Sneak" : "Jump") + "#execute";
        }
    }

    /** Sneak.execute - the public no-arg face of {@link Keypress("sneak")}. */
    public static final class Sneak extends Keypress {
        public Sneak() {
            super("sneak");
        }
    }

    /** Jump.execute - the public no-arg face of {@link Keypress("jump")}. */
    public static final class Jump extends Keypress {
        public Jump() {
            super("jump");
        }
    }

    /* ================================================================== DROP */
    /** Drop.execute - drop the held item (APPLE by default). */
    public static final class Drop implements Cg {
        private final Rendered rendered;

        public Drop() {
            Random r = new Random();
            String line = "&6&lXProtect &8» &7Please &cdrop &7the item you're holding "
                    + "(usually using Q key).";
            BufferedImage scene = McUi.scene(line, r, 420);
            // captchas.drop.item: APPLE
            BufferedImage item = Img.rgb(24, 24);
            Graphics2D gi = Img.g2d(item, true);
            gi.setColor(new Color(0xD0, 0x3A, 0x2E));
            gi.fillOval(3, 3, 18, 18);
            gi.setColor(new Color(0x8A, 0x22, 0x1A));
            gi.fillOval(3, 13, 18, 8);
            gi.setColor(new Color(0x5A, 0x7A, 0x2A));
            gi.fillRect(11, 0, 3, 5);
            gi.dispose();
            // the chat scene is the base of the frame, so the band keeps its coordinates
            rendered = new Rendered(McUi.over(scene, item),
                    chatBand(scene, line, "drop"));
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "drop";
        }

        @Override
        public String answer() {
            return "drop";
        }

        /** The fixed chat line the constructor hands to {@code McUi.scene}, stripped. */
        @Override
        public String prompt() {
            return McUi.strip("&6&lXProtect &8» &7Please &cdrop &7the item you're holding "
                    + "(usually using Q key).");
        }

        @Override
        public BufferedImage image() {
            return rendered.image();
        }

        /**
         * The band of the word, in the challenge line of the chat scene.
         *
         * <p>The line reads {@code XProtect » Please drop the item you're holding
         * (usually using Q key).}; the band is the word {@code drop} alone. The apple
         * drawn below the chat is a picture, not text.
         */
        @Override
        public int[] roi() {
            return rendered.roi();
        }

        @Override
        public String source() {
            return SRC + ".Drop#execute";
        }
    }

    /* =================================================================== GUI */
    /** Gui.execute - 27 slots of random items, click the one named in the title. */
    public static final class Gui implements Cg {
        private static final String[] ITEMS = {
                "Stone", "Cobblestone", "Oak Log", "Dirt", "Sand", "Gravel", "Glass", "Coal Ore", "Iron Ore",
                "Gold Ore", "Diamond Ore", "Lapis Ore", "Redstone Ore", "Emerald Ore", "Clay", "Snow Block",
                "Ice", "Packed Ice", "Bricks", "Bookshelf", "Mossy Cobblestone", "Obsidian", "Netherrack",
                "Glowstone", "Jack O'Lantern", "Pumpkin", "Melon", "Hay Bale", "Bone Block", "Quartz Block",
                "Iron Block", "Gold Block", "Diamond Block", "Emerald Block", "Lapis Block", "Redstone Block",
                "Slime Block", "Prismarine", "Purpur Block", "Magma Block", "Soul Sand", "Gravel Block"};

        private final String target;
        private final Rendered rendered;

        public Gui() {
            Random r = new Random();
            int slots = 27;
            int cols = 9;
            List<String> pool = new ArrayList<>(List.of(ITEMS));
            java.util.Collections.shuffle(pool, r);
            String[] grid = pool.subList(0, slots).toArray(new String[0]);
            target = grid[r.nextInt(slots)];
            String title = "Click on the &6" + titleCase(target);
            BufferedImage inv = McUi.inventory(cols, 3, title);
            Graphics2D g = Img.g2d(inv, true);
            for (int i = 0; i < slots; i++) {
                McUi.slotItem(g, cols, 3, i, colorFor(grid[i]), "");
            }
            g.dispose();
            String line = "&6&lXProtect &8» &7Please click on the &c" + target + "&7.";
            BufferedImage scene = McUi.scene(line, r, 380);
            // the chat scene is the base of the frame, so the band keeps its coordinates
            rendered = new Rendered(McUi.over(scene, inv),
                    chatBand(scene, line, target));
        }

        private static String titleCase(String s) {
            return Character.toUpperCase(s.charAt(0)) + s.substring(1);
        }

        private static Color colorFor(String name) {
            int h = name.hashCode();
            return new Color(90 + Math.abs(h % 140), 90 + Math.abs((h / 7) % 140), 90 + Math.abs((h / 13) % 140));
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "gui";
        }

        @Override
        public String answer() {
            return target;
        }

        /** The chat line the constructor hands to {@code McUi.scene}, stripped. */
        @Override
        public String prompt() {
            return McUi.strip("&6&lXProtect &8» &7Please click on the &c" + target + "&7.");
        }

        @Override
        public BufferedImage image() {
            return rendered.image();
        }

        /**
         * The band of the item name, in the challenge line of the chat scene.
         *
         * <p>The name is written twice: in the chat line {@code XProtect » Please click
         * on the Cobblestone.} and in the title bar of the inventory window, where it is
         * written in gold. The chat line is the one that carries the answer verbatim -
         * the title bar capitalises the name - so the band is the item name in the chat
         * line, without the plugin prefix and without the chat above it.
         */
        @Override
        public int[] roi() {
            return rendered.roi();
        }

        @Override
        public String source() {
            return SRC + ".Gui#execute";
        }
    }

    /* ============================================================== DIFFERENT */
    /** Different.execute - 9 redstone blocks with one emerald block hidden among them. */
    public static final class Different implements Cg {
        private final Random r = new Random();
        private final int diffSlot = r.nextInt(9);
        private final BufferedImage img;

        public Different() {
            BufferedImage inv = McUi.inventory(9, 1, "Click on the different item");
            Graphics2D g = Img.g2d(inv, true);
            for (int i = 0; i < 9; i++) {
                boolean isDiff = i == diffSlot;
                McUi.slotItem(g, 9, 1, i,
                        isDiff ? new Color(0x2E, 0xB7, 0x4F) : new Color(0xB0, 0x2A, 0x2A), "");
            }
            g.dispose();
            img = McUi.over(McUi.scene("&6&lXProtect &8» &7Please click on the different item.", r, 380), inv);
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "different";
        }

        @Override
        public String answer() {
            return "EMERALD_BLOCK";
        }

        /** The chat line the constructor hands to {@code McUi.scene}, stripped. */
        @Override
        public String prompt() {
            return McUi.strip("&6&lXProtect &8» &7Please click on the different item.");
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * No band: the answer is a block, not a text.
         *
         * <p>The window asks the player to spot the one emerald block among nine red
         * ones. The frame carries no word that names the answer - the title bar only
         * says "Click on the different item" - so there is no text band to hand over.
         */
        @Override
        public int[] roi() {
            return null;
        }

        @Override
        public String source() {
            return SRC + ".Different#execute";
        }
    }

    /* ================================================================ PICTURE */
    /**
     * Picture.execute - shows one image out of the pictures folder and asks the player to
     * type its file name from a list. The "caption grid" is re-rendered as a drawn scene
     * since the shipped folder is user-supplied.
     */
    public static final class Picture implements Cg {
        private static final String[] SUBJECTS = {"cat", "dog", "tree", "house", "car", "boat", "fish", "bird",
                "flower", "chair", "table", "lamp", "book", "clock", "door", "window", "star", "moon", "cloud", "sun"};
        private final Random r = new Random();
        private final String[] options = pickOptions(r);
        private final String answer;
        private final BufferedImage img;

        public Picture() {
            answer = options[r.nextInt(options.length)];
            int cols = 5;
            int rows = 4;
            BufferedImage panel = McUi.inventory(cols, rows, "Type what you're seeing");
            Graphics2D g = Img.g2d(panel, true);
            for (int i = 0; i < options.length; i++) {
                McUi.slotItem(g, cols, rows, i, colorFor(options[i]), "");
            }
            g.dispose();

            int w = panel.getWidth();
            int h = panel.getHeight() + 52;
            BufferedImage out = Img.rgb(w, h);
            Graphics2D go = Img.g2d(out, true);
            go.setColor(new Color(0x10, 0x10, 0x14));
            go.fillRect(0, 0, w, h);
            go.drawImage(panel, 0, 52, null);
            McUi.drawColored(go, McUi.codes("&7Choose from: &c" + String.join(", ", options)), 4, 26, 12f, true);
            go.dispose();
            img = out;
        }

        private static String[] pickOptions(Random r) {
            List<String> all = new ArrayList<>(List.of(SUBJECTS));
            java.util.Collections.shuffle(all, r);
            return all.subList(0, 6).toArray(new String[0]);
        }

        private static Color colorFor(String name) {
            int h = name.hashCode();
            return new Color(80 + Math.abs(h % 150), 80 + Math.abs((h / 11) % 150), 80 + Math.abs((h / 17) % 150));
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "picture";
        }

        @Override
        public String answer() {
            return answer;
        }

        /**
         * {@code instructions.picture} from {@code lang/en_US.yml} - the window title
         * "Type what you're seeing" plus the option list drawn under the panel.
         */
        @Override
        public String prompt() {
            return McUi.strip("&6&lXProtect &8» &7Type what you're seeing. Choose from [&c"
                    + String.join(", ", options) + "&7].");
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * No band: the frame lists six candidates and the answer is one of them.
         *
         * <p>The picture captcha draws the option list ("Choose from: cat, dog, tree,
         * house, car, boat") above the panel of swatches, and the answer is one of those
         * six words. No band of the frame carries the answer on its own - the band that
         * holds it holds five wrong answers with it.
         */
        @Override
        public int[] roi() {
            return null;
        }

        @Override
        public String source() {
            return SRC + ".Picture#execute";
        }
    }
}