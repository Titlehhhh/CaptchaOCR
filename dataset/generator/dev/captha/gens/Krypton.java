package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.Random;

/**
 * <b>Archy-X/Krypton</b> (github.com/Archy-X/Krypton) - a two-mode join captcha.
 *
 * <p>The upstream project ships no licence file, so everything below is an independent
 * implementation written against the observable behaviour of the plugin: the MAP mode
 * (a short code rendered onto a Minecraft map item) and the MENU mode (a 6x9 inventory in
 * which exactly one of 54 identical stacks is the one to click).
 *
 * <pre>
 *   src/main/java/com/archyx/krypton/captcha/MapGenerator.java   - code + draw position
 *   src/main/java/com/archyx/krypton/captcha/CaptchaMenu.java     - the click-one-stack GUI
 *   src/main/java/com/archyx/krypton/util/MaterialUtil.java      - candidate item pool
 *   src/main/resources/config.yml, src/main/resources/messages.yml
 * </pre>
 *
 * <p>The glyph table further down is Minecraft's own 5x7 map font (the bitmap used by
 * {@code MapCanvas.drawText}), not a system typeface.
 */
public final class Krypton {

    private Krypton() {
    }

    public static final String PLUGIN = "Archy-X/Krypton";
    public static final String MAP_SRC = "com.archyx.krypton.captcha.MapGenerator#generateCode";
    public static final String MENU_SRC = "com.archyx.krypton.captcha.CaptchaMenu";

    /* -------------------------------------------------------- config.yml --- */
    /** captcha.map.code_length */
    private static final int CODE_LENGTH = 5;
    /** captcha.map.use_numbers */
    private static final boolean USE_NUMBERS = true;
    /** captcha.map.use_capital_letters */
    private static final boolean USE_CAPITAL_LETTERS = true;

    /* ---------------------------------------------------- map geometry ---- */
    /** A Bukkit map is always a 128x128 pixel tile. */
    private static final int MAP_EDGE = 128;
    /** generatePosition() draws inside an 80px wide / 80px tall budget. */
    private static final int TEXT_SPAN = 80;
    /** The source budgets 4 map pixels per configured code character. */
    private static final int BUDGET_PER_CHAR = 4;
    /** x is offset by 2 so a 1px glyph is never clipped on the left edge. */
    private static final int X_BIAS = 2;
    /** y starts at 5 rather than 0. */
    private static final int Y_BIAS = 5;
    /** Lengths above this are clamped before the position is derived. */
    private static final int MAX_LENGTH_CLAMP = 20;

    /** Colour the vanilla map canvas draws glyphs in (MapPalette black). */
    private static final Color MAP_INK = new Color(0x00, 0x00, 0x00);
    /** A freshly created map has no base layer, so the tiles are shown as bare paper. */
    private static final Color MAP_PAPER = new Color(0xFF, 0xFF, 0xFF);

    /* --------------------------------------------------- messages.yml ----- */
    private static final String MAP_INFO = "&cEnter the code on the map in chat to be verified.";
    private static final String MENU_TITLE = "Click the item to be verified";
    /** menu.fill_item - the hover name of the 53 decoy stacks (never drawn, only on hover). */
    private static final String MENU_FILL_ITEM = "&cDO NOT CLICK ME";
    /** menu.click_item - the hover name of the single correct stack. */
    private static final String MENU_CLICK_ITEM = "&aCLICK ME!";
    /** Chat line the menu is shown over; the plugin itself only sends the GUI. */
    private static final String MENU_CHAT = "&6&lKrypton &8» &7Click the item to be verified.";

    /** SmartInventory.builder().size(6, 9) - a 54 slot grid. */
    private static final int MENU_COLS = 6;
    private static final int MENU_ROWS = 9;
    private static final int MENU_SLOTS = MENU_COLS * MENU_ROWS;

