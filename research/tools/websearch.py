"""Multi-engine web search helper: searx(json) + google + bing + yandex. Compact output.

Usage:
  python websearch.py --file queries.txt [engines...]
  python websearch.py "query one" "query two" bing google
"""
import sys, io, re, html, json, urllib.parse, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


def fetch(url, timeout=30, extra=None):
    h = dict(HDRS)
    if extra:
        h.update(extra)
    try:
        r = requests.get(url, headers=h, timeout=timeout)
        return r.status_code, r.text
    except Exception as e:
        return -1, f"__ERR__ {type(e).__name__}: {str(e)[:160]}"


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def searx(q):
    st, t = fetch("https://searx.be/search?q=" + urllib.parse.quote(q) + "&format=json&language=all",
                  extra={"Accept": "application/json"})
    if st != 200:
        return [], f"status={st}"
    try:
        data = json.loads(t)
    except Exception:
        return [], "not-json"
    res = []
    for r in data.get("results", [])[:15]:
        res.append((r.get("title", ""), r.get("url", ""), (r.get("content") or "")[:240]))
    return res, "ok"


def google(q):
    st, t = fetch("https://www.google.com/search?q=" + urllib.parse.quote(q) + "&num=20&hl=ru")
    if st != 200:
        return [], f"status={st}"
    out, seen = [], set()
    for m in re.finditer(r'<a href="(/url\?q=[^"&]+[^"]*)"[^>]*>(.*?)</a>', t, re.S):
        href = urllib.parse.unquote(re.search(r"q=([^&]+)", m.group(1)).group(1))
        title = strip_tags(m.group(2))
        if title and href.startswith("http") and href not in seen:
            seen.add(href)
            out.append((title, href, ""))
    if not out:
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>\s*<h3[^>]*>(.*?)</h3>', t, re.S):
            out.append((strip_tags(m.group(2)), html.unescape(m.group(1)), ""))
    return out, "ok"


def bing(q):
    st, t = fetch("https://www.bing.com/search?q=" + urllib.parse.quote(q) + "&count=20&setlang=ru")
    if st != 200:
        return [], f"status={st}"
    out = []
    for blk in re.findall(r'<li class="b_algo".*?(?=<li class="b_algo"|</ol>)', t, re.S):
        m = re.search(r'<h2>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not m:
            continue
        sn = ""
        ms = re.search(r'<p class="b_(?:lineclamp\d|paractl)?[^"]*"[^>]*>(.*?)</p>', blk, re.S)
        if ms:
            sn = strip_tags(ms.group(1))
        out.append((strip_tags(m.group(2)), html.unescape(m.group(1)), sn[:240]))
    return out, "ok"


def yandex(q):
    st, t = fetch("https://yandex.ru/search/?text=" + urllib.parse.quote(q))
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*OrganicTitle-Link[^"]*"[^>]*>(.*?)</a>', t, re.S):
        out.append((strip_tags(m.group(2)), html.unescape(m.group(1)), ""))
    if not out:
        for m in re.finditer(r'class="Link"[^>]*href="(https?://[^"]+)"', t):
            out.append(("", html.unescape(m.group(1)), ""))
    return out, "ok"


ENGINES = {"searx": searx, "google": google, "bing": bing, "yandex": yandex}


def search(q, engines):
    seen = set()
    for en in engines:
        try:
            res, status = ENGINES[en](q)
        except Exception as e:
            print(f"  [{en}] EXC {type(e).__name__}: {e}")
            continue
        print(f"  -- {en} ({status}): {len(res)} hits")
        for title, href, snip in res:
            key = re.sub(r"[?#].*", "", href)
            if key in seen:
                continue
            seen.add(key)
            print(f"     * {title}")
            print(f"       {href}")
            if snip:
                print(f"       {snip}")
        time.sleep(0.4)
    if not seen:
        print("     (nothing)")


if __name__ == "__main__":
    args = sys.argv[1:]
    engines = [a for a in args if a in ENGINES]
    queries = [a for a in args if a not in ENGINES]
    if "--file" in queries:
        i = queries.index("--file")
        queries = queries[:i] + open(queries[i + 1], encoding="utf-8").read().splitlines()
    engines = engines or ["searx", "google", "bing", "yandex"]
    for q in queries:
        q = q.strip()
        if not q or q.startswith("#"):
            continue
        print("=" * 100)
        print("QUERY:", q)
        search(q, engines)
        sys.stdout.flush()
