// The "one folder, no Python" runtime in C#: ONNX Runtime (Microsoft.ML.OnnxRuntime)
// + System.Drawing for the PNG. The pipeline is the training pipeline of
// train/captcha_crnn.py: crop the band -> grayscale -> measure the glyph height ->
// scale the glyph to 32 px -> normalise -> ONNX Runtime -> greedy CTC decode.
//
//   captcha.exe <model.onnx> <config.json> <image.png> [x y w h]

using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using Microsoft.ML.OnnxRuntime;
using Microsoft.ML.OnnxRuntime.Tensors;

class Program
{
    static int Main(string[] args)
    {
        if (args.Length < 3)
        {
            Console.Error.WriteLine("usage: captcha.exe <model.onnx> <config.json> <image.png> [x y w h]");
            return 2;
        }
        string modelPath = args[0], configPath = args[1], imagePath = args[2];
        int[] roi = args.Length >= 7
            ? new[] { int.Parse(args[3]), int.Parse(args[4]), int.Parse(args[5]), int.Parse(args[6]) }
            : null;

        using var cfgDoc = JsonDocument.Parse(File.ReadAllText(configPath));
        var cfg = cfgDoc.RootElement;
        string charset = cfg.GetProperty("charset").GetString();
        int glyphHeight = cfg.GetProperty("input").GetProperty("glyph_height").GetInt32();
        int minWidth = cfg.GetProperty("input").GetProperty("min_width").GetInt32();
        int maxWidth = cfg.GetProperty("input").GetProperty("max_width").GetInt32();
        double mean = cfg.GetProperty("preprocess").GetProperty("mean").GetDouble();
        double std = cfg.GetProperty("preprocess").GetProperty("std").GetDouble();

        // -- the band
        byte[] gray;
        int bw, bh;
        using (var bmp = new Bitmap(imagePath))
        {
            int x0 = 0, y0 = 0, w = bmp.Width, h = bmp.Height;
            if (roi != null)
            {
                x0 = Math.Clamp(roi[0], 0, bmp.Width - 1);
                y0 = Math.Clamp(roi[1], 0, bmp.Height - 1);
                w = Math.Clamp(roi[2], 1, bmp.Width - x0);
                h = Math.Clamp(roi[3], 1, bmp.Height - y0);
            }
            bw = w; bh = h;
            var band = new byte[w * h];
            var rect = new Rectangle(x0, y0, w, h);
            var data = bmp.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            for (int y = 0; y < h; y++)
            {
                IntPtr row = IntPtr.Add(data.Scan0, y * data.Stride);
                byte[] rowBytes = MarshalCopy(row, w * 4);
                for (int x = 0; x < w; x++)
                {
                    int b = rowBytes[4 * x], g = rowBytes[4 * x + 1], r = rowBytes[4 * x + 2];
                    int l = (r * 299 + g * 587 + b * 114 + 500) / 1000;
                    band[y * w + x] = (byte)Math.Clamp(l, 0, 255);
                }
            }
            bmp.UnlockBits(data);
            gray = band;
        }

        // -- the glyph height (the trainer's rule)
        int line = LineHeight(gray, bw, bh);
        double scale = glyphHeight / (double)Math.Max(1, line);
        int outW = (int)Math.Floor(bw * scale + 0.5);
        outW = Math.Clamp(outW, minWidth, maxWidth);
        var scaled = ResizeBilinear(gray, bw, bh, outW, glyphHeight);

        // -- the tensor
        var tensor = new float[1 * 1 * glyphHeight * outW];
        for (int i = 0; i < tensor.Length; i++)
            tensor[i] = (float)((scaled[i] / 255.0 - mean) / std);

        // -- the model
        using var session = new InferenceSession(modelPath);
        var input = new DenseTensor<float>(tensor, new[] { 1, 1, glyphHeight, outW });
        string[] inputNames = { session.InputNames.First() };
        using var results = session.Run(new[] { NamedOnnxValue.CreateFromTensor(inputNames[0], input) });
        var logits = results.First().AsEnumerable<float>().ToArray();
        int classes = charset.Length + 1;
        int steps = logits.Length / classes;

        // -- the greedy CTC decode
        var chars = new System.Text.StringBuilder();
        double logSum = 0; int nConf = 0, prev = -1;
        for (int t = 0; t < steps; t++)
        {
            int best = 0; float bestV = logits[t * classes];
            for (int c = 1; c < classes; c++)
                if (logits[t * classes + c] > bestV) { bestV = logits[t * classes + c]; best = c; }
            double mx = logits[t * classes];
            double sum = 0;
            for (int c = 0; c < classes; c++) { if (logits[t * classes + c] > mx) mx = logits[t * classes + c]; }
            for (int c = 0; c < classes; c++) sum += Math.Exp(logits[t * classes + c] - mx);
            double post = Math.Exp(bestV - mx) / sum;
            if (best != prev && best != 0)
            {
                chars.Append(charset[best - 1]);
                logSum += Math.Log(Math.Max(post, 1e-6));
                nConf++;
            }
            prev = best;
        }
        double conf = nConf > 0 ? Math.Exp(logSum / nConf) : 0.0;

        Console.WriteLine("{\"file\":\"" + imagePath.Replace("\\", "/") + "\",\"text\":\"" + chars +
                          "\",\"confidence\":" + conf.ToString("F6", CultureInfo.InvariantCulture) +
                          ",\"width\":" + outW + "}");
        return 0;
    }