    /* ===================================================================== MAP */
    /**
     * The map captcha: {@code generateCode()} picks {@code captcha.map.code_length}
     * characters out of lower case, upper case and digits, {@code generatePosition()}
     * picks a spot for the whole string, and the string is drawn once per map render tick
     * with Minecraft's native map font.
     *
     * <p>Two quirks of the source are preserved deliberately:
     * <ul>
     *   <li>the "numbers only" arm still emits a lower case letter or a digit, so a
     *       digits-only configuration is not actually digits-only;</li>
     *   <li>the position is generated once, when the map is created, not on every render.</li>
     * </ul>
     */
    public static final class Map implements Cg {
        private final String code;
        private final int[] pos;
        private final BufferedImage img;
        private final int[] roi;

        public Map() {
            Random r = new Random();
            code = generateCode(CODE_LENGTH, USE_NUMBERS, USE_CAPITAL_LETTERS, r);
            pos = generatePosition(CODE_LENGTH, r);
            img = render(code, pos);
            roi = band(pos, code);
        }

        /**
         * The band of the code on the map.
         *
         * <p>The map is a 128x128 sheet of bare paper and the code is five map-font
         * glyphs somewhere on it - the plugin draws the whole string at a position it
         * generates once, when the map is created. The band is exactly the box those
         * glyphs occupy: the position the plugin chose, five map-font cells wide and
         * eight rows high.
         *
         * <p>Unlike the other bands of this dataset this one moves from sample to
         * sample, because the plugin moves the code: the position is the one
         * {@code generatePosition()} produced, so the band is exact for every sample
         * rather than constant.
         */
        private static int[] band(int[] pos, String code) {
            int w = 0;
            int drawn = 0;
            for (int i = 0; i < code.length(); i++) {
                char c = code.charAt(i);
                int[] rows = glyph(c);
                if (rows == null) {
                    continue;
                }
                w += c == ' ' ? SPACE_ADVANCE : advance(rows);
                drawn++;
            }
            // The renderer leaves one blank column between two glyphs (pen += w + 1),
            // so the drawn run is (drawn - 1) columns wider than the sum of the glyph
            // widths: for the shipped 5 char code that is code.length() - 1 = 4 px.
            // Without it the band was 4 px too narrow and the last glyph fell outside.
            w += Math.max(0, drawn - 1);
            return new int[]{pos[0], pos[1], w, 8};
        }

        /**
         * The four-way character choice. With the shipped config (numbers and capitals both
         * on) every character costs one {@code nextInt(3)} roll: 0 lower case, 1 upper case,
         * 2 digit. The digit arm appends an {@code int}, which is always a single digit.
         */
        static String generateCode(int length, boolean numbers, boolean capitals, Random r) {
            StringBuilder code = new StringBuilder(length);
            for (int i = 0; i < length; i++) {
                if (numbers && capitals) {
                    switch (r.nextInt(3)) {
                        case 0 -> code.append((char) (r.nextInt(26) + 'a'));
                        case 1 -> code.append((char) (r.nextInt(26) + 'A'));
                        case 2 -> code.append(r.nextInt(10));
                        default -> {
                        }
                    }
                } else if (capitals) {
                    switch (r.nextInt(2)) {
                        case 0 -> code.append((char) (r.nextInt(26) + 'a'));
                        default -> code.append((char) (r.nextInt(26) + 'A'));
                    }
                } else if (numbers) {
                    // Reproduced as-is: this arm is mixed, it is not digits-only.
                    switch (r.nextInt(2)) {
                        case 0 -> code.append((char) (r.nextInt(26) + 'a'));
                        default -> code.append(r.nextInt(10));
                    }
                } else {
                    code.append((char) (r.nextInt(26) + 'a'));
                }
            }
            return code.toString();
        }

        /** Top-left corner of the drawn string: {@code [2, 62] x [5, 84]} for a 5 char code. */
        static int[] generatePosition(int length, Random r) {
            int len = Math.min(length, MAX_LENGTH_CLAMP);
            return new int[]{
                    r.nextInt(TEXT_SPAN - len * BUDGET_PER_CHAR + 1) + X_BIAS,
                    r.nextInt(TEXT_SPAN) + Y_BIAS
            };
        }

