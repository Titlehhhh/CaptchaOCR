package dev.captcha.gens;

import dev.captcha.Cg;
import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.util.Random;

/**
 * Clean-room reimplementation of <b>Supl1n/CaptchaGUI</b> (me.supl1na.captcha), the
 * click-the-block inventory captcha a joining player is shown.
 *
 * <p>The whole challenge is a 9-slot inventory window titled {@code "Captcha"} with a
 * single emerald block in it, carrying the display name {@code §a¡Click here!}. The block
 * is placed in a random slot between 1 and 7 inclusive, so slots 0 and 8 are never used.
 * Every other slot is empty. Clicking the block clears the check; clicking anything else
 * kicks the player with {@code "¡Nope!"}.
 *
 * <p><b>Mode: clean-room.</b> The upstream repository has no LICENSE file - the README,
 * the LICENSE and the plugin.yml all 404 - so there is no licence permitting a
 * line-by-line copy, and the house rule of this dataset is a clean-room reimplementation
 * wherever the licence forbids copying or none exists. The behaviour above was read from
 * the upstream source and rewritten independently; no upstream code, comments or
 * identifiers are carried over.
 *
 * <pre>
 *   src/main/java/me/supl1na/captcha/CaptchaListener.java#onPlayerJoin
 *   src/main/java/me/supl1na/captcha/CaptchaListener.java#onClick
 * </pre>
 *
 * <p>There is no image at all in this plugin - the challenge is delivered purely through
 * the inventory GUI - so the sample is a rendering of that GUI, the same way the other
 * GUI-delivered captchas in this dataset are rendered.
 */
public final class Supl1nCaptchaGui {

    private Supl1nCaptchaGui() {
    }

    public static final String PLUGIN = "CaptchaGUI";
    public static final String SRC = "me.supl1na.captcha.CaptchaListener#onPlayerJoin";

    /** The window title the listener passes to {@code Bukkit.createInventory}. */
    private static final String TITLE = "Captcha";

    /** The display name of the one item in the GUI, green section-sign colour code. */
    private static final String ITEM_NAME = "&a¡Click here!";

    /** The kick message the listener uses for a wrong click. */
    private static final String KICK = "¡Nope!";

    /**
     * The emerald block colour. Minecraft renders the top face of an emerald block as
     * #5DCB3E; the GUI swatch uses that as its base and the helper darkens the edges.
     */
    private static final Color EMERALD = new Color(0x5DCB3E);

    /**
     * One sample: the 9-slot GUI with the emerald block in its random slot.
     */
    public static final class ClickBlock implements Cg {

        private final Random r = new Random();
        /** getRandomNumberInRange(1, 7) - inclusive on both ends, so 0 and 8 never occur. */
        private final int slot = 1 + r.nextInt(7);
        private final BufferedImage img;

        public ClickBlock() {
            BufferedImage inv = McUi.inventory(9, 1, TITLE);
            Graphics2D g = Img.g2d(inv, true);
            // The item's name is a Minecraft tooltip, not slot text, so it is left out of the
            // swatch and carried by prompt() instead - the same split the other GUI
            // captchas in this dataset use.
            McUi.slotItem(g, 9, 1, slot, EMERALD, "");
            g.dispose();
            this.img = inv;
        }

        @Override
        public String plugin() {
            return PLUGIN;
        }

        @Override
        public String id() {
            return "clickblock";
        }

        /**
         * The slot the emerald block occupies - the only thing the player can act on.
         * It is a 0-based inventory index in 1..7.
         */
        @Override
        public String answer() {
            return String.valueOf(slot);
        }

        /**
         * The window title plus the item's display name, which together are the entire
         * instruction the player receives. The kick message is not shown to a player who
         * solves the captcha, so it is not part of the prompt.
         */
        @Override
        public String prompt() {
            return McUi.strip(TITLE) + " » " + McUi.strip(ITEM_NAME);
        }

        @Override
        public BufferedImage image() {
            return img;
        }

        /**
         * No band: this is not an OCR task.
         *
         * <p>The answer is a slot <i>index</i> - the emerald block sits in one of the
         * nine slots and the player has to click it. The frame carries no text that
         * carries the answer: the title bar says "Captcha" and the item's display name
         * is a hover tooltip, which never reaches the screen. There is nothing for a
         * recogniser to read, so there is no band to hand over.
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
}
