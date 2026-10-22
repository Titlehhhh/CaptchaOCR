import os,sys
from PIL import Image
import numpy as np
base=os.path.join(os.path.dirname(__file__),"..","site","captchas")
def seams(path,gx=3,gy=3):
    im=Image.open(path).convert("RGB"); a=np.asarray(im).astype(int); H,W,_=a.shape
    xs=[round(i*W/gx) for i in range(gx+1)]; ys=[round(i*H/gy) for i in range(gy+1)]
    # baseline: mean abs diff between two rows 40 px apart (typical texture gradient)
    base_v=np.abs(a[20]-a[60]).mean(); base_h=np.abs(a[:,20]-a[:,60]).mean()
    vs=[]
    for c in range(1,gx):
        x=xs[c]; vs.append(round(float(np.abs(a[:,x-1]-a[:,x]).mean()),2))
    hs=[]
    for r in range(1,gy):
        y=ys[r]; hs.append(round(float(np.abs(a[y-1]-a[y]).mean()),2))
    # rotation-aware: compare a[-1] row of left tile to a[0] of right tile, and also try
    # a[0] of left tile (180-rotated) -> a[-1] of right tile
    print(f"{os.path.relpath(path,base)}")
    print(f"   vertical seams {vs}  (texture baseline {base_v:.2f})")
    print(f"   horizontal seams {hs}  (texture baseline {base_h:.2f})")
for rel in sys.argv[1:]:
    p=os.path.join(base,rel)
    if os.path.isdir(p):
        for f in sorted(x for x in os.listdir(p) if x.endswith(".png")): seams(os.path.join(p,f))
    else: seams(p)
