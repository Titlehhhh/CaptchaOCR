import os,sys,itertools
from PIL import Image
import numpy as np
sys.path.insert(0,os.path.dirname(__file__))
from jigsaw2 import load_tiles, cost_matrices
# The GalleryCaptcha reference gallery was removed from this repository on 2026-10-22
# (it held third-party screenshots). Point CAPTCHA_GALLERY_DIR at a local copy to use it.
base=os.environ.get("CAPTCHA_GALLERY_DIR","")
if not base:
    raise SystemExit("the reference gallery is no longer part of this repository (2026-10-22); "
                     "set CAPTCHA_GALLERY_DIR to a local copy to run this script")
def seams(tiles,perm,gx=3,gy=3):
    cV,cH=cost_matrices(tiles)
    out=[]
    for r in range(gy):
        for c in range(gx):
            p=r*gx+c
            if c>0: out.append(("H",round(float(cH[perm[p-1],perm[p]]),1)))
            if r>0: out.append(("V",round(float(cV[perm[p-gx],perm[p]]),1)))
    return out
for rel in sys.argv[1:]:
    p=os.path.join(base,rel)
    for rot in (0,180):
        tiles,xs,ys,W,H=load_tiles(p,3,3,rot)
        cV,cH=cost_matrices(tiles)
        n=9; best=(1e18,None)
        for perm in itertools.permutations(range(n)):
            tot=0.0
            for r in range(3):
                for c in range(3):
                    pp=r*3+c
                    if c>0: tot+=cH[perm[pp-1],perm[pp]]
                    if r>0: tot+=cV[perm[pp-3],perm[pp]]
                    if tot>=best[0]: break
                if tot>=best[0]: break
            if tot<best[0]: best=(tot,perm)
        sm=seams(tiles,best[1])
        print(f"{os.path.relpath(p,base)} rot={rot}: cost={best[0]:.1f}  perm={best[1]}")
        print("     seams:",sm)