        /**
         * What the client paints: bare map paper with the code blitted in the map font.
         * The map has no base layer, so unset tiles are the map's own paper colour.
         */
        static BufferedImage render(String code, int[] pos) {
            BufferedImage map = Img.rgb(MAP_EDGE, MAP_EDGE);
            Graphics2D g = Img.g2d(map, false);
            g.setColor(MAP_PAPER);
            g.fillRect(0, 0, MAP_EDGE, MAP_EDGE);
            drawMapText(g, pos[0], pos[1], code);
            g.dispose();
            return map;
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

        @Override
        public String prompt() {
            return McUi.strip(MAP_INFO);
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the code on the map.
         *
         * <p>The sheet is bare paper with the five glyphs of the code somewhere on it -
         * the plugin picks the position when the map is created and never moves it
         * again. The band is the box the code occupies, so a solver can crop away the
         * empty paper. The position differs from sample to sample, and the band is
         * stored per sample, so the crop is always exact.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return MAP_SRC;
        }
    }

    /* ==================================================================== MENU */
    /**
     * The menu captcha: a 6x9 inventory whose 54 slots are all filled with the same item
     * ("DO NOT CLICK ME"), with exactly one slot replaced by a different item ("CLICK ME!").
     * Clicking any of the 53 decoys increments the failure counter; {@code fail_kick_max_attempts}
     * is 5 and {@code menu.reopen_delay} is 40 ticks.
     */
    public static final class Menu implements Cg {
        private final String fillMaterial;
        private final String clickMaterial;
        private final int clickSlot;
        private final BufferedImage img;

        public Menu() {
            Random r = new Random();
            int fill = r.nextInt(MATERIALS.length);
            // The source re-rolls until the click stack is not the fill material.
            int click;
            do {
                click = r.nextInt(MATERIALS.length);
            } while (click == fill || COLORS[click].equals(COLORS[fill]));
            fillMaterial = MATERIALS[fill];
            clickMaterial = MATERIALS[click];
            // The source hands the two bounds straight to the grid, column first.
            clickSlot = r.nextInt(MENU_COLS) + r.nextInt(MENU_ROWS) * MENU_COLS;

            BufferedImage inv = McUi.inventory(MENU_COLS, MENU_ROWS, MENU_TITLE);
            Graphics2D g = Img.g2d(inv, true);
            for (int i = 0; i < MENU_SLOTS; i++) {
                // Hover names only, so nothing is painted into the slots themselves.
                McUi.slotItem(g, MENU_COLS, MENU_ROWS, i, COLORS[fill], "");
            }
            McUi.slotItem(g, MENU_COLS, MENU_ROWS, clickSlot, COLORS[click], "");
            g.dispose();

            img = McUi.over(McUi.scene(MENU_CHAT, r, 380), inv);
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "menu";
        }

        @Override
        public String answer() {
            return clickMaterial;
        }

        @Override
        public String prompt() {
            return MENU_TITLE;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * No band: the answer is an item, not a text.
         *
         * <p>The window holds 54 stacks and exactly one of them is a different item; the
         * title bar says "Click the item to be verified" and names no item at all.
         */
        @Override
        public int[] roi() {
            return null;
        }

        @Override
        public String source() {
            return MENU_SRC;
        }
    }

