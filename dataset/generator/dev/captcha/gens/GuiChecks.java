package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.Color;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

/**
 * Two "click the right thing in an inventory" checks, reimplemented from scratch
 * after reading how each plugin assembles its GUI.
 *
 * <ul>
 *   <li>{@link ItemSlot} - me.yukun.captchas.gui.Captcha. The challenge is delivered
 *       entirely by the window title: the plugin substitutes the correct item's display
 *       name into {@code GUI.Name} before the inventory is created, so the title names the
 *       target and the player has to find it among 45 stacked items.</li>
 *   <li>{@link Wool} - org.china2b2t.captchalib.Main#onJoin. Fifty-four slots of wool
 *       where one block is a different colour from the other fifty-three.</li>
 * </ul>
 *
 * <p>Item names in Minecraft live in the tooltip only, never inside the slot texture, so
 * every swatch below is drawn with an empty label. The item itself is what distinguishes
 * one slot from another.
 */
public final class GuiChecks {

    private GuiChecks() {
    }

    /* ---------------------------------------------------------------- catalog */

    /** One line of the plugin's item list: a Bukkit material plus the text it is shown as. */
    static final class Mat {
        final String material;
        final String label;

        Mat(String material, String label) {
            this.material = material;
            this.label = label;
        }
    }

    /**
     * Prefix and suffix the plugin wraps around every configured label before the '&amp;'
     * codes are translated, so a label becomes {@code &c<label>&r} and therefore renders red.
     */
    static final String NAME_PREFIX = "&c";
    static final String NAME_SUFFIX = "&r";

