import json,os,collections
m=json.load(open(os.path.join("site","captchas","manifest.json"),encoding="utf-8"))
g=collections.OrderedDict()
for e in m: g.setdefault(e["section"],[]).append(e["url"].rsplit("/",1)[-1])
for k,v in g.items():
    print(f"--- {k}  n={len(v)}")
    print("   ", ", ".join(v[:60]))
