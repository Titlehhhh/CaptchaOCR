"""Code search for a literal string across grep.app + sourcegraph."""
import sys, io, json, urllib.parse, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}


def grepapp(q):
    url = "https://grep.app/api/search?q=" + urllib.parse.quote(q)
    r = requests.get(url, headers=H, timeout=40)
    print("== grep.app:", r.status_code)
    if r.status_code != 200:
        print("  ", r.text[:200]); return
    d = r.json()
    hits = d.get("hits", {})
    print("  total:", hits.get("total"))
    for h in hits.get("hits", [])[:25]:
        repo = h.get("repo", {})
        path = h.get("path", {})
        repo = repo.get("raw") if isinstance(repo, dict) else repo
        path = path.get("raw") if isinstance(path, dict) else path
        print("  ", repo, "|", path)
        sn = h.get("content", {})
        sn = sn.get("snippet", "") if isinstance(sn, dict) else str(sn)
        print("      ", sn.replace("\n", " ")[:300])


def sourcegraph(q):
    url = ("https://sourcegraph.com/.api/search/stream?q=" +
           urllib.parse.quote(q) + "&v=V3&t=standard&display=60")
    r = requests.get(url, headers={**H, "Accept": "text/event-stream"}, timeout=90)
    print("== sourcegraph:", r.status_code, len(r.text))
    seen = set()
    for line in r.text.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            d = json.loads(line[6:])
        except Exception:
            continue
        if isinstance(d, list):
            for m in d:
                repo = m.get("repository")
                path = m.get("path")
                if not repo:
                    continue
                key = (repo, path)
                if key in seen:
                    continue
                seen.add(key)
                print("  ", repo, "|", path)
                for cm in (m.get("chunkMatches") or [])[:3]:
                    txt = re.sub(r"<[^>]+>", "", cm.get("content", ""))
                    print("      ", txt.replace("\n", " ")[:300])
    print("  matches:", len(seen))


import re
for q in sys.argv[1:]:
    print("#" * 100)
    print("QUERY:", q)
    for f in (grepapp, sourcegraph):
        try:
            f(q)
        except Exception as e:
            print(f.__name__, "EXC", type(e).__name__, str(e)[:200])
        time.sleep(1.2)
    sys.stdout.flush()