    /** The full item list the plugin ships, 207 materials, in configuration order. */
    static final Mat[] CATALOG = {
            new Mat("ACTIVATOR_RAIL", "Activator Rail"),
            new Mat("ANVIL", "Anvil"),
            new Mat("APPLE", "Apple"),
            new Mat("ARROW", "Arrow"),
            new Mat("BAKED_POTATO", "Baked Potato"),
            new Mat("BEACON", "Beacon"),
            new Mat("BEDROCK", "Bedrock"),
            new Mat("BLAZE_POWDER", "Blaze Powder"),
            new Mat("BLAZE_ROD", "Blaze Rod"),
            new Mat("BONE", "Bone"),
            new Mat("BOOK", "Book"),
            new Mat("WRITABLE_BOOK", "Book and Quill"),
            new Mat("BOOKSHELF", "Bookshelf"),
            new Mat("BOW", "Bow"),
            new Mat("BOWL", "Bowl"),
            new Mat("BREAD", "Bread"),
            new Mat("BRICK", "Brick"),
            new Mat("BRICKS", "Brick Block"),
            new Mat("BRICK_STAIRS", "Brick Stairs"),
            new Mat("BROWN_MUSHROOM", "Brown Mushroom"),
            new Mat("BUCKET", "Bucket"),
            new Mat("CACTUS", "Cactus"),
            new Mat("CAKE", "Cake"),
            new Mat("CARROT_ON_A_STICK", "Carrot on a Stick"),
            new Mat("CAULDRON", "Cauldron"),
            new Mat("CHAINMAIL_BOOTS", "Chainmail Boots"),
            new Mat("CHAINMAIL_CHESTPLATE", "Chainmail Chestplate"),
            new Mat("CHAINMAIL_HELMET", "Chainmail Helmet"),
            new Mat("CHAINMAIL_LEGGINGS", "Chainmail Leggings"),
            new Mat("CHEST", "Chest"),
            new Mat("CLAY", "Clay Block"),
            new Mat("CLAY_BALL", "Clay Ball"),
            new Mat("COAL", "Coal"),
            new Mat("COAL_ORE", "Coal Ore"),
            new Mat("COBBLESTONE_WALL", "Cobblestone Wall"),
            new Mat("COBBLESTONE", "Cobblestone"),
            new Mat("COBBLESTONE_STAIRS", "Cobblestone Stairs"),
            new Mat("COMPASS", "Compass"),
            new Mat("COOKED_BEEF", "Cooked Beef"),
            new Mat("COOKED_CHICKEN", "Cooked Chicken"),
            new Mat("COOKIE", "Cookie"),
            new Mat("DAYLIGHT_DETECTOR", "Daylight Detector"),
            new Mat("DEAD_BUSH", "Dead Bush"),
            new Mat("DETECTOR_RAIL", "Detector Rail"),
            new Mat("DIAMOND", "Diamond"),
            new Mat("DIAMOND_AXE", "Diamond Axe"),
            new Mat("DIAMOND_BLOCK", "Diamond Block"),
            new Mat("DIAMOND_BOOTS", "Diamond Boots"),
            new Mat("DIAMOND_CHESTPLATE", "Diamond Chestplate"),
            new Mat("DIAMOND_HELMET", "Diamond Helmet"),
            new Mat("DIAMOND_HOE", "Diamond Hoe"),
            new Mat("DIAMOND_LEGGINGS", "Diamond Leggings"),
            new Mat("DIAMOND_ORE", "Diamond Ore"),
            new Mat("DIAMOND_PICKAXE", "Diamond Pickaxe"),
            new Mat("DIAMOND_SHOVEL", "Diamond Shovel"),
            new Mat("DIAMOND_SWORD", "Diamond Sword"),
            new Mat("REPEATER", "Repeater"),
            new Mat("DIRT", "Dirt"),
            new Mat("DISPENSER", "Dispenser"),
            new Mat("DRAGON_EGG", "Dragon Egg"),
            new Mat("DROPPER", "Dropper"),
            new Mat("EGG", "Egg"),
            new Mat("EMERALD", "Emerald"),
            new Mat("EMERALD_BLOCK", "Emerald Block"),
            new Mat("EMERALD_ORE", "Emerald Ore"),
            new Mat("MAP", "Empty Map"),
            new Mat("ENCHANTED_BOOK", "Enchanted Book"),
            new Mat("ENCHANTING_TABLE", "Enchantment Table"),
            new Mat("ENDER_CHEST", "Ender Chest"),
            new Mat("ENDER_PEARL", "Ender Pearl"),
            new Mat("END_PORTAL_FRAME", "End Portal"),
            new Mat("END_STONE", "End Stone"),
            new Mat("EXPERIENCE_BOTTLE", "Bottle of Enchanting"),
            new Mat("TNT_MINECART", "Minecart with TNT"),
            new Mat("ENDER_EYE", "Eye of Ender"),
            new Mat("FEATHER", "Feather"),
            new Mat("FERMENTED_SPIDER_EYE", "Fermented Spider Eye"),
            new Mat("FIRE_CHARGE", "Fire Charge"),
            new Mat("FIREWORK_ROCKET", "Firework Rocket"),
            new Mat("FIREWORK_STAR", "Firework Star"),
            new Mat("FISHING_ROD", "Fishing Rod"),
            new Mat("FLINT", "Flint"),
            new Mat("FLINT_AND_STEEL", "Flint and Steel"),
            new Mat("FURNACE", "Furnace"),
            new Mat("GHAST_TEAR", "Ghast Tear"),
            new Mat("GLASS", "Glass"),
            new Mat("GLASS_BOTTLE", "Glass Bottle"),
            new Mat("GLOWSTONE", "Glowstone Block"),
            new Mat("GLOWSTONE_DUST", "Glowstone Dust"),
            new Mat("GOLDEN_AXE", "Golden Axe"),
            new Mat("GOLD_BLOCK", "Gold Block"),
            new Mat("GOLDEN_BOOTS", "Golden Boots"),
            new Mat("GOLDEN_CHESTPLATE", "Golden Chestplate"),
            new Mat("GOLDEN_HELMET", "Golden Helmet"),
            new Mat("GOLDEN_HOE", "Golden Hoe"),
            new Mat("GOLD_INGOT", "Gold Ingot"),
            new Mat("GOLDEN_LEGGINGS", "Golden Leggings"),
            new Mat("GOLD_NUGGET", "Gold Nugget"),
            new Mat("GOLD_ORE", "Gold Ore"),
            new Mat("GOLDEN_PICKAXE", "Golden Pickaxe"),
            new Mat("GOLDEN_SHOVEL", "Golden Shovel"),
            new Mat("GOLDEN_SWORD", "Golden Sword"),
            new Mat("GOLDEN_APPLE", "Golden Apple"),
            new Mat("GOLDEN_CARROT", "Golden Carrot"),
            new Mat("GRASS", "Grass"),
            new Mat("GRAVEL", "Gravel"),
            new Mat("COOKED_PORKCHOP", "Cooked Porkchop"),
            new Mat("HOPPER", "Hopper"),
            new Mat("HOPPER_MINECART", "Minecart with Hopper"),
            new Mat("ICE", "Ice"),
            new Mat("IRON_AXE", "Iron Axe"),
            new Mat("IRON_BLOCK", "Iron Block"),
            new Mat("IRON_BOOTS", "Iron Boots"),
            new Mat("IRON_CHESTPLATE", "Iron Chestplate"),
            new Mat("IRON_DOOR", "Iron Door"),
            new Mat("IRON_HELMET", "Iron Helmet"),
            new Mat("IRON_HOE", "Iron Hoe"),
            new Mat("IRON_INGOT", "Iron Ingot"),
            new Mat("IRON_LEGGINGS", "Iron Leggings"),
            new Mat("IRON_ORE", "Iron Ore"),
            new Mat("IRON_PICKAXE", "Iron Pickaxe"),
            new Mat("IRON_SHOVEL", "Iron Shovel"),
            new Mat("IRON_SWORD", "Iron Sword"),
            new Mat("ITEM_FRAME", "Item Frame"),
            new Mat("JACK_O_LANTERN", "Jack o' Lantern"),
            new Mat("JUKEBOX", "Jukebox"),
            new Mat("LADDER", "Ladder"),
            new Mat("LAPIS_BLOCK", "Lapis Lazuli Block"),
            new Mat("LAPIS_ORE", "Lapis Lazuli Ore"),
            new Mat("LAVA_BUCKET", "Bucket of Lava"),
            new Mat("LEAD", "Lead"),
            new Mat("LEATHER", "Leather"),
            new Mat("LEATHER_BOOTS", "Leather Boots"),
            new Mat("LEATHER_CHESTPLATE", "Leather Chestplate"),
            new Mat("LEATHER_HELMET", "Leather Helmet"),
            new Mat("LEATHER_LEGGINGS", "Leather Leggings"),
            new Mat("LEVER", "Lever"),
            new Mat("MAGMA_CREAM", "Magma Cream"),
            new Mat("MELON_SLICE", "Melon Slice"),
            new Mat("MELON", "Melon Block"),
            new Mat("MELON_SEEDS", "Melon Seeds"),
            new Mat("MILK_BUCKET", "Bucket of Milk"),
            new Mat("MINECART", "Minecart"),
            new Mat("MOSSY_COBBLESTONE", "Mossy Cobblestone"),
            new Mat("MUSHROOM_STEW", "Mushroom Soup"),
            new Mat("NAME_TAG", "Name Tag"),
            new Mat("NETHER_BRICK", "Nether Brick Block"),
            new Mat("NETHER_BRICK_STAIRS", "Nether Brick Stairs"),
            new Mat("NETHER_STAR", "Nether Star"),
            new Mat("NETHERRACK", "Netherrack"),
            new Mat("NOTE_BLOCK", "Note Block"),
            new Mat("OBSIDIAN", "Obsidian"),
            new Mat("PAINTING", "Painting"),
            new Mat("PAPER", "Paper"),
            new Mat("POISONOUS_POTATO", "Poisonous Potato"),
            new Mat("POWERED_RAIL", "Powered Rail"),
            new Mat("PUMPKIN", "Pumpkin"),
            new Mat("PUMPKIN_PIE", "Pumpkin Pie"),
            new Mat("PUMPKIN_SEEDS", "Pumpkin Seeds"),
            new Mat("QUARTZ_BLOCK", "Quartz Block"),
            new Mat("NETHER_QUARTZ_ORE", "Quartz Ore"),
            new Mat("QUARTZ_STAIRS", "Quartz Stairs"),
            new Mat("RAIL", "Rails"),
            new Mat("BEEF", "Raw Beef"),
            new Mat("CHICKEN", "Raw Chicken"),
            new Mat("RED_MUSHROOM", "Red Mushroom"),
            new Mat("REDSTONE", "Redstone Dust"),
            new Mat("REDSTONE_BLOCK", "Redstone Block"),
            new Mat("COMPARATOR", "Redstone Comparator"),
            new Mat("REDSTONE_ORE", "Redstone Ore"),
            new Mat("ROTTEN_FLESH", "Rotten Flesh"),
            new Mat("SADDLE", "Saddle"),
            new Mat("SAND", "Sand"),
            new Mat("SHEARS", "Shears"),
            new Mat("SLIME_BALL", "Slime Ball"),
            new Mat("SNOWBALL", "Snow Ball"),
            new Mat("SNOW_BLOCK", "Snow Block"),
            new Mat("SOUL_SAND", "Soul Sand"),
            new Mat("SPIDER_EYE", "Spider Eye"),
            new Mat("SPONGE", "Sponge"),
            new Mat("STICK", "Stick"),
            new Mat("STONE", "Stone"),
            new Mat("STONE_AXE", "Stone Axe"),
            new Mat("STONE_BUTTON", "Stone Button"),
            new Mat("STONE_HOE", "Stone Hoe"),
            new Mat("STONE_PICKAXE", "Stone Pickaxe"),
            new Mat("STONE_SHOVEL", "Stone Shovel"),
            new Mat("STONE_SWORD", "Stone Sword"),
            new Mat("STRING", "String"),
            new Mat("SUGAR", "Sugar"),
            new Mat("SUGAR_CANE", "Sugar Cane"),
            new Mat("TNT", "TNT"),
            new Mat("TORCH", "Torch"),
            new Mat("TRIPWIRE_HOOK", "Tripwire Hook"),
            new Mat("VINE", "Vine"),
            new Mat("CLOCK", "Clock"),
            new Mat("WATER_BUCKET", "Bucket of Water"),
            new Mat("LILY_PAD", "Lily Pad"),
            new Mat("COBWEB", "Cobweb"),
            new Mat("WHEAT", "Wheat"),
            new Mat("WOODEN_AXE", "Wooden Axe"),
            new Mat("WOODEN_HOE", "Wooden Hoe"),
            new Mat("WOODEN_PICKAXE", "Wooden Pickaxe"),
            new Mat("WOODEN_SHOVEL", "Wooden Shovel"),
            new Mat("WOODEN_SWORD", "Wooden Sword"),
            new Mat("CRAFTING_TABLE", "Crafting Table"),
            new Mat("WRITTEN_BOOK", "Written Book")};

