import os,sys,collections
from PIL import Image
import numpy as np
base=os.path.join(os.path.dirname(__file__),"..","site","captchas")
def rep(path):
    im=Image.open(path).convert("RGBA")
    a=np.asarray(im)
    H,W,_=a.shape
    al=a[:,:,3]
    print(f"\n== {os.path.relpath(path,base)} {W}x{H} alpha: min={al.min()} max={al.max()} distinct={len(np.unique(al))}")
    if al.min()<255:
        n=(al<255).sum()
        print(f"   pixels with alpha<255: {n} ({100*n/(W*H):.1f}%)")
        # colour of transparent pixels
        tr=a[al<255][:,:3]
        c=collections.Counter(map(tuple,tr))
        for col,k in c.most_common(4): print("   alpha<255 rgb",col,"x",k)
    # dominant opaque colours
    op=a[al==255][:,:3]
    c=collections.Counter(map(tuple,op))
    print("   opaque palette:", [(f"#{r:02X}{g:02X}{b:02X}",k) for (r,g,b),k in c.most_common(8)])
for rel in sys.argv[1:]:
    p=os.path.join(base,rel)
    if os.path.isdir(p):
        for f in sorted(x for x in os.listdir(p) if x.endswith(".png")): rep(os.path.join(p,f))
    else: rep(p)
