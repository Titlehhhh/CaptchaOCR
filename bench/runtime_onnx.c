/* runtime_onnx.c - the "one folder, no Python" runtime for the captcha CRNN.
 *
 *   captcha_runtime.exe <model.onnx> <config.json> <image.png> [x y w h]
 *                      [--dump-tensor <file.raw>] [--threads N]
 *
 * What it needs at run time: the ONNX Runtime DLL, this exe, the model and the
 * config - that is the whole folder. No Python, no torch, no third-party library
 * beyond the Windows Imaging Component (WIC, part of the OS) for the PNG.
 *
 * The pipeline is the training pipeline of train/captcha_crnn.py:
 *   crop the band -> grayscale -> measure the glyph height -> scale the glyph to
 *   32 px -> normalise to [-1, 1] -> ONNX Runtime -> greedy CTC decode.
 *
 * Build (MSVC, from the folder that holds onnxruntime.h and onnxruntime.lib):
 *   cl /O2 /std:c11 runtime_onnx.c /link onnxruntime.lib windowscodecs.lib ole32.lib
 * Build (gcc/clang, Linux):
 *   cc -O2 runtime_onnx.c -lonnxruntime -lole32 -lwindowscodecs -lm
 */

#define COBJMACROS
#define INITGUID
#include <windows.h>
#include <objbase.h>
#include <wincodec.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "onnxruntime_c_api.h"

#define MAX_CHARSET 512

static void die(const char *msg) {
    fprintf(stderr, "error: %s\n", msg);
    exit(1);
}

/* ------------------------------------------------------------------ the config */

static char *read_file(const char *path, long *size_out) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)n + 1);
    if (!buf) { fclose(f); return NULL; }
    if (fread(buf, 1, (size_t)n, f) != (size_t)n) { free(buf); fclose(f); return NULL; }
    buf[n] = 0;
    fclose(f);
    if (size_out) *size_out = n;
    return buf;
}

static const char *find_value(const char *buf, const char *key) {
    char pat[128];
    snprintf(pat, sizeof pat, "\"%s\"", key);
    const char *p = strstr(buf, pat);
    if (!p) return NULL;
    p = strchr(p, ':');
    if (!p) return NULL;
    return p + 1;
}

static int json_int(const char *buf, const char *key, int def) {
    const char *p = find_value(buf, key);
    if (!p) return def;
    return (int)strtol(p, NULL, 10);
}

static double json_double(const char *buf, const char *key, double def) {
    const char *p = find_value(buf, key);
    if (!p) return def;
    return strtod(p, NULL);
}

static int json_string(const char *buf, const char *key, char *out, size_t n) {
    const char *p = find_value(buf, key);
    if (!p) return 0;
    while (*p && *p != '"') p++;
    if (!*p) return 0;
    p++;
    size_t i = 0;
    while (*p && *p != '"' && i + 1 < n) out[i++] = *p++;
    out[i] = 0;
    return 1;
}

/* ------------------------------------------------------------------ the picture */

/* Decode a PNG into a grayscale buffer. The conversion is the ITU-R 601-2 one
 * Pillow uses for "L", rounded - that is what the model was trained on. */
static void to_wide(const char *in, wchar_t *out, int n) {
    int len = MultiByteToWideChar(CP_ACP, 0, in, -1, out, n);
    if (len <= 0) { out[0] = 0; }
}