    /* ---------------------------------------------------------------- helpers */

    /**
     * Fills the window the way the plugin does: shuffle the whole item list, then read the
     * first {@code size} entries. Because the list is walked without replacement, no two
     * slots ever hold the same material.
     */
    private static Mat[] deal(Random r, int size) {
        List<Mat> pool = new ArrayList<>(List.of(CATALOG));
        Collections.shuffle(pool, r);
        return pool.subList(0, size).toArray(new Mat[0]);
    }

    /** Stable pseudo-colour standing in for a material's block texture. */
    private static Color swatch(String key) {
        int h = key.hashCode();
        return new Color(70 + Math.abs(h % 170), 70 + Math.abs((h / 7) % 170),
                70 + Math.abs((h / 13) % 170));
    }

    /**
     * Colours for a dealt hand. Two different materials that happen to hash to the same
     * triple are nudged apart so that no slot is ever a perfect visual twin of another.
     */
    private static Color[] swatches(Mat[] dealt) {
        Color[] out = new Color[dealt.length];
        List<Integer> taken = new ArrayList<>(dealt.length);
        for (int i = 0; i < dealt.length; i++) {
            Color c = swatch(dealt[i].material);
            for (int bump = 1; taken.contains(c.getRGB()); bump++) {
                c = swatch(dealt[i].material + '#' + bump);
            }
            taken.add(c.getRGB());
            out[i] = c;
        }
        return out;
    }