    static int LineHeight(byte[] img, int w, int h)
    {
        if (h < 3) return h;
        var busy = new bool[h];
        for (int y = 0; y < h; y++)
        {
            double sum = 0, sum2 = 0;
            for (int x = 0; x < w; x++) { double v = img[y * w + x]; sum += v; sum2 += v * v; }
            double mean = sum / w;
            double var = sum2 / w - mean * mean;
            if (var < 0) var = 0;
            busy[y] = Math.Sqrt(var) > 6.0;
        }
        var runs = new System.Collections.Generic.List<int>();
        int start = -1;
        for (int y = 0; y <= h; y++)
        {
            bool b = y < h && busy[y];
            if (b && start < 0) start = y;
            else if (!b && start >= 0) { runs.Add(y - start); start = -1; }
        }
        var keep = runs.Where(r => r >= 2).OrderBy(r => r).ToArray();
        if (keep.Length == 0) return h;
        int med = keep.Length % 2 == 1 ? keep[keep.Length / 2] : (keep[keep.Length / 2 - 1] + keep[keep.Length / 2]) / 2;
        return Math.Max(1, med);
    }

    // Pillow's BILINEAR: a triangle of support 1 scaled by the reduction factor,
    // one horizontal pass into an 8-bit image, then one vertical pass.
    static byte[] ResizeBilinear(byte[] src, int sw, int sh, int dw, int dh)
    {
        var tmp = new byte[dw * sh];
        var (kk, bounds, counts) = Coeffs(sw, dw);
        for (int y = 0; y < sh; y++)
            for (int x = 0; x < dw; x++)
            {
                double sum = 0;
                for (int k = 0; k < counts[x]; k++)
                    sum += kk[x * ksize + k] * src[y * sw + bounds[x] + k];
                tmp[y * dw + x] = (byte)Math.Clamp((int)Math.Floor(sum + 0.5), 0, 255);
            }
        var (kk2, bounds2, counts2) = Coeffs(sh, dh);
        var outp = new byte[dw * dh];
        for (int y = 0; y < dh; y++)
            for (int x = 0; x < dw; x++)
            {
                double sum = 0;
                for (int k = 0; k < counts2[y]; k++)
                    sum += kk2[y * ksize + k] * tmp[(bounds2[y] + k) * dw + x];
                outp[y * dw + x] = (byte)Math.Clamp((int)Math.Floor(sum + 0.5), 0, 255);
            }
        return outp;
    }

    const int ksize = 64;

    static (double[], int[], int[]) Coeffs(int inSize, int outSize)
    {
        double scale = (double)inSize / outSize;
        double filterscale = scale > 1.0 ? scale : 1.0;
        double sup = filterscale;
        double ss = 1.0 / filterscale;
        var k = new double[outSize * ksize];
        var bounds = new int[outSize];
        var counts = new int[outSize];
        for (int xx = 0; xx < outSize; xx++)
        {
            double center = (xx + 0.5) * scale;
            int xmin = (int)(center - sup + 0.5);
            if (xmin < 0) xmin = 0;
            int xmax = (int)(center + sup + 0.5);
            if (xmax > inSize) xmax = inSize;
            xmax -= xmin;
            double ww = 0;
            for (int i = 0; i < xmax; i++)
            {
                double v = (i + xmin - center + 0.5) * ss;
                if (v < 0) v = -v;
                double w = v < 1.0 ? 1.0 - v : 0.0;
                k[xx * ksize + i] = w;
                ww += w;
            }
            for (int i = 0; i < xmax; i++) if (ww != 0.0) k[xx * ksize + i] /= ww;
            bounds[xx] = xmin;
            counts[xx] = xmax;
        }
        return (k, bounds, counts);
    }

    static byte[] MarshalCopy(IntPtr ptr, int len)
    {
        var buf = new byte[len];
        System.Runtime.InteropServices.Marshal.Copy(ptr, buf, 0, len);
        return buf;
    }
}
