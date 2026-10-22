package dev.captcha;

import java.awt.image.BufferedImage;

/**
 * One captcha challenge sample.
 *
 * Every reimplementation is modelled on the real generation code of a specific
 * Minecraft anti-bot plugin (see {@link #plugin()} and {@link #source()}).
 */
public interface Cg {

    /** Plugin / library the algorithm was taken from, e.g. "LagBug/XProtect". */
    String plugin();

    /** Captcha type id, e.g. "map". */
    String id();

    /** Ground-truth answer a legitimate player would produce. */
    String answer();

    /** Faithful re-render of what the player is shown. */
    BufferedImage image();

    /** Where the original algorithm lives. */
    String source();

    /**
     * The challenge text the player is shown, when it is not already obvious from
     * {@link #image()}. Written into labels.jsonl so the dataset is self-contained.
     */
    default String prompt() {
        return null;
    }

    /**
     * The bounding box of the text that carries the answer, as {@code [x, y, w, h]} in
     * pixels, or {@code null} when the whole image is the text.
     *
     * <p>Most captcha types in this dataset are <b>scenes</b>, not a picture of a string:
     * a Minecraft chat log, an inventory window, an anvil dialog, a web panel. In those
     * the answer is one line among several, and a recogniser that is shown the whole
     * frame is being asked an ill-posed question - it can learn layout heuristics
     * ("the line after Tries Left:") that do not transfer to a different plugin.
     *
     * <p>The generator knows exactly where it drew the answer, so it can hand that
     * rectangle over. A solver then crops to the band and recognises the string, which
     * is both simpler and far more accurate. And because the plugin is known at
     * inference time, the cropper is a per-plugin constant, not something that has to be
     * learned.
     */
    default int[] roi() {
        return null;
    }

    /**
     * The literal string that is drawn in the image, when it is not the same as
     * {@link #answer()}.
     *
     * <p>Most types draw exactly what the player has to type, so this is the answer by
     * default. The exception is the number-word family: the image shows the number
     * spelled out in Russian words ({@code «сто восемьдесят два»}), while the player
     * must type the digits ({@code 182}). A recogniser is trained on what is in the
     * picture, and a small lexicon turns the words into the digits - so the dataset
     * carries both.
     */
    default String text() {
        return answer();
    }
}