    /* ---------------------------------------------------------------- chrome */

    /** Window panel geometry, mirrored here so the title strip can be re-laid out. */
    private static final int SLOT = 18;
    private static final int PAD = 12;
    private static final int TITLE_H = 24;
    private static final Color PANEL_BG = new Color(0xC6, 0xC6, 0xC6);
    private static final Color PANEL_EDGE = new Color(0x55, 0x55, 0x55);

    /**
     * The point size the title is drawn at: the largest one that still fits into the
     * strip.
     *
     * <p>Split out of {@link #drawTitle} so that the band of the title can be placed
     * with the very size the title is drawn with.
     *
     * <p>The size comes from {@link McUi#titleSize}, the helper the shared inventory
     * chrome uses, so the two cannot drift apart.
     */
    private static float titleSize(Graphics2D g, String text, int w) {
        return McUi.titleSize(g, text, w);
    }

    /**
     * Paints the window title at a size that fits the panel.
     *
     * <p>Item names here are long - "Captcha: Chainmail Chestplate" is already wider than
     * a 186px window - and a title clipped by the panel edge would hide the very text the
     * challenge is built on. So the strip is cleared back to bare panel and the title is
     * written again at the largest size that fits, which is what the client does when a
     * GUI name is wider than the window.
     */
    private static void drawTitle(BufferedImage panel, int cols, String text) {
        Graphics2D g = Img.g2d(panel, true);
        int w = cols * SLOT + PAD * 2;
        g.setColor(PANEL_BG);
        g.fillRect(0, 0, w, TITLE_H);
        g.setColor(PANEL_EDGE);
        g.drawLine(0, TITLE_H, w, TITLE_H);
        McUi.drawColored(g, McUi.codes(text), PAD, 16, titleSize(g, text, w), true);
        g.dispose();
    }

