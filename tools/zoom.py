from PIL import Image
im=Image.open(r"site\captchas\s10_API_V8_Объект_капчи\004.png").convert("RGB")
# empty cells (1,1) and (2,1) in a 250x150 3x3 -> x 83..166, y 50..150
crop=im.crop((83,50,167,150)).resize((84*6,100*6), Image.NEAREST)
crop.save(r"tmp\empty_cell.png")
print("saved", crop.size)