static uint8_t *load_grayscale(const char *path, int *out_w, int *out_h) {
    HRESULT hr;
    IWICImagingFactory *factory = NULL;
    IWICBitmapDecoder *decoder = NULL;
    IWICBitmapFrameDecode *frame = NULL;
    IWICBitmap *bitmap = NULL;
    IWICFormatConverter *converter = NULL;
    uint8_t *pixels = NULL, *gray = NULL;
    wchar_t wpath[MAX_PATH];

    to_wide(path, wpath, MAX_PATH);
    hr = CoInitializeEx(NULL, COINIT_MULTITHREADED);
    if (FAILED(hr)) die("CoInitializeEx failed");
    hr = CoCreateInstance(&CLSID_WICImagingFactory, NULL, CLSCTX_INPROC_SERVER,
                          &IID_IWICImagingFactory, (void **)&factory);
    if (FAILED(hr)) die("WIC factory unavailable");
    hr = IWICImagingFactory_CreateDecoderFromFilename(factory, wpath, NULL, GENERIC_READ,
                                                       WICDecodeMetadataCacheOnDemand, &decoder);
    if (FAILED(hr)) die("cannot open the picture");
    hr = IWICBitmapDecoder_GetFrame(decoder, 0, &frame);
    if (FAILED(hr)) die("cannot read the frame");
    hr = IWICImagingFactory_CreateBitmapFromSource(factory, (IWICBitmapSource *)frame,
                                                    WICBitmapCacheOnLoad, &bitmap);
    if (FAILED(hr)) die("cannot create the bitmap");
    hr = IWICImagingFactory_CreateFormatConverter(factory, &converter);
    if (FAILED(hr)) die("cannot create the converter");
    hr = IWICFormatConverter_Initialize(converter, (IWICBitmapSource *)bitmap,
                                         &GUID_WICPixelFormat32bppBGR,
                                         WICBitmapDitherTypeNone, NULL, 0.0,
                                         WICBitmapPaletteTypeCustom);
    if (FAILED(hr)) die("cannot initialise the converter");

    UINT w = 0, h = 0;
    hr = IWICBitmapSource_GetSize((IWICBitmapSource *)converter, &w, &h);
    if (FAILED(hr) || w == 0 || h == 0) die("empty picture");
    UINT stride = w * 4;
    pixels = (uint8_t *)malloc((size_t)stride * h);
    if (!pixels) die("out of memory");
    hr = IWICFormatConverter_CopyPixels(converter, NULL, stride, (UINT)((size_t)stride * h), pixels);
    if (FAILED(hr)) die("cannot copy the pixels");

    gray = (uint8_t *)malloc((size_t)w * h);
    if (!gray) die("out of memory");
    for (UINT y = 0; y < h; y++) {
        const uint8_t *row = pixels + (size_t)y * stride;   /* B, G, R, A */
        for (UINT x = 0; x < w; x++) {
            int b = row[4 * x + 0], g = row[4 * x + 1], r = row[4 * x + 2];
            int l = (r * 299 + g * 587 + b * 114 + 500) / 1000;
            if (l < 0) l = 0;
            if (l > 255) l = 255;
            gray[(size_t)y * w + x] = (uint8_t)l;
        }
    }

    if (converter) converter->lpVtbl->Release(converter);
    if (bitmap) bitmap->lpVtbl->Release(bitmap);
    if (frame) frame->lpVtbl->Release(frame);
    if (decoder) decoder->lpVtbl->Release(decoder);
    if (factory) factory->lpVtbl->Release(factory);
    free(pixels);
    *out_w = (int)w;
    *out_h = (int)h;
    return gray;
}

/* ------------------------------------------------------------------ the geometry */

/* The height of one line of glyphs inside the band: the rows of a text line vary
 * a lot across the row, the blank rows between the lines do not, so the median
 * length of the "busy" runs is the height of one line. The trainer's rule. */
static int line_height(const uint8_t *img, int w, int h) {
    if (h < 3) return h;
    int *busy = (int *)malloc((size_t)h * sizeof(int));
    int *runs = (int *)malloc((size_t)h * sizeof(int));
    if (!busy || !runs) die("out of memory");
    for (int y = 0; y < h; y++) {
        double sum = 0.0, sum2 = 0.0;
        for (int x = 0; x < w; x++) {
            double v = img[(size_t)y * w + x];
            sum += v;
            sum2 += v * v;
        }
        double mean = sum / w;
        double var = sum2 / w - mean * mean;
        if (var < 0) var = 0;
        busy[y] = (sqrt(var) > 6.0) ? 1 : 0;
    }
    int n = 0, start = -1;
    for (int y = 0; y <= h; y++) {
        int b = (y < h) ? busy[y] : 0;
        if (b && start < 0) start = y;
        else if (!b && start >= 0) { runs[n++] = y - start; start = -1; }
    }
    free(busy);
    int best = 0;
    int *keep = (int *)malloc((size_t)(n > 0 ? n : 1) * sizeof(int));
    if (!keep) die("out of memory");
    int m = 0;
    for (int i = 0; i < n; i++) if (runs[i] >= 2) keep[m++] = runs[i];
    free(runs);
    if (m == 0) { free(keep); return h; }
    for (int i = 1; i < m; i++) {          /* insertion sort, m is tiny */
        int v = keep[i], j = i - 1;
        while (j >= 0 && keep[j] > v) { keep[j + 1] = keep[j]; j--; }
        keep[j + 1] = v;
    }
    best = (m % 2) ? keep[m / 2] : (keep[m / 2 - 1] + keep[m / 2]) / 2;
    free(keep);
    return best < 1 ? 1 : best;
}