    /**
     * Chat window width that keeps the challenge line whole. A CJK line is roughly twice
     * as wide as a Latin one at the same point size, so a fixed width would guillotine the
     * tail of the join banner.
     */
    private static int chatWidth(String text) {
        return McUi.chatWidth(text, 14f, 400);
    }

    /* ============================================================ Yukun99/Captchas */

    /**
     * <b>me.yukun.captchas</b> - a plain anti-autoclick check. {@code GUI.Size} is 45 (five
     * rows) out of the box and every one of those 45 slots is stacked with a different item.
     * One index is drawn up front and becomes the target; the check itself is nothing more
     * than comparing the raw slot of a click against that index, so the item a player
     * actually clicks never matters. Closing the window re-opens it a tick later, which is
     * how the plugin keeps the window on screen.
     *
     * <p>The window title is what identifies the target: the correct item's own display
     * name - {@code &c<label>&r} - is substituted into {@code GUI.Name} before the
     * inventory is created, so it is printed on the title bar of the very window the player
     * has to search. The answer is therefore readable straight off the screenshot.
     *
     * <pre>
     *   me.yukun.captchas.gui.Captcha#slot        - RANDOM.nextInt(Config.getGUISize())
     *   me.yukun.captchas.config.Config#getGUI   - GUI.Name with %item% filled in
     *   me.yukun.captchas.config.Items#getCaptchaItems
     *   me.yukun.captchas.gui.CaptchaListener#captchaClickEvent - raw slot compare
     * </pre>
     */
    public static final class ItemSlot implements Cg {

        /** GUI.Size default: 45 items, i.e. a five row window. */
        static final int SIZE = 45;
        static final int COLS = 9;
        static final int ROWS = 5;

        /** Duration.Time default, and the FirstJoin.OverrideDuration value for new players. */
        static final int DURATION = 100;
        static final int FIRST_JOIN_DURATION = 30;

        private static final String PREFIX = "&bCapt&echas&f >> &7";

        private final int targetSlot;
        private final Mat target;
        private final String chat;
        private final BufferedImage img;
        private final int[] roi;

        public ItemSlot() {
            Random r = new Random();
            Mat[] dealt = deal(r, SIZE);
            // Drawn before the window is filled, and completely independent of it.
            targetSlot = r.nextInt(SIZE);
            target = dealt[targetSlot];
            // A first-time player is given the shorter override and skips the warning.
            chat = PREFIX + "Captcha triggered! Please click the right item in "
                    + (r.nextBoolean() ? FIRST_JOIN_DURATION : DURATION) + " seconds.";

            Color[] colours = swatches(dealt);
            BufferedImage inv = McUi.inventory(COLS, ROWS, "");
            String title = guiName(target);
            drawTitle(inv, COLS, title);
            Graphics2D g = Img.g2d(inv, true);
            for (int i = 0; i < SIZE; i++) {
                // No label: the display name only ever appears in the hover tooltip.
                McUi.slotItem(g, COLS, ROWS, i, colours[i], "");
            }
            g.dispose();
            BufferedImage scene = McUi.scene(chat, r, chatWidth(chat));
            img = McUi.over(scene, inv);
            roi = titleBand(scene, inv, title, target.label);
        }

        /**
         * The band of the item name in the title bar of the window.
         *
         * <p>The chat line the plugin sends does not name the item at all - it only says
         * that a captcha was triggered - so the title bar is the one place where the
         * answer is written down. The band is the item's display name inside it, at the
         * size the title is actually drawn with.
         */
        private static int[] titleBand(BufferedImage scene, BufferedImage inv,
                                       String title, String label) {
            int w = COLS * SLOT + PAD * 2;
            Graphics2D g = TextBand.measure();
            try {
                int size = Math.round(titleSize(g, title, w));
                TextBand.Hit hit = TextBand.locate(g, McUi.codes(title), label, size);
                if (hit == null) {
                    return null;
                }
                g.setFont(Img.font("Monospaced",
                        hit.bold() ? java.awt.Font.BOLD : java.awt.Font.PLAIN, size));
                FontMetrics fm = g.getFontMetrics();
                // the window is centred on the chat scene, and the chat scene is the base
                int invX = (scene.getWidth() - inv.getWidth()) / 2;
                int invY = scene.getHeight() - 10;
                return TextBand.box(invX + PAD + hit.x(), invY + 16, fm.getAscent(),
                        fm.getDescent(), fm.stringWidth(label));
            } finally {
                g.dispose();
            }
        }

