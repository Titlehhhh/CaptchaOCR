from PIL import Image
import os
for f,tag in [(r"site\captchas\s05_API_V5_Латинские_Цифры_3x3_пазлы\002.png","v5_002"),
              (r"site\captchas\s04_API_V4_Пазл_капчи\027.png","v4_027"),
              (r"site\captchas\s07_API_V53_Латинские_Цифры_2x2_пазлы\001.png","v53_001")]:
    im=Image.open(f).convert("RGB")
    d=im.resize((150,90), Image.LANCZOS).resize((600,360), Image.NEAREST)
    out=os.path.join("tmp", f"down150_{tag}.png")
    d.save(out); print(out)
