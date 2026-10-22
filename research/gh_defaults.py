# -*- coding: utf-8 -*-
"""Scan the top GitHub 'captcha' repos for a 150x90 default geometry."""
import json, re, urllib.request, urllib.parse, concurrent.futures, sys

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CapthaModel-research",
      "Accept": "application/vnd.github+json"}

def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

queries = [
    "captcha in:name,description,readme",
    "captcha generator in:name,description",
    "captcha image in:name,description",
]

repos = {}
for q in queries:
    url = "https://api.github.com/search/repositories?q=%s&sort=stars&order=desc&per_page=100" % urllib.parse.quote(q)
    try:
        data = json.loads(get(url))
    except Exception as e:
        print("search failed:", e)
        continue
    for it in data.get("items", []):
        repos[(it["full_name"])] = it["default_branch"]
    print("query %-40s -> %d repos (total %d)" % (q, len(data.get("items", [])), len(repos)))

print("unique repos:", len(repos))

CANDIDATE_READMES = ["README.md", "readme.md", "README.MD", "Readme.md"]

def probe(item):
    full, branch = item
    for name in CANDIDATE_READMES:
        url = "https://raw.githubusercontent.com/%s/%s/%s" % (full, branch, name)
        try:
            txt = get(url, 25)
        except Exception:
            continue
        hits = []
        for m in re.finditer(r"[^\n]{0,90}150[^\n]{0,40}90[^\n]{0,60}", txt):
            hits.append(m.group(0).strip())
        for m in re.finditer(r"[^\n]{0,90}\b150\s*[x×]\s*90\b[^\n]{0,60}", txt):
            hits.append(m.group(0).strip())
        if hits:
            return full, hits[:6]
        return full, []
    return full, []

results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    for full, hits in ex.map(probe, list(repos.items())):
        if hits:
            print("HIT", full)
            for h in hits:
                print("     ", h[:200])
            results.append((full, hits))
        if len(results) > 40:
            break

print("done, %d repos with 150x90 hits" % len(results))