    /* =========================================================== item pool === */
    /**
     * A stand-in for {@code MaterialUtil.getValidMaterials()}, which on any modern server is
     * every {@code Material} whose {@code isItem()} is true - roughly a thousand entries.
     * These are real Bukkit item material names with a representative swatch colour; the
     * colours are pairwise distinct so the single odd stack is always identifiable.
     */
    private static final String[] MATERIALS = {
            "STONE", "COBBLESTONE", "STONE_BRICKS", "MOSSY_COBBLESTONE", "GRASS_BLOCK", "DIRT",
            "COARSE_DIRT", "PODZOL", "OAK_PLANKS", "SPRUCE_PLANKS", "BIRCH_PLANKS", "JUNGLE_PLANKS",
            "SAND", "RED_SAND", "GRAVEL", "CLAY", "SNOW_BLOCK", "ICE", "PACKED_ICE", "BLUE_ICE",
            "OAK_LOG", "BIRCH_LOG", "SPRUCE_LOG", "OAK_LEAVES", "BIRCH_LEAVES", "SPONGE", "GLASS",
            "LAPIS_BLOCK", "LAPIS_ORE", "DISPENSER", "SANDSTONE", "NOTE_BLOCK", "POWERED_RAIL",
            "DETECTOR_RAIL", "STICKY_PISTON", "WEB", "TALL_GRASS", "DEAD_BUSH", "PISTON",
            "WHITE_WOOL", "DANDELION", "POPPY", "BLUE_ORCHID", "REDSTONE_TORCH", "REDSTONE_BLOCK",
            "SNOW", "OAK_SAPLING", "CHEST", "DIAMOND_BLOCK", "DIAMOND_ORE", "CRAFTING_TABLE",
            "FURNACE", "LADDER", "RAIL", "COBBLESTONE_STAIRS", "OAK_FENCE", "GLASS_PANE", "MELON",
            "PUMPKIN", "CAKE", "REPEATER", "EMERALD_BLOCK", "ENDER_CHEST", "OBSIDIAN", "GLOWSTONE",
            "NETHER_BRICKS", "SOUL_SAND", "QUARTZ_BLOCK", "HAY_BLOCK", "SLIME_BLOCK", "PRISMARINE",
            "MAGMA_BLOCK"};

    private static final Color[] COLORS = {
            new Color(0x7F7F7F), new Color(0x606060), new Color(0x7A7A72), new Color(0x5F7A52),
            new Color(0x6C9E46), new Color(0x8A6444), new Color(0x77553B), new Color(0x5A3D26),
            new Color(0xB4894D), new Color(0x7A5A36), new Color(0xD6C48A), new Color(0xB1805A),
            new Color(0xDCD3A0), new Color(0xBE6A29), new Color(0x8C8880), new Color(0xA0A7B4),
            new Color(0xF0F5F7), new Color(0x7CADEE), new Color(0x8AB4F0), new Color(0x74A8F0),
            new Color(0x6B4F2A), new Color(0xD7CCA5), new Color(0x3B2611), new Color(0x3C6E28),
            new Color(0x7CB352), new Color(0xC3C246), new Color(0xC6DDE0), new Color(0x1E3A8A),
            new Color(0x354C8E), new Color(0x747474), new Color(0xDAD0A0), new Color(0x5B3A2E),
            new Color(0x9A7B54), new Color(0xA17B44), new Color(0x9AA24E), new Color(0xD8D8C0),
            new Color(0x7FB238), new Color(0x946428), new Color(0x9A6E4A), new Color(0xE9ECEC),
            new Color(0xFFEC33), new Color(0xD93A2E), new Color(0x2FBFA8), new Color(0xA32B20),
            new Color(0xB6212A), new Color(0xF3FAFB), new Color(0x74A03A), new Color(0x9A6E2F),
            new Color(0x39D4D6), new Color(0x5EABAB), new Color(0x8B6A44), new Color(0x555555),
            new Color(0xB08048), new Color(0x8E8880), new Color(0x4A4A4A), new Color(0x9C7A45),
            new Color(0xB8D8DC), new Color(0x6F9B2C), new Color(0xC07615), new Color(0xF0E0C8),
            new Color(0x9A8E9E), new Color(0x2FCB5B), new Color(0x2E6A4E), new Color(0x14101F),
            new Color(0xF5C451), new Color(0x321B21), new Color(0x524139), new Color(0xEDE9E2),
            new Color(0xA67818), new Color(0x71C465), new Color(0x5F9E8E), new Color(0x8E3E1C)};

