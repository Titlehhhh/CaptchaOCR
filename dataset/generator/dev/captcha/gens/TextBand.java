package dev.captcha.gens;

import dev.captcha.Img;
import dev.captcha.McUi;

import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.util.ArrayList;
import java.util.List;

/**
 * The geometry the {@code roi()} bands are made of: where exactly a piece of text sits
 * in a frame.
 *
 * <p>The generators draw their answer at a known pen position, so the band that carries
 * it is arithmetic and not guesswork: the text is measured with the very font it is
 * drawn with, and the pen is walked the way the renderer walks it.
 *
 * <p>Nothing in here draws and nothing in here consumes randomness, so using it cannot
 * change a single pixel of a render - it only measures what has already been drawn.
 */
final class TextBand {

    private TextBand() {
    }

    /**
     * A measuring context for the Minecraft chat font - the one {@link McUi#drawColored}
     * writes with. It carries the same rendering hints as the drawing contexts of the
     * generators, and Monospaced is a logical font, so its advances are whole pixels and
     * the throw-away context measures exactly what the drawing context measures.
     */
    static Graphics2D measure() {
        return Img.g2d(Img.rgb(1, 1), true);
    }

    /**
     * The width of a plain string in the chat font at the given point size.
     *
     * @param size the point size, rounded the way {@link McUi#drawColored} rounds it
     */
    static int width(Graphics2D g, String plain, int size) {
        g.setFont(Img.font("Monospaced", Font.PLAIN, size));
        return g.getFontMetrics().stringWidth(plain);
    }

    /**
     * Where a piece of text sits inside a string that is drawn with
     * {@link McUi#drawColored}: the x it is drawn at and the face it is drawn in.
     *
     * <p>The renderer draws a line as a sequence of runs: every colour or style code
     * ends the current run, the pen moves on by the measured width of that run, and the
     * next run is drawn where the pen stands. A {@code &l} switches the face to bold
     * for the rest of the line, so the runs after it are measured in the bold face.
     * This walks the string exactly the way the renderer walks it.
     *
     * @param coded the line, with its colour codes, as it is handed to the renderer
     * @param needle the piece of the line to locate
     * @param size the point size the line is drawn at
     * @return where the needle is drawn, or {@code null} when it is not in the line
     */
    static Hit locate(Graphics2D g, String coded, String needle, int size) {
        int px = Math.round(size);
        boolean bold = false;
        int x = 0;

        List<Run> runs = new ArrayList<>();
        StringBuilder buf = new StringBuilder();
        for (int i = 0; i < coded.length(); i++) {
            char ch = coded.charAt(i);
            if ((ch == '§' || ch == '&') && i + 1 < coded.length() && isCode(coded.charAt(i + 1))) {
                // the run that ends here is drawn in the face that is active now
                runs.add(new Run(x, buf.toString(), bold));
                x += measure(g, buf.toString(), bold, px);
                buf.setLength(0);
                char code = Character.toLowerCase(coded.charAt(i + 1));
                if (code == 'l') {
                    bold = true;
                } else if (code == 'r') {
                    bold = false;
                }
                i++;
                continue;
            }
            buf.append(ch);
        }
        runs.add(new Run(x, buf.toString(), bold));

        StringBuilder plain = new StringBuilder();
        for (Run r : runs) {
            plain.append(r.text);
        }
        int at = plain.indexOf(needle);
        if (at < 0) {
            return null;
        }
        int pos = 0;
        for (Run r : runs) {
            if (at < pos + r.text.length()) {
                int left = r.x + measure(g, r.text.substring(0, at - pos), r.bold, px);
                return new Hit(left, r.bold);
            }
            pos += r.text.length();
        }
        return null;
    }

    /**
     * The x offset at which {@code needle} starts inside a string that is drawn with
     * {@link McUi#drawColored}, or -1 when it is not in the line.
     */
    static int offsetOf(Graphics2D g, String coded, String needle, int size) {
        Hit hit = locate(g, coded, needle, size);
        return hit == null ? -1 : hit.x();
    }

    /**
     * The band of a run of text: the glyph box of the run, in the frame's coordinates.
     *
     * @param x the left edge of the run
     * @param baseline the baseline the run is drawn on
     * @param ascent the ascent of the font the run is drawn in
     * @param descent the descent of that font
     * @param w the width of the run
     */
    static int[] box(int x, int baseline, int ascent, int descent, int w) {
        return new int[]{x, baseline - ascent, w, ascent + descent};
    }

    /**
     * The band, but only if it fits into the frame.
     *
     * <p>A band that the frame cuts in half is worse than no band: the crop would hold
     * a part of the answer, and a recogniser trained on it would be fitted against a
     * label it cannot read. So a band that does not fit is not a band - the caller gets
     * {@code null} and the sample is left to the caller to deal with.
     */
    static int[] fits(int[] band, int width, int height) {
        if (band == null) {
            return null;
        }
        if (band[0] < 0 || band[1] < 0
                || band[0] + band[2] > width || band[1] + band[3] > height) {
            return null;
        }
        return band;
    }

    /**
     * Clamps a band to the frame it belongs to.
     *
     * <p>For a band whose <i>ink</i> is inside the frame but whose margin is not: the
     * margin is the caller's, the ink is what matters.
     */
    static int[] inside(int[] band, int width, int height) {
        if (band == null) {
            return null;
        }
        int x = Math.max(0, band[0]);
        int y = Math.max(0, band[1]);
        int w = Math.min(band[2], width - x);
        int h = Math.min(band[3], height - y);
        if (w <= 0 || h <= 0) {
            return null;
        }
        return new int[]{x, y, w, h};
    }

    /** The width of a run of text in the face it is drawn in. */
    private static int measure(Graphics2D g, String text, boolean bold, int size) {
        g.setFont(Img.font("Monospaced", bold ? Font.BOLD : Font.PLAIN, size));
        return g.getFontMetrics().stringWidth(text);
    }

    /**
     * Whether a character is one of the codes {@link McUi#drawColored} understands: the
     * sixteen colours and the five style codes.
     */
    private static boolean isCode(char c) {
        char l = Character.toLowerCase(c);
        return (l >= '0' && l <= '9') || (l >= 'a' && l <= 'f')
                || l == 'k' || l == 'l' || l == 'm' || l == 'n' || l == 'r';
    }

    /** One run of a coloured string: where it starts, what it says and in which face. */
    private record Run(int x, String text, boolean bold) {
    }

    /** Where a needle sits in a coloured line: the x it is drawn at and its face. */
    record Hit(int x, boolean bold) {
    }
}
