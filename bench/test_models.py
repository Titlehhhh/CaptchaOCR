#!/usr/bin/env python3
"""Test multiple CAPTCHA/OCR models on our project images."""
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

from PIL import Image
import numpy as np

# Paths to our 5 test images from different generators
IMAGES = {
    "InstantlyMoist_textcaptcha": r"dataset/out/InstantlyMoist\Captcha\textcaptcha\001.png",
    "Archy-X_Krypton_map": r"dataset/out/Archy-X\Krypton\map\001.png",
    "JSH32_Minecaptcha_map": r"dataset/out/JSH32\Minecaptcha\map\001.png",
    "LagBug_XProtect_code": r"dataset/out/LagBug\XProtect\code\001.png",
    "irootdev_AnBot_captcha": r"dataset/out/irootdev\AnBot\captcha\001.png",
}

print("=" * 70)
print("TEST IMAGES FOUND")
for name, path in IMAGES.items():
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    print(f"  {name}: {path} | exists={exists} | size={size} bytes")
print("=" * 70)

# --- Model 1: microsoft/trocr-base-handwritten (transformers) ---
print("\n[MODEL 1] microsoft/trocr-base-handwritten via transformers")
try:
    from transformers import pipeline
    print("  Loading pipeline 'image-text-to-text' ...")
    # Note: pipeline type changed in v5; TrOCR uses 'image-text-to-text'
    pipe = pipeline("image-text-to-text", model="microsoft/trocr-base-handwritten", device=-1)
    print("  Pipeline loaded.")
    for name, path in IMAGES.items():
        img = Image.open(path).convert("RGB")
        result = pipe(img)
        text = str(result)
        print(f"    {name}: {text}")
except Exception as e:
    print(f"  ERROR loading/running microsoft/trocr-base-handwritten: {e}")
    import traceback
    traceback.print_exc()

# --- Model 2: keras-io/ocr-for-captcha (TF-Keras) ---
print("\n[MODEL 2] keras-io/ocr-for-captcha (TF-Keras) via huggingface)")
try:
    from huggingface_hub import from_pretrained_keras
    model = from_pretrained_keras("keras-io/ocr-for-captcha")
    print("  Model loaded from huggingface.")
    # This is a Keras model with CTC; inference requires custom decode
    # We'll just confirm load; full inference needs character mapping
    print("  Note: this model requires CTC decoding; not directly text-output without post-process.")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

# --- Model 3: EasyOCR ---
print("\n[MODEL 3] EasyOCR (ready-to-use OCR)")
try:
    import easyocr
    reader = easyocr.Reader(["en"], gpu=False)
    print("  EasyOCR reader initialized.")
    for name, path in IMAGES.items():
        img = Image.open(path)
        result = reader.readtext(np.array(img), detail=0, paragraph=False)
        text = " ".join(result) if result else "(no text detected)"
        print(f"    {name}: '{text}'")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

# --- Model 4: Try fine-tuned captcha models from HF ---
print("\n[MODEL 4] hongyusir/trocr-base-printed_captcha_ocr via pipeline")
try:
    from transformers import pipeline
    pipe_captcha = pipeline("image-text-to-text", model="hongyusir/trocr-base-printed_captcha_ocr", device=-1)
    print("  Captcha-tuned TrOCR loaded.")
    for name, path in IMAGES.items():
        img = Image.open(path).convert("RGB")
        result = pipe_captcha(img)
        text = result[0]["generated_text"] if isinstance(result, list) else str(result)
        print(f"    {name}: '{text}'")
except Exception as e:
    print(f"  ERROR: {e}")

# --- Model 5: Try DunnBC22 captcha model ---
print("\n[MODEL 5] DunnBC22/trocr-base-printed_captcha_ocr via pipeline")
try:
    pipe_captcha2 = pipeline("image-text-to-text", model="DunnBC22/trocr-base-printed_captcha_ocr", device=-1)
    print("  Captcha-tuned TrOCR loaded.")
    for name, path in IMAGES.items():
        img = Image.open(path).convert("RGB")
        result = pipe_captcha2(img)
        text = result[0]["generated_text"] if isinstance(result, list) else str(result)
        print(f"    {name}: '{text}'")
except Exception as e:
    print(f"  ERROR: {e}")

# --- Show image info ---
print("\n" + "=" * 70)
print("IMAGE PREVIEW (sizes)")
for name, path in IMAGES.items():
    img = Image.open(path)
    print(f"  {name}: size={img.size}, mode={img.mode}")