    /* ======================================================== map font ====== */
    /**
     * Minecraft's 5x7 map font, one glyph per code point starting at U+0020.
     * Every glyph is eight row bitmasks, bit 0 being the left-most pixel column.
     */
    private static final String FONT_CHARS =
            " !\"#$%&'()*+,-./0123456789:;<=>?"
                    + "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_"
                    + "`abcdefghijklmnopqrstuvwxyz{|}~";

    private static final int[][] FONT = {
            {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}, // ' '
            {0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x01, 0x00}, // '!'
            {0x0A, 0x0A, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00}, // '"'
            {0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A, 0x00}, // '#'
            {0x04, 0x1E, 0x01, 0x0E, 0x10, 0x0F, 0x04, 0x00}, // '$'
            {0x11, 0x09, 0x08, 0x04, 0x02, 0x12, 0x11, 0x00}, // '%'
            {0x04, 0x0A, 0x04, 0x16, 0x0D, 0x09, 0x16, 0x00}, // '&'
            {0x02, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00}, // '\''
            {0x0C, 0x02, 0x01, 0x01, 0x01, 0x02, 0x0C, 0x00}, // '('
            {0x03, 0x04, 0x08, 0x08, 0x08, 0x04, 0x03, 0x00}, // ')'
            {0x00, 0x00, 0x09, 0x06, 0x09, 0x00, 0x00, 0x00}, // '*'
            {0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00, 0x00}, // '+'
            {0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01}, // ','
            {0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00, 0x00}, // '-'
            {0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x00}, // '.'
            {0x10, 0x08, 0x08, 0x04, 0x02, 0x02, 0x01, 0x00}, // '/'
            {0x0E, 0x11, 0x19, 0x15, 0x13, 0x11, 0x0E, 0x00}, // '0'
            {0x04, 0x06, 0x04, 0x04, 0x04, 0x04, 0x1F, 0x00}, // '1'
            {0x0E, 0x11, 0x10, 0x0C, 0x02, 0x11, 0x1F, 0x00}, // '2'
            {0x0E, 0x11, 0x10, 0x0C, 0x10, 0x11, 0x0E, 0x00}, // '3'
            {0x18, 0x14, 0x12, 0x11, 0x1F, 0x10, 0x10, 0x00}, // '4'
            {0x1F, 0x01, 0x0F, 0x10, 0x10, 0x11, 0x0E, 0x00}, // '5'
            {0x0C, 0x02, 0x01, 0x0F, 0x11, 0x11, 0x0E, 0x00}, // '6'
            {0x1F, 0x11, 0x10, 0x08, 0x04, 0x04, 0x04, 0x00}, // '7'
            {0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E, 0x00}, // '8'
            {0x0E, 0x11, 0x11, 0x1E, 0x10, 0x08, 0x06, 0x00}, // '9'
            {0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x01, 0x00}, // ':'
            {0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x01, 0x01}, // ';'
            {0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08, 0x00}, // '<'
            {0x00, 0x00, 0x1F, 0x00, 0x00, 0x1F, 0x00, 0x00}, // '='
            {0x01, 0x02, 0x04, 0x08, 0x04, 0x02, 0x01, 0x00}, // '>'
            {0x0E, 0x11, 0x10, 0x08, 0x04, 0x00, 0x04, 0x00}, // '?'
            {0x1E, 0x21, 0x2D, 0x2D, 0x3D, 0x01, 0x1E, 0x00}, // '@'
            {0x0E, 0x11, 0x1F, 0x11, 0x11, 0x11, 0x11, 0x00}, // 'A'
            {0x0F, 0x11, 0x0F, 0x11, 0x11, 0x11, 0x0F, 0x00}, // 'B'
            {0x0E, 0x11, 0x01, 0x01, 0x01, 0x11, 0x0E, 0x00}, // 'C'
            {0x0F, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0F, 0x00}, // 'D'
            {0x1F, 0x01, 0x07, 0x01, 0x01, 0x01, 0x1F, 0x00}, // 'E'
            {0x1F, 0x01, 0x07, 0x01, 0x01, 0x01, 0x01, 0x00}, // 'F'
            {0x1E, 0x01, 0x19, 0x11, 0x11, 0x11, 0x0E, 0x00}, // 'G'
            {0x11, 0x11, 0x1F, 0x11, 0x11, 0x11, 0x11, 0x00}, // 'H'
            {0x07, 0x02, 0x02, 0x02, 0x02, 0x02, 0x07, 0x00}, // 'I'
            {0x10, 0x10, 0x10, 0x10, 0x10, 0x11, 0x0E, 0x00}, // 'J'
            {0x11, 0x09, 0x07, 0x09, 0x11, 0x11, 0x11, 0x00}, // 'K'
            {0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x1F, 0x00}, // 'L'
            {0x11, 0x1B, 0x15, 0x11, 0x11, 0x11, 0x11, 0x00}, // 'M'
            {0x11, 0x13, 0x15, 0x19, 0x11, 0x11, 0x11, 0x00}, // 'N'
            {0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E, 0x00}, // 'O'
            {0x0F, 0x11, 0x0F, 0x01, 0x01, 0x01, 0x01, 0x00}, // 'P'
            {0x0E, 0x11, 0x11, 0x11, 0x11, 0x09, 0x16, 0x00}, // 'Q'
            {0x0F, 0x11, 0x0F, 0x11, 0x11, 0x11, 0x11, 0x00}, // 'R'
            {0x1E, 0x01, 0x0E, 0x10, 0x10, 0x11, 0x0E, 0x00}, // 'S'
            {0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x00}, // 'T'
            {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E, 0x00}, // 'U'
            {0x11, 0x11, 0x11, 0x11, 0x0A, 0x0A, 0x04, 0x00}, // 'V'
            {0x11, 0x11, 0x11, 0x11, 0x15, 0x1B, 0x11, 0x00}, // 'W'
            {0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11, 0x11, 0x00}, // 'X'
            {0x11, 0x0A, 0x04, 0x04, 0x04, 0x04, 0x04, 0x00}, // 'Y'
            {0x1F, 0x10, 0x08, 0x04, 0x02, 0x01, 0x1F, 0x00}, // 'Z'
            {0x07, 0x01, 0x01, 0x01, 0x01, 0x01, 0x07, 0x00}, // '['
            {0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10, 0x00}, // '\\'
            {0x07, 0x04, 0x04, 0x04, 0x04, 0x04, 0x07, 0x00}, // ']'
            {0x04, 0x0A, 0x11, 0x00, 0x00, 0x00, 0x00, 0x00}, // '^'
            {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F}, // '_'
            {0x01, 0x01, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00}, // '`'
            {0x00, 0x00, 0x0E, 0x10, 0x1E, 0x11, 0x1E, 0x00}, // 'a'
            {0x01, 0x01, 0x0D, 0x13, 0x11, 0x11, 0x0F, 0x00}, // 'b'
            {0x00, 0x00, 0x0E, 0x11, 0x01, 0x11, 0x0E, 0x00}, // 'c'
            {0x10, 0x10, 0x16, 0x19, 0x11, 0x11, 0x1E, 0x00}, // 'd'
            {0x00, 0x00, 0x0E, 0x11, 0x1F, 0x01, 0x1E, 0x00}, // 'e'
            {0x0C, 0x02, 0x0F, 0x02, 0x02, 0x02, 0x02, 0x00}, // 'f'
            {0x00, 0x00, 0x1E, 0x11, 0x11, 0x1E, 0x10, 0x0F}, // 'g'
            {0x01, 0x01, 0x0D, 0x13, 0x11, 0x11, 0x11, 0x00}, // 'h'
            {0x01, 0x00, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00}, // 'i'
            {0x10, 0x00, 0x10, 0x10, 0x10, 0x11, 0x11, 0x0E}, // 'j'
            {0x01, 0x01, 0x09, 0x05, 0x03, 0x05, 0x09, 0x00}, // 'k'
            {0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x02, 0x00}, // 'l'
            {0x00, 0x00, 0x0B, 0x15, 0x15, 0x11, 0x11, 0x00}, // 'm'
            {0x00, 0x00, 0x0F, 0x11, 0x11, 0x11, 0x11, 0x00}, // 'n'
            {0x00, 0x00, 0x0E, 0x11, 0x11, 0x11, 0x0E, 0x00}, // 'o'
            {0x00, 0x00, 0x0D, 0x13, 0x11, 0x0F, 0x01, 0x01}, // 'p'
            {0x00, 0x00, 0x16, 0x19, 0x11, 0x1E, 0x10, 0x10}, // 'q'
            {0x00, 0x00, 0x0D, 0x13, 0x01, 0x01, 0x01, 0x00}, // 'r'
            {0x00, 0x00, 0x1E, 0x01, 0x0E, 0x10, 0x0F, 0x00}, // 's'
            {0x02, 0x02, 0x07, 0x02, 0x02, 0x02, 0x04, 0x00}, // 't'
            {0x00, 0x00, 0x11, 0x11, 0x11, 0x11, 0x1E, 0x00}, // 'u'
            {0x00, 0x00, 0x11, 0x11, 0x11, 0x0A, 0x04, 0x00}, // 'v'
            {0x00, 0x00, 0x11, 0x11, 0x15, 0x15, 0x1E, 0x00}, // 'w'
            {0x00, 0x00, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x00}, // 'x'
            {0x00, 0x00, 0x11, 0x11, 0x11, 0x1E, 0x10, 0x0F}, // 'y'
            {0x00, 0x00, 0x1F, 0x08, 0x04, 0x02, 0x1F, 0x00}, // 'z'
            {0x0C, 0x02, 0x02, 0x01, 0x02, 0x02, 0x0C, 0x00}, // '{'
            {0x01, 0x01, 0x01, 0x00, 0x01, 0x01, 0x01, 0x00}, // '|'
            {0x03, 0x04, 0x04, 0x08, 0x04, 0x04, 0x03, 0x00}, // '}'
            {0x26, 0x19, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}  // '~'
    };

