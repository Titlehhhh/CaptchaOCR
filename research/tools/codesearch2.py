"""Code search for Russian number words that a number-to-words list would contain."""
import sys, io, re, json, urllib.parse, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}


def grepapp(q, lang=""):
    url = "https://grep.app/api/search?q=" + urllib.parse.quote(q)
    if lang:
        url += "&filter[lang][0]=" + lang
    r = requests.get(url, headers=H, timeout=40)
    print("== grep.app:", r.status_code)
    if r.status_code != 200:
        print("  ", r.text[:160]); return
    hits = r.json().get("hits", {})
    print("  total:", hits.get("total"))
    for h in hits.get("hits", [])[:20]:
        repo = h.get("repo", {}); path = h.get("path", {})
        repo = repo.get("raw") if isinstance(repo, dict) else repo
        path = path.get("raw") if isinstance(path, dict) else path
        sn = h.get("content", {})
        sn = sn.get("snippet", "") if isinstance(sn, dict) else str(sn)
        print("  ", repo, "|", path)
        print("      ", re.sub(r"<[^>]+>", "", sn).replace("\n", " ")[:260])


def sourcegraph(q):
    url = ("https://sourcegraph.com/.api/search/stream?q=" +
           urllib.parse.quote(q) + "&v=V3&t=standard&display=60")
    r = requests.get(url, headers={**H, "Accept": "text/event-stream"}, timeout=120)
    print("== sourcegraph:", r.status_code)
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
                repo, path = m.get("repository"), m.get("path")
                if not repo or (repo, path) in seen:
                    continue
                seen.add((repo, path))
                print("  ", repo, "|", path)
                for cm in (m.get("chunkMatches") or [])[:2]:
                    print("      ", re.sub(r"<[^>]+>", "", cm.get("content", "")).replace("\n", " ")[:260])
    print("  matches:", len(seen))


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
