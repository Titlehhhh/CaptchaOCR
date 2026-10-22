import java.awt.Font;
import java.awt.font.FontRenderContext;

public class FontInfo {
    public static void main(String[] a) {
        for (String n : new String[]{"Arial", "SansSerif", "Dialog"}) {
            Font f = new Font(n, Font.BOLD, 24);
            System.out.println(n + " -> name=" + f.getFontName() + " family=" + f.getFamily() + " ps=" + f.getPSName());
        }
        FontRenderContext frc = new FontRenderContext(null, false, false);
        Font hf = new Font("Arial", Font.BOLD, 12);
        Font cf = new Font("Arial", Font.BOLD, 24);
        Font ff = new Font("Arial", Font.PLAIN, 10);
        double hw = hf.getStringBounds("SECURITY VERIFICATION", frc).getWidth();
        double fw = ff.getStringBounds("Type the code in chat", frc).getWidth();
        System.out.println("header width = " + hw + "  -> x=5 right edge " + (5 + hw) + " (canvas 128)");
        System.out.println("code 'A7K2X' width = " + cf.getStringBounds("A7K2X", frc).getWidth()
                + "  -> x=(128-" + cf.getStringBounds("A7K2X", frc).getWidth() + ")/2");
        System.out.println("footer width = " + fw + "  -> x=15 right edge " + (15 + fw) + " (canvas 128)");
        System.out.println("java.version = " + System.getProperty("java.version"));
        System.out.println("os = " + System.getProperty("os.name") + " " + System.getProperty("os.version"));
    }
}
