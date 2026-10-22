package dev.captcha.gens;

/**
 * The Minecraft map colour palette, shared by the map captchas of this dataset.
 *
 * <p>Both plugins that paint their captcha onto a Minecraft map - BotFilter and
 * LimboFilter - reduce the finished picture to this palette, because that is what the
 * client renders. A captcha that is "nearly" palette coloured is not what the player
 * sees, so the quantisation is part of the rendering, not a post-process.
 *
 * <p>The palette is four black shades (the slots a map uses for "nothing here")
 * followed by the 140 real colours. Packed as {@code 0xRRGGBB}.
 */
final class MapPalette {

    private MapPalette() {
    }

    /** The palette of the upstream map code. */
    static final int[] COLOURS = {
            0x000000, 0x000000, 0x000000, 0x000000,
            0x597D27, 0x6D9930, 0x7FB238, 0x435E1D,
            0xAEA473, 0xD5C98C, 0xF7E9A3, 0x827B56,
            0x8C8C8C, 0xABABAB, 0xC7C7C7, 0x696969,
            0xB40000, 0xDC0000, 0xFF0000, 0x870000,
            0x7070B4, 0x8A8ADC, 0xA0A0FF, 0x545487,
            0x757575, 0x909090, 0xA7A7A7, 0x585858,
            0x005700, 0x006A00, 0x007C00, 0x004100,
            0xB4B4B4, 0xDCDCDC, 0xFFFFFF, 0x878787,
            0x737681, 0x8D909E, 0xA4A8B8, 0x565861,
            0x6A4C36, 0x825E42, 0x976D4D, 0x4F3928,
            0x4F4F4F, 0x606060, 0x707070, 0x3B3B3B,
            0x2D2DB4, 0x3737DC, 0x4040FF, 0x212187,
            0x645432, 0x7B663E, 0x8F7748, 0x4B3F26,
            0xB4B1AC, 0xDCD9D3, 0xFFFCF5, 0x878581,
            0x985924, 0xBA6D2C, 0xD87F33, 0x72431B,
            0x7D3598, 0x9941BA, 0xB24CD8, 0x5E2872,
            0x486C98, 0x5884BA, 0x6699D8, 0x365172,
            0xA1A124, 0xC5C52C, 0xE5E533, 0x79791B,
            0x599011, 0x6DB015, 0x7FCC19, 0x436C0D,
            0xAA5974, 0xD06D8E, 0xF27FA5, 0x804357,
            0x353535, 0x414141, 0x4C4C4C, 0x282828,
            0x6C6C6C, 0x848484, 0x999999, 0x515151,
            0x35596C, 0x416D84, 0x4C7F99, 0x284351,
            0x592C7D, 0x6D3699, 0x7F3FB2, 0x43215E,
            0x24357D, 0x2C4199, 0x334CB2, 0x1B285E,
            0x483524, 0x58412C, 0x664C33, 0x36281B,
            0x485924, 0x586D2C, 0x667F33, 0x36431B,
            0x6C2424, 0x842C2C, 0x993333, 0x511B1B,
            0x111111, 0x151515, 0x191919, 0x0D0D0D,
            0xB0A836, 0xD7CD42, 0xFAEE4D, 0x847E28,
            0x409A96, 0x4FBCB7, 0x5CDBD5, 0x307370,
            0x345AB4, 0x3F6EDC, 0x4A80FF, 0x274387,
            0x009928, 0x00BB32, 0x00D93A, 0x00721E,
            0x5B3C22, 0x6F4A2A, 0x815631, 0x442D19,
            0x4F0100, 0x600100, 0x700200, 0x3B0100
    };

    /** The first palette slot that may be used as a match target (the four blacks are not). */
    static final int FIRST_MATCHABLE = 4;

    /**
     * The palette match of the upstream map code: a weighted RGB distance, where red
     * and blue count a little less than green, and the red weight grows with the
     * lightness of the pair. The first palette slot with the smallest distance wins.
     */
    static int nearest(int argb) {
        int r = (argb >> 16) & 0xFF;
        int g = (argb >> 8) & 0xFF;
        int b = argb & 0xFF;

        int best = -1;
        double bestDistance = -1;
        for (int i = FIRST_MATCHABLE; i < COLOURS.length; i++) {
            int candidate = COLOURS[i];
            int cr = (candidate >> 16) & 0xFF;
            int cg = (candidate >> 8) & 0xFF;
            int cb = candidate & 0xFF;

            double mean = (r + cr) / 2.0;
            int dr = r - cr;
            int dg = g - cg;
            int db = b - cb;
            double weightR = 2.0 + mean / 256.0;
            double weightG = 4.0;
            double weightB = 2.0 + (255.0 - mean) / 256.0;
            double distance = weightR * dr * dr + weightG * dg * dg + weightB * db * db;

            if (bestDistance < 0 || distance < bestDistance) {
                bestDistance = distance;
                best = i;
            }
        }
        return 0xFF000000 | COLOURS[best];
    }

    /** The palette index of a colour, for the code that paints in palette indices. */
    static int indexOf(int argb) {
        int r = (argb >> 16) & 0xFF;
        int g = (argb >> 8) & 0xFF;
        int b = argb & 0xFF;

        int best = FIRST_MATCHABLE;
        double bestDistance = -1;
        for (int i = FIRST_MATCHABLE; i < COLOURS.length; i++) {
            int candidate = COLOURS[i];
            int cr = (candidate >> 16) & 0xFF;
            int cg = (candidate >> 8) & 0xFF;
            int cb = candidate & 0xFF;

            double mean = (r + cr) / 2.0;
            int dr = r - cr;
            int dg = g - cg;
            int db = b - cb;
            double weightR = 2.0 + mean / 256.0;
            double weightG = 4.0;
            double weightB = 2.0 + (255.0 - mean) / 256.0;
            double distance = weightR * dr * dr + weightG * dg * dg + weightB * db * db;

            if (bestDistance < 0 || distance < bestDistance) {
                bestDistance = distance;
                best = i;
            }
        }
        return best;
    }
}
