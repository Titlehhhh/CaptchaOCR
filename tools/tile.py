from PIL import Image
im=Image.open(r"site\captchas\s04_API_V4_Пазл_капчи\003.png").convert("RGB")
t=im.crop((167,100,250,150)).resize((83*5,50*5), Image.LANCZOS)
t.save(r"tmp\tile_003_22.png")
t.rotate(180).save(r"tmp\tile_003_22_rot180.png")
t.rotate(90, expand=True).save(r"tmp\tile_003_22_rot90.png")
print("ok")
