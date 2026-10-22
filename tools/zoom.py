from PIL import Image
import os
# The GalleryCaptcha reference gallery was removed from this repository on 2026-10-22
# (it held third-party screenshots). Point CAPTCHA_GALLERY_DIR at a local copy to use it.
base = os.environ.get("CAPTCHA_GALLERY_DIR", "")
if not base:
    raise SystemExit("the reference gallery is no longer part of this repository (2026-10-22); "
                     "set CAPTCHA_GALLERY_DIR to a local copy to run this script")
im=Image.open(os.path.join(base,"s10_API_V8_Объект_капчи","004.png")).convert("RGB")
# empty cells (1,1) and (2,1) in a 250x150 3x3 -> x 83..166, y 50..150
crop=im.crop((83,50,167,150)).resize((84*6,100*6), Image.NEAREST)
crop.save(r"tmp\empty_cell.png")
print("saved", crop.size)
