package dev.captcha;

import java.awt.AlphaComposite;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.GradientPaint;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;

/**
 * Renders the in-game surfaces an anti-bot plugin uses to deliver a challenge:
 * chat, actionbar, titles and inventory GUIs. Non-image captchas (sneak, jump,
 * slot, equation ...) are delivered through these surfaces, so their samples are
 * re-rendered here rather than being skipped.
 */
public final class McUi {

    /** Minecraft section-sign colour codes used by the plugins' message strings. */
    public enum Mc {
        BLACK('0', 0x000000), DARK_BLUE('1', 0x0000AA), DARK_GREEN('2', 0x00AA00),
        DARK_AQUA('3', 0x00AAAA), DARK_RED('4', 0xAA0000), DARK_PURPLE('5', 0xAA00AA),
        GOLD('6', 0xFFAA00), GRAY('7', 0xAAAAAA), DARK_GRAY('8', 0x555555),
        BLUE('9', 0x5555FF), GREEN('a', 0x55FF55), AQUA('b', 0x55FFFF),
        RED('c', 0xFF5555), LIGHT_PURPLE('d', 0xFF55FF), YELLOW('e', 0xFFFF55),
        WHITE('f', 0xFFFFFF);

        public final char code;
        public final int rgb;

        Mc(char code, int rgb) {
            this.code = code;
            this.rgb = rgb;
        }

        static Mc byCode(char c) {
            for (Mc m : values()) {
                if (m.code == Character.toLowerCase(c)) {
                    return m;
                }
            }
            return null;
        }
    }

    private McUi() {
    }

    /** Replaces '&amp;'-style codes with '&amp;§'-style codes so MC colours resolve. */
    public static String codes(String s) {
        return s == null ? "" : s.replace("&", "§");
    }

    /**
     * Strips the formatting codes: the sixteen colours and the style codes
     * {@code k} (obfuscated), {@code l} (bold), {@code m} (strikethrough), {@code n}
     * (underline) and {@code r} (reset).
     */
    public static String strip(String s) {
        return s == null ? "" : s.replaceAll("[§&][0-9a-fk-orA-FK-OR]", "");
    }

