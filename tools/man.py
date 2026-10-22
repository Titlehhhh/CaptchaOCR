import json,os,collections
# The GalleryCaptcha reference gallery was removed from this repository on 2026-10-22
# (it held third-party screenshots). Point CAPTCHA_GALLERY_DIR at a local copy to use it.
base=os.environ.get("CAPTCHA_GALLERY_DIR","")
if not base:
    raise SystemExit("the reference gallery is no longer part of this repository (2026-10-22); "
                     "set CAPTCHA_GALLERY_DIR to a local copy to run this script")
m=json.load(open(os.path.join(base,"manifest.json"),encoding="utf-8"))
g=collections.OrderedDict()
for e in m: g.setdefault(e["section"],[]).append(e["url"].rsplit("/",1)[-1])
for k,v in g.items():
    print(f"--- {k}  n={len(v)}")
    print("   ", ", ".join(v[:60]))