    /** Advance width of the space character; every other glyph is trimmed to its ink. */
    private static final int SPACE_ADVANCE = 3;

    /** Row bitmasks for ch, or null when the map font has no glyph for it. */
    private static int[] glyph(char ch) {
        int i = FONT_CHARS.indexOf(ch);
        return i < 0 ? null : FONT[i];
    }

    /** Ink width: one past the right-most set pixel column, at least one column. */
    private static int advance(int[] rows) {
        int last = 0;
        for (int row : rows) {
            for (int col = 0; col < 8; col++) {
                if ((row & (1 << col)) != 0 && col > last) {
                    last = col;
                }
            }
        }
        return last + 1;
    }

    /**
     * Blits a string with the map font at (x, y). Glyphs are 8 rows tall, columns are laid
     * left to right and separated by one blank column, and the run is clipped to the map.
     */
    private static void drawMapText(Graphics2D g, int x, int y, String text) {
        g.setColor(MAP_INK);
        int pen = x;
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            int[] rows = glyph(ch);
            int w;
            if (rows == null) {
                continue; // no glyph, the canvas skips the character entirely
            } else if (ch == ' ') {
                w = SPACE_ADVANCE;
            } else {
                w = advance(rows);
                for (int row = 0; row < 8; row++) {
                    for (int col = 0; col < w; col++) {
                        if ((rows[row] & (1 << col)) != 0
                                && pen + col >= 0 && pen + col < MAP_EDGE
                                && y + row >= 0 && y + row < MAP_EDGE) {
                            g.fillRect(pen + col, y + row, 1, 1);
                        }
                    }
                }
            }
            pen += w + 1;
        }
    }
}