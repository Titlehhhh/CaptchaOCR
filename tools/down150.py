from PIL import Image
import os
# The GalleryCaptcha reference gallery was removed from this repository on 2026-10-22
# (it held third-party screenshots). Point CAPTCHA_GALLERY_DIR at a local copy to use it.
base = os.environ.get("CAPTCHA_GALLERY_DIR", "")
if not base:
    raise SystemExit("the reference gallery is no longer part of this repository (2026-10-22); "
                     "set CAPTCHA_GALLERY_DIR to a local copy to run this script")
for f,tag in [(os.path.join(base,"s05_API_V5_Латинские_Цифры_3x3_пазлы","002.png"),"v5_002"),
              (os.path.join(base,"s04_API_V4_Пазл_капчи","027.png"),"v4_027"),
              (os.path.join(base,"s07_API_V53_Латинские_Цифры_2x2_пазлы","001.png"),"v53_001")]:
    im=Image.open(f).convert("RGB")
    d=im.resize((150,90), Image.LANCZOS).resize((600,360), Image.NEAREST)
    out=os.path.join("tmp", f"down150_{tag}.png")
    d.save(out); print(out)
