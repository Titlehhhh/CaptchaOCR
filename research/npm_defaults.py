# -*- coding: utf-8 -*-
"""Scan npm captcha packages for a 150x90 default geometry (README + description)."""
import json, re, urllib.request, urllib.parse, concurrent.futures

UA = {"User-Agent": "CapthaModel-research"}


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


names = set()
for q in ("captcha", "captcha generator", "captcha image", "svg captcha", "canvas captcha"):
    try:
        d = json.loads(get("https://registry.npmjs.org/-/v1/search?text=%s&size=50"
                          % urllib.parse.quote(q)))
    except Exception as e:
        print("search failed", q, e)
        continue
    for o in d.get("objects", []):
        names.add(o["package"]["name"])
print("packages:", len(names))

PAT = re.compile(r"[^\n]{0,80}150[^\n]{0,30}90[^\n]{0,50}", re.I)


def probe(n):
    try:
        d = json.loads(get("https://registry.npmjs.org/%s/latest" % urllib.parse.quote(n)))
    except Exception:
        return n, []
    text = (d.get("readme") or "") + "\n" + (d.get("description") or "")
    hits = [m.group(0).strip() for m in PAT.finditer(text)]
    return n, hits[:5]


with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
    for n, hits in ex.map(probe, sorted(names)):
        if hits:
            print("HIT", n)
            for h in hits:
                print("    ", h[:190])