    /**
     * Renders text with Minecraft section-sign colours onto g at (x,y).
     *
     * <p>Returns the x the pen ended at.
     *
     * <p><b>The pen advances by the measured width of every run.</b> That is the whole
     * point of splitting a line into colour runs: {@code "&7Tries Left: &f3"} is three
     * runs that sit next to each other on the screen, not three runs stacked on the
     * same pixels. An earlier version of this method only moved the pen by half a
     * space per colour code, which drew every run of a line on top of the others - the
     * chat scenes came out as unreadable jumbles, and an OCR model measured on them
     * could not do better than chance.
     *
     * <p>The style codes are handled too: {@code &l} switches to the bold face,
     * {@code &r} resets the colour to white, and the decorative ones
     * ({@code &k}, {@code &m}, {@code &n}) are consumed rather than drawn literally.
     */
    public static int drawColored(Graphics2D g, String text, int x, int y, float size, boolean shadow) {
        int px = Math.round(size);
        boolean bold = false;
        int cx = x;
        Color cur = Color.WHITE;
        StringBuilder buf = new StringBuilder();
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if ((ch == '§' || ch == '&') && i + 1 < text.length()) {
                char code = Character.toLowerCase(text.charAt(i + 1));
                Mc m = Mc.byCode(code);
                if (m != null) {
                    cx = flush(g, buf, cx, y, cur, shadow, bold, px);
                    cur = new Color(m.rgb);
                    i++;
                    continue;
                }
                if (code == 'l') {
                    cx = flush(g, buf, cx, y, cur, shadow, bold, px);
                    bold = true;
                    i++;
                    continue;
                }
                if (code == 'r') {
                    cx = flush(g, buf, cx, y, cur, shadow, bold, px);
                    cur = Color.WHITE;
                    bold = false;
                    i++;
                    continue;
                }
                if (code == 'k' || code == 'm' || code == 'n') {
                    // decorative codes change nothing in a still image, but they must
                    // not be drawn as literal characters
                    cx = flush(g, buf, cx, y, cur, shadow, bold, px);
                    i++;
                    continue;
                }
            }
            buf.append(ch);
        }
        cx = flush(g, buf, cx, y, cur, shadow, bold, px);
        return cx;
    }

    /**
     * Draws one colour run and returns the x the pen has to continue at.
     */
    private static int flush(Graphics2D g, StringBuilder buf, int x, int y, Color c,
                              boolean shadow, boolean bold, int size) {
        if (buf.length() == 0) {
            return x;
        }
        String s = buf.toString();
        g.setFont(Img.font("Monospaced", bold ? java.awt.Font.BOLD : java.awt.Font.PLAIN, size));
        int w = g.getFontMetrics().stringWidth(s);
        if (shadow) {
            g.setColor(new Color(0x3F, 0x3F, 0x3F));
            g.drawString(s, x + 2, y + 2);
        }
        g.setColor(c);
        g.drawString(s, x, y);
        buf.setLength(0);
        return x + w;
    }

    /** The dark translucent backdrop the client draws behind chat. */
    public static BufferedImage backdrop(int w, int h) {
        BufferedImage img = Img.rgb(w, h);
        Graphics2D g = Img.g2d(img, true);
        g.setPaint(new GradientPaint(0, 0, new Color(0x10, 0x10, 0x14, 235), 0, h, new Color(0x00, 0x00, 0x00, 190)));
        g.fillRect(0, 0, w, h);
        g.dispose();
        return img;
    }

    /** A full "chat window" scene of a given size. */
    public static BufferedImage chat(int w, int h) {
        BufferedImage img = backdrop(w, h);
        return img;
    }

    /** The inventory GUI chrome: panel, title strip, slot grid. */
    public static BufferedImage inventory(int cols, int rows, String title) {
        int slot = 18;
        int pad = 12;
        int w = cols * slot + pad * 2;
        int h = rows * slot + pad * 2 + 26;
        BufferedImage img = Img.rgb(w, h);
        Graphics2D g = Img.g2d(img, true);
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setColor(new Color(0xC6, 0xC6, 0xC6));
        g.fillRect(0, 0, w, h);
        g.setColor(new Color(0x55, 0x55, 0x55));
        g.setStroke(new BasicStroke(1f));
        g.drawRect(0, 0, w - 1, h - 1);
        g.drawLine(0, 24, w, 24);
        // the title is written at the largest size that fits the panel, so that a name
        // wider than the window is not clipped - the client elides it the same way
        drawColored(g, codes(title), pad, 16, titleSize(g, title, w), true);
        g.setComposite(AlphaComposite.SrcOver);
        for (int r = 0; r < rows; r++) {
            for (int c = 0; c < cols; c++) {
                int x = pad + c * slot;
                int y = 26 + pad + r * slot;
                g.setColor(new Color(0x8B, 0x8B, 0x8B));
                g.fillRect(x, y, slot, slot);
                g.setColor(new Color(0x37, 0x37, 0x37));
                g.drawRect(x, y, slot - 1, slot - 1);
                g.drawLine(x, y, x + slot - 1, y + slot - 1);
                g.drawLine(x + slot - 1, y, x, y + slot - 1);
            }
        }
        g.dispose();
        return img;
    }

    /** Fills an inventory slot with a simple shaded block-ish swatch + item name. */
    public static void slotItem(Graphics2D g, int cols, int rows, int index, Color c, String label) {
        int slot = 18;
        int pad = 12;
        int col = index % cols;
        int row = index / cols;
        int x = pad + col * slot;
        int y = 26 + pad + row * slot;
        int m = 3;
        g.setColor(c);
        g.fillRect(x + m, y + m, slot - m * 2, slot - m * 2);
        g.setColor(new Color(c.getRed() / 2, c.getGreen() / 2, c.getBlue() / 2));
        g.fillRect(x + m, y + slot - m - 5, slot - m * 2, 5);
        g.fillRect(x + slot - m - 5, y + m, 5, slot - m * 2);
        g.setColor(new Color(255, 255, 255, 70));
        g.drawLine(x + m, y + m, x + slot - m - 1, y + m);
        if (label != null && !label.isEmpty()) {
            g.setFont(Img.font("Monospaced", java.awt.Font.PLAIN, 11));
            g.setColor(Color.BLACK);
            g.drawString(label, x + m + 1, y + slot - m - 1);
            g.setColor(Color.WHITE);
            g.drawString(label, x + m, y + slot - m - 2);
        }
    }

    /* --------------------------------------------------------------- context */

    /** Random-ish player names used to give the chat backdrop some variation. */
    private static final String[] NAMES = {
            "Steve", "Alex", "Notch", "Herobrine", "CreeperKing", "DiamondDan", "xX_Steve_Xx",
            "Player", "Griefer99", "Redstoner", "Enderman", "Piglin", "Axolotl", "Pandaslayer",
            "Steve_2011", "qwe123", "NoobMaster", "BuildCraft", "MinerPro", "CreeperZombie"};

    private static final String[] FILLER = {
            "&7[Server] &fJoin the server on &bplay.example.net",
            "&7[Server] &fSet your locale to your language!",
            "&a>> &7Welcome back, %name%!",
            "&7Remember to vote for the server!",
            "&c[MOTD] &7Season VI has started.",
            "&7Type &f/help &7for a list of commands.",
            "&b[Join] &f%name% joined the game",
            "&7Click &fhere &7to claim your daily reward."};

    /**
     * Renders the challenge line underneath a few lines of ordinary server chat.
     *
     * <p>Several XProtect challenges (sneak, jump, drop) are a fixed message with no random
     * component at all, so 100 renders of the challenge alone would be byte-identical. The
     * surrounding chat is what actually differs between two real screenshots of the plugin,
     * so it is what carries the per-sample variation here. The challenge line itself stays
     * exactly as the plugin emits it.
     *
     * <p><b>The frame is widened when the message needs it.</b> The plugins' own messages
     * are 55 to 78 characters, which is 430 to 600 pixels at the chat font - more than the
     * 420 pixel frame the callers ask for. A frame that is too narrow does not merely look
     * wrong, it <b>cuts the answer off the picture</b>: the code the player has to type is
     * simply not there any more, and no recogniser can recover it. The real client wraps
     * the message onto a second row; here the frame is widened instead, which keeps the
     * answer on the first row and leaves the pen walk - and therefore every text band
     * computed from it - unchanged.
     */
    public static BufferedImage scene(String challenge, java.util.Random r, int width) {
        int lines = 2 + r.nextInt(3);
        String[] pre = new String[lines];
        for (int i = 0; i < lines; i++) {
            String t = FILLER[r.nextInt(FILLER.length)];
            pre[i] = t.replace("%name%", NAMES[r.nextInt(NAMES.length)]);
        }
        int lineH = 22;
        int w = Math.max(width, chatWidth(challenge, 14f, width));
        int h = 16 + lineH * (lines + 1) + 10;
        BufferedImage img = backdrop(w, h);
        Graphics2D g = Img.g2d(img, true);
        int y = 24;
        for (String l : pre) {
            drawColored(g, codes(l), 6, y, 14f, true);
            y += lineH;
        }
        drawColored(g, codes(challenge), 6, y, 14f, true);
        g.dispose();
        return img;
    }

    /**
     * The width a chat line needs so that it is not cut off by the frame.
     */
    public static int chatWidth(String text, float size, int min) {
        Graphics2D g = Img.g2d(Img.rgb(1, 1), true);
        int w = Math.round(codedWidth(g, text, size)) + 14;
        g.dispose();
        return Math.max(min, w);
    }

    /**
     * Width a coloured string will occupy: the glyphs, plus a half space for every
     * colour code, which is what the pen adds when it steps over a code.
     */
    public static float codedWidth(Graphics2D g, String text, float size) {
        java.awt.Font font = Img.font("Monospaced", java.awt.Font.PLAIN, Math.round(size));
        java.awt.FontMetrics fm = g.getFontMetrics(font);
        String coded = codes(text);
        String plain = strip(coded);
        int codes = (coded.length() - plain.length()) / 2;
        return fm.stringWidth(plain) + codes * (fm.charWidth(' ') / 2f);
    }

    /**
     * The largest size at which a window title fits the panel.
     *
     * <p>The titles the plugins use are 18 to 33 characters, which is 150 to 280 pixels -
     * wider than the 186 pixel inventory window. A title that is clipped by the panel edge
     * hides the very text the challenge is built on ("Click on the color Blu" instead of
     * "Blue"), so the title is written at the largest size that fits, which is what the
     * client does when a GUI name is wider than the window.
     */
    public static float titleSize(Graphics2D g, String text, int w) {
        float size = 13f;
        while (size > 5f && codedWidth(g, text, size) > w - 24) {
            size -= 0.5f;
        }
        return size;
    }

    /** Stacks a rendered GUI on top of a chat scene, the way the client draws it. */
    public static BufferedImage over(BufferedImage base, BufferedImage top) {
        int w = Math.max(base.getWidth(), top.getWidth() + 40);
        int h = base.getHeight() + top.getHeight() + 20;
        BufferedImage out = Img.rgb(w, h);
        Graphics2D g = Img.g2d(out, true);
        g.drawImage(base, 0, 0, null);
        g.drawImage(top, (w - top.getWidth()) / 2, base.getHeight() - 10, null);
        g.dispose();
        return out;
    }

    /**
     * Same as {@link #scene} but the challenge line is split so that one fragment can be
     * drawn in an arbitrary RGB colour - XProtect's colour captcha replaces the word
     * "THIS" with the colour itself, which is not one of the 16 section-sign codes.
     */
    public static BufferedImage sceneSplit(String before, String literal, Color literalColor,
                                           String after, java.util.Random r, int width) {
        int lines = 2 + r.nextInt(3);
        String[] pre = new String[lines];
        for (int i = 0; i < lines; i++) {
            String t = FILLER[r.nextInt(FILLER.length)];
            pre[i] = t.replace("%name%", NAMES[r.nextInt(NAMES.length)]);
        }
        int lineH = 22;
        int h = 16 + lineH * (lines + 1) + 10;
        BufferedImage img = backdrop(width, h);
        Graphics2D g = Img.g2d(img, true);
        int y = 24;
        for (String l : pre) {
            drawColored(g, codes(l), 6, y, 14f, true);
            y += lineH;
        }
        int x = drawColored(g, codes(before), 6, y, 14f, true);
        g.setFont(Img.font("Monospaced", java.awt.Font.PLAIN, 14));
        g.setColor(new Color(0x3F, 0x3F, 0x3F));
        g.drawString(literal, x + 2, y + 2);
        g.setColor(literalColor);
        g.drawString(literal, x, y);
        x += g.getFontMetrics().stringWidth(literal);
        drawColored(g, codes(after), x, y, 14f, true);
        g.dispose();
        return img;
    }
}