/* Pillow's BILINEAR: a triangle of support 1 scaled by the reduction factor,
 * one horizontal pass into an 8-bit image, then one vertical pass. */
typedef struct {
    double *k;
    int *bounds;
    int *counts;
    int ksize;
} Coeffs;

static void coeffs(int in_size, int out_size, Coeffs *c) {
    double scale = (double)in_size / (double)out_size;
    double filterscale = scale > 1.0 ? scale : 1.0;
    double sup = filterscale;                 /* the bilinear filter has support 1 */
    double ss = 1.0 / filterscale;
    int ksize = (int)ceil(sup) * 2 + 1;
    c->k = (double *)calloc((size_t)out_size * ksize, sizeof(double));
    c->bounds = (int *)calloc((size_t)out_size, sizeof(int));
    c->counts = (int *)calloc((size_t)out_size, sizeof(int));
    c->ksize = ksize;
    if (!c->k || !c->bounds || !c->counts) die("out of memory");
    for (int xx = 0; xx < out_size; xx++) {
        double center = (xx + 0.5) * scale;
        int xmin = (int)(center - sup + 0.5);
        if (xmin < 0) xmin = 0;
        int xmax = (int)(center + sup + 0.5);
        if (xmax > in_size) xmax = in_size;
        xmax -= xmin;
        double ww = 0.0;
        for (int i = 0; i < xmax; i++) {
            double x = (i + xmin - center + 0.5) * ss;
            if (x < 0) x = -x;
            double w = (x < 1.0) ? (1.0 - x) : 0.0;
            c->k[(size_t)xx * ksize + i] = w;
            ww += w;
        }
        for (int i = 0; i < xmax; i++) if (ww != 0.0) c->k[(size_t)xx * ksize + i] /= ww;
        c->bounds[xx] = xmin;
        c->counts[xx] = xmax;
    }
}

static void coeffs_free(Coeffs *c) {
    free(c->k); free(c->bounds); free(c->counts);
}

static uint8_t *resize_bilinear(const uint8_t *src, int sw, int sh, int dw, int dh) {
    uint8_t *tmp = (uint8_t *)malloc((size_t)dw * sh);
    uint8_t *out = (uint8_t *)malloc((size_t)dw * dh);
    if (!tmp || !out) die("out of memory");
    Coeffs c;
    coeffs(sw, dw, &c);
    for (int y = 0; y < sh; y++) {
        const uint8_t *row = src + (size_t)y * sw;
        for (int x = 0; x < dw; x++) {
            double sum = 0.0;
            int cnt = c.counts[x];
            for (int k = 0; k < cnt; k++)
                sum += c.k[(size_t)x * c.ksize + k] * row[c.bounds[x] + k];
            int v = (int)floor(sum + 0.5);
            if (v < 0) v = 0;
            if (v > 255) v = 255;
            tmp[(size_t)y * dw + x] = (uint8_t)v;
        }
    }
    coeffs_free(&c);
    coeffs(sh, dh, &c);
    for (int y = 0; y < dh; y++) {
        int cnt = c.counts[y];
        for (int x = 0; x < dw; x++) {
            double sum = 0.0;
            for (int k = 0; k < cnt; k++)
                sum += c.k[(size_t)y * c.ksize + k] * tmp[(size_t)(c.bounds[y] + k) * dw + x];
            int v = (int)floor(sum + 0.5);
            if (v < 0) v = 0;
            if (v > 255) v = 255;
            out[(size_t)y * dw + x] = (uint8_t)v;
        }
    }
    coeffs_free(&c);
    free(tmp);
    return out;
}

/* ------------------------------------------------------------------ the runtime */