        /** GUI.Name with %item% already replaced, exactly as the plugin builds it. */
        static String guiName(Mat m) {
            return "&b&lCaptcha:&r " + NAME_PREFIX + m.label + NAME_SUFFIX;
        }

        @Override
        public String plugin() {
            return "Yukun99/Captchas";
        }

        @Override
        public String id() {
            return "itemslot";
        }

        /**
         * The target item's label. The full display name the plugin stores on the stack is
         * {@code &c<label>&r}, and that coloured form is what the title bar shows.
         */
        @Override
        public String answer() {
            return target.label;
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * The band of the item's display name in the title bar of the window.
         *
         * <p>The frame is a chat log with a 45 slot window on top of it, and the name of
         * the item to click is written into the window's title - the plugin substitutes
         * it into {@code GUI.Name} before the inventory is created. The band is that
         * name, at the size the title is drawn with, and nothing else of the frame.
         */
        @Override
        public int[] roi() {
            return roi;
        }

        @Override
        public String source() {
            return "me.yukun.captchas.gui.Captcha";
        }

        @Override
        public String prompt() {
            return McUi.strip(chat);
        }
    }

    /* ========================================================= China2B2T/Captcha */

    /**
     * <b>org.china2b2t.captchalib</b> - the join-time check. After the plugin holds the
     * main thread for one second and then waits a further forty ticks, a full six row
     * window is opened; a single random index gets lime wool, every other slot gets red
     * wool. The names attached to the two stacks differ, but that difference is only ever
     * shown on hover - on screen the challenge is one off-colour block in a wall of 53.
     *
     * <p>Worth keeping in mind about the click handler: the misclick counter is declared
     * inside the handler, so it is reset to one on every single event and the three-strike
     * branch below it can never be taken. No amount of wrong clicking ever reaches the
     * kick; the item alone decides the outcome.
     *
     * <pre>
     *   org.china2b2t.captchalib.Main#onJoin  - 54 slot window, r.nextInt(54)
     *   org.china2b2t.captchalib.Main#onClick - display name compare, local counter
     * </pre>
     */
    public static final class Wool implements Cg {

        static final int SLOTS = 54;
        static final int COLS = 9;
        static final int ROWS = 6;

        /** Minecraft's own dye colours for the two wool blocks. */
        static final Color LIME = new Color(0x80, 0xC7, 0x1F);
        static final Color RED = new Color(0xB0, 0x2E, 0x26);

        /** The join banner line that introduces the check, verbatim. */
        static final String BANNER = "&6首先，我们要确认您是不是机器人 :) "
                + "请您完成验证码即可游玩";

        private final int targetSlot;
        private final BufferedImage img;

        public Wool() {
            Random r = new Random();
            targetSlot = r.nextInt(SLOTS);

            BufferedImage inv = McUi.inventory(COLS, ROWS, "");
            drawTitle(inv, COLS, "&6&lChina2B2T Captcha");
            Graphics2D g = Img.g2d(inv, true);
            for (int j = 0; j < SLOTS; j++) {
                // The two stacks are told apart by their tooltip name, not by any text
                // drawn into the slot, so both are rendered without a label.
                McUi.slotItem(g, COLS, ROWS, j, j == targetSlot ? LIME : RED, "");
            }
            g.dispose();
            img = McUi.over(McUi.scene(BANNER, r, chatWidth(BANNER)), inv);
        }

        @Override
        public String plugin() {
            return "China2B2T/Captcha";
        }

        @Override
        public String id() {
            return "wool";
        }

        @Override
        public String answer() {
            return "LIME_WOOL";
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * No band: the answer is a block, not a text.
         *
         * <p>The window asks the player to spot the one lime wool among 53 red ones.
         * The frame carries no word that names the answer - the title bar only says
         * "China2B2T Captcha" - so there is no text band to hand over.
         */
        @Override
        public int[] roi() {
            return null;
        }

        @Override
        public String source() {
            return "org.china2b2t.captchalib.Main#onJoin";
        }

        @Override
        public String prompt() {
            return BANNER;
        }
    }
}