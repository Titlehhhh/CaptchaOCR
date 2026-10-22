import dev.captcha.gens.CaptchaVerifyZ;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.File;

/**
 * Renders the reference codes with the project's own generator and writes them next to
 * the upstream reference renders, so the two can be pixel-diffed.
 */
public class DiffCaptchaVerifyZ {
    public static void main(String[] args) throws Exception {
        String[] codes = {"00000", "A7K2X", "M3P9L", "QWERT", "ZZZZZ"};
        File out = new File("research/myout");
        out.mkdirs();
        for (String c : codes) {
            BufferedImage img = new CaptchaVerifyZ.Map(c).image();
            File f = new File(out, "mine-" + c + ".png");
            ImageIO.write(img, "png", f);
            System.out.println("wrote " + f);
        }
    }
}