int main(int argc, char **argv) {
    const char *model_path = NULL, *config_path = NULL, *image_path = NULL;
    const char *dump_path = NULL;
    int roi[4] = {0, 0, 0, 0};
    int have_roi = 0, threads = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--dump-tensor") && i + 1 < argc) { dump_path = argv[++i]; }
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) { threads = atoi(argv[++i]); }
        else if (!model_path) model_path = argv[i];
        else if (!config_path) config_path = argv[i];
        else if (!image_path) image_path = argv[i];
        else if (!have_roi && i + 3 < argc) {
            roi[0] = atoi(argv[i]); roi[1] = atoi(argv[i + 1]);
            roi[2] = atoi(argv[i + 2]); roi[3] = atoi(argv[i + 3]);
            have_roi = 1; i += 3;
        }
    }
    if (!model_path || !config_path || !image_path) {
        fprintf(stderr, "usage: %s <model.onnx> <config.json> <image.png> [x y w h]\n", argv[0]);
        return 2;
    }

    char charset[MAX_CHARSET];
    char *cfg = read_file(config_path, NULL);
    if (!cfg) die("cannot read the config");
    if (!json_string(cfg, "charset", charset, sizeof charset)) die("no charset in the config");
    int glyph_height = json_int(cfg, "glyph_height", 32);
    int min_width = json_int(cfg, "min_width", 64);
    int max_width = json_int(cfg, "max_width", 400);
    double mean = json_double(cfg, "mean", 0.5);
    double std = json_double(cfg, "std", 0.5);
    free(cfg);

    int iw = 0, ih = 0;
    uint8_t *gray = load_grayscale(image_path, &iw, &ih);

    /* the band */
    int x0 = 0, y0 = 0, bw = iw, bh = ih;
    if (have_roi) {
        x0 = roi[0]; y0 = roi[1]; bw = roi[2]; bh = roi[3];
        if (x0 < 0) x0 = 0;
        if (y0 < 0) y0 = 0;
        if (x0 > iw - 1) x0 = iw - 1;
        if (y0 > ih - 1) y0 = ih - 1;
        if (bw > iw - x0) bw = iw - x0;
        if (bh > ih - y0) bh = ih - y0;
        if (bw < 1) bw = 1;
        if (bh < 1) bh = 1;
    }
    uint8_t *band = (uint8_t *)malloc((size_t)bw * bh);
    if (!band) die("out of memory");
    for (int y = 0; y < bh; y++)
        memcpy(band + (size_t)y * bw, gray + (size_t)(y + y0) * iw + x0, (size_t)bw);
    free(gray);

    /* the glyph height, then the scale */
    int line = line_height(band, bw, bh);
    double scale = (double)glyph_height / (double)(line > 0 ? line : 1);
    int w = (int)floor(bw * scale + 0.5);
    if (w < min_width) w = min_width;
    if (w > max_width) w = max_width;

    uint8_t *scaled = resize_bilinear(band, bw, bh, w, glyph_height);
    free(band);

    size_t n = (size_t)glyph_height * w;
    float *tensor = (float *)malloc(n * sizeof(float));
    if (!tensor) die("out of memory");
    for (size_t i = 0; i < n; i++)
        tensor[i] = (float)(((double)scaled[i] / 255.0 - mean) / std);
    free(scaled);

    if (dump_path) {
        FILE *f = fopen(dump_path, "wb");
        if (!f) die("cannot write the tensor");
        fwrite(tensor, sizeof(float), n, f);
        fclose(f);
    }

    /* ONNX Runtime */
    const OrtApi *ort = OrtGetApiBase()->GetApi(ORT_API_VERSION);
    OrtEnv *env = NULL;
    OrtSessionOptions *opts = NULL;
    OrtSession *session = NULL;
    OrtMemoryInfo *mem = NULL;
    OrtAllocator *allocator = NULL;
    if (ort->CreateEnv(ORT_LOGGING_LEVEL_WARNING, "captcha", &env) != NULL) die("CreateEnv failed");
    if (ort->CreateSessionOptions(&opts) != NULL) die("CreateSessionOptions failed");
    if (threads > 0) ort->SetIntraOpNumThreads(opts, threads);
    ort->SetSessionGraphOptimizationLevel(opts, ORT_ENABLE_ALL);
    wchar_t wmodel[MAX_PATH];
    to_wide(model_path, wmodel, MAX_PATH);
    if (ort->CreateSession(env, wmodel, opts, &session) != NULL) die("cannot load the model");
    if (ort->GetAllocatorWithDefaultOptions(&allocator) != NULL) die("no allocator");

    OrtMemoryInfo *mem_info = NULL;
    ort->CreateCpuMemoryInfo(OrtArenaAllocator, OrtMemTypeDefault, &mem_info);

    char *input_name = NULL;
    ort->SessionGetInputName(session, 0, allocator, &input_name);
    if (!input_name) input_name = "image";

    int64_t shape[4] = {1, 1, glyph_height, w};
    OrtValue *input = NULL;
    if (ort->CreateTensorWithDataAsOrtValue(mem_info, tensor, n * sizeof(float), shape, 4,
                                            ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT, &input) != NULL)
        die("cannot create the input tensor");

    const char *input_names[1] = {input_name};
    const char *output_names[1] = {"logits"};
    OrtValue *outputs[1] = {NULL};
    if (ort->Run(session, NULL, input_names, (const OrtValue *const *)&input, 1,
                 output_names, 1, outputs) != NULL)
        die("the inference failed");

    OrtTensorTypeAndShapeInfo *info = NULL;
    ort->GetTensorTypeAndShape(outputs[0], &info);
    size_t out_count = 0;
    ort->GetTensorShapeElementCount(info, &out_count);
    float *logits = NULL;
    ort->GetTensorMutableData(outputs[0], (void **)&logits);

    int classes = 0;
    OrtTensorTypeAndShapeInfo *linfo = NULL;
    if (ort->GetTensorTypeAndShape(outputs[0], &linfo) == NULL) {
        size_t nd = 0;
        ort->GetDimensionsCount(linfo, &nd);
        int64_t dims[4] = {0, 0, 0, 0};
        if (nd >= 1 && nd <= 4) {
            ort->GetDimensions(linfo, dims, nd);
            classes = (int)dims[nd - 1];      /* the class axis is the last one */
        }
    }
    if (classes <= 0) die("cannot read the output shape");
    int steps = (int)(out_count / classes);

    /* the greedy CTC decode */
    char text[MAX_CHARSET];
    int tlen = 0;
    double log_sum = 0.0;
    int n_conf = 0;
    int prev = -1;
    for (int t = 0; t < steps; t++) {
        const float *row = logits + (size_t)t * classes;
        int best = 0;
        float best_v = row[0];
        for (int c = 1; c < classes; c++) if (row[c] > best_v) { best_v = row[c]; best = c; }
        /* the posterior of the winner */
        double mx = row[0], sum = 0.0;
        for (int c = 0; c < classes; c++) {
            if (row[c] > mx) mx = row[c];
        }
        for (int c = 0; c < classes; c++) sum += exp((double)row[c] - mx);
        double post = exp((double)best_v - mx) / sum;
        if (best != prev && best != 0) {
            if (tlen + 1 < (int)sizeof charset) text[tlen++] = charset[best - 1];
            log_sum += log(post < 1e-6 ? 1e-6 : post);
            n_conf++;
        }
        prev = best;
    }
    text[tlen] = 0;
    double conf = n_conf ? exp(log_sum / n_conf) : 0.0;

    /* the path goes into a JSON string: make the separators JSON-safe */
    char jpath[MAX_PATH * 2];
    size_t pl = strlen(image_path);
    if (pl >= sizeof jpath) pl = sizeof jpath - 1;
    for (size_t i = 0; i < pl; i++) jpath[i] = (image_path[i] == '\\') ? '/' : image_path[i];
    jpath[pl] = 0;
    printf("{\"file\":\"%s\",\"text\":\"%s\",\"confidence\":%.6f,\"width\":%d}\n",
           jpath, text, conf, w);

    ort->ReleaseValue(outputs[0]);
    ort->ReleaseValue(input);
    ort->ReleaseSession(session);
    ort->ReleaseSessionOptions(opts);
    ort->ReleaseEnv(env);
    free(tensor);
    return 0;
}
