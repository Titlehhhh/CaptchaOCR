import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.Image;
import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;

/**
 * Research-only reference render of the CaptchaVerifyZ map renderer.
 * Replicates, line for line, the algorithm decompiled from
 * com.Mateitaa1.CaptchaVerifyZ.CaptchaVerifyZ$CaptchaMapRenderer#render
 * (CaptchaVerifyZ-1.4.jar, sha256 59526593F6B53C81...).
 * Purpose: pixel-verify a clean-room re-implementation. Not part of the dataset generator.
 */
public class RefRender {
    public static void main(String[] args) throws Exception {
        String outDir = args.length > 0 ? args[0] : ".";
        String[] codes = {"A7K2X", "QWERT", "00000", "ZZZZZ", "M3P9L"};
        for (String code : codes) {
            BufferedImage image = new BufferedImage(128, 128, 1);
            Graphics2D g2d = image.createGraphics();
            g2d.setColor(Color.DARK_GRAY);
            g2d.fillRect(0, 0, 128, 128);
            g2d.setColor(Color.WHITE);
            g2d.setFont(new Font("Arial", 1, 12));
            g2d.drawString("SECURITY VERIFICATION", 5, 20);
            g2d.setColor(Color.YELLOW);
            g2d.setFont(new Font("Arial", 1, 24));
            FontMetrics fm = g2d.getFontMetrics();
            int x = (128 - fm.stringWidth(code)) / 2;
            g2d.drawString(code, x, 70);
            g2d.setColor(Color.LIGHT_GRAY);
            g2d.setFont(new Font("Arial", 0, 10));
            g2d.drawString("Type the code in chat", 15, 100);
            g2d.dispose();
            File f = new File(outDir, "ref-" + code + ".png");
            ImageIO.write(image, "png", f);
            System.out.println("wrote " + f + "  (code x=" + x + ")");
        }
    }
}
