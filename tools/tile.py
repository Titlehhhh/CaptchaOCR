from PIL import Image
import os
# The GalleryCaptcha reference gallery was removed from this repository on 2026-10-22
# (it held third-party screenshots). Point CAPTCHA_GALLERY_DIR at a local copy to use it.
base = os.environ.get("CAPTCHA_GALLERY_DIR", "")
if not base:
    raise SystemExit("the reference gallery is no longer part of this repository (2026-10-22); "
                     "set CAPTCHA_GALLERY_DIR to a local copy to run this script")
im=Image.open(os.path.join(base,"s04_API_V4_Пазл_капчи","003.png")).convert("RGB")
t=im.crop((167,100,250,150)).resize((83*5,50*5), Image.LANCZOS)
t.save(r"tmp\tile_003_22.png")
t.rotate(180).save(r"tmp\tile_003_22_rot180.png")
t.rotate(90, expand=True).save(r"tmp\tile_003_22_rot90.png")
print("ok")
