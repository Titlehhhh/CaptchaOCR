"""Search via baidu / sogou / qwant / marginalia / rambler / searxng (server-rendered engines)."""
import sys, io, re, json, html, urllib.parse, time, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def get(u):
    try:
        r = requests.get(u, headers=H, timeout=30)
        return r.status_code, r.text
    except Exception as e:
        return -1, f"__ERR__ {type(e).__name__}: {str(e)[:120]}"


def baidu(q):
    st, t = get("https://www.baidu.com/s?wd=" + urllib.parse.quote(q) + "&rn=20")
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(r'<div[^>]*class="result[^"]*c-container[^"]*"(.*?)(?=<div[^>]*class="result[^"]*c-container|$)', t, re.S):
        b = m.group(1)
        a = re.search(r'<a[^>]+href="(http[^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if a:
            out.append((strip_tags(a.group(2))[:140], html.unescape(a.group(1)), strip_tags(b)[:200]))
    return out, "ok"


def sogou(q):
    st, t = get("https://www.sogou.com/web?query=" + urllib.parse.quote(q))
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(r'<h3[^>]*class="vr-title"[^>]*>(.*?)</h3>(.*?)(?=<h3[^>]*class="vr-title"|$)', t, re.S):
        a = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', m.group(1), re.S)
        if a:
            out.append((strip_tags(a.group(2))[:140], html.unescape(a.group(1)), strip_tags(m.group(2))[:200]))
    return out, "ok"


def qwant(q):
    st, t = get("https://www.qwant.com/?q=" + urllib.parse.quote(q) + "&t=web")
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(r'"url":"(https?:[^"]+)","(?:[^"]*?)"title":"(.*?)"', t):
        out.append((m.group(2)[:140], m.group(1), ""))
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*data-testid="[^"]*"', t):
        pass
    return out, "ok"


def marginalia(q):
    st, t = get("https://search.marginalia.nu/search?query=" + urllib.parse.quote(q))
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', t, re.S):
        out.append((strip_tags(m.group(2))[:140], html.unescape(m.group(1)), ""))
    for m in re.finditer(r'<a[^>]+class="[^"]*title[^"]*"[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        out.append((strip_tags(m.group(2))[:140], html.unescape(m.group(1)), ""))
    return out, "ok"


def searxng(q):
    st, t = get("https://priv.au/search?q=" + urllib.parse.quote(q))
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(r'<h3>\s*<a href="(https?://[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        out.append((strip_tags(m.group(2))[:140], html.unescape(m.group(1)), ""))
    for m in re.finditer(r'<article[^>]*>.*?<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        out.append((strip_tags(m.group(2))[:140], html.unescape(m.group(1)), ""))
    return out, "ok"


def rambler(q):
    st, t = get("https://nova.rambler.ru/search?query=" + urllib.parse.quote(q))
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        txt = strip_tags(m.group(2))
        if txt and len(txt) > 12:
            out.append((txt[:140], html.unescape(m.group(1)), ""))
    return out, "ok"


ENGINES = {"baidu": baidu, "sogou": sogou, "qwant": qwant, "marginalia": marginalia,
           "searxng": searxng, "rambler": rambler}

if __name__ == "__main__":
    args = sys.argv[1:]
    engines = [a for a in args if a in ENGINES] or list(ENGINES)
    queries = [a for a in args if a not in ENGINES]
    if "--file" in queries:
        i = queries.index("--file")
        queries = queries[:i] + open(queries[i + 1], encoding="utf-8").read().splitlines()
    for q in queries:
        q = q.strip()
        if not q:
            continue
        print("=" * 100)
        print("QUERY:", q)
        seen = set()
        for en in engines:
            try:
                res, status = ENGINES[en](q)
            except Exception as e:
                print(f"  [{en}] EXC {type(e).__name__}: {e}")
                continue
            print(f"  -- {en} ({status}): {len(res)}")
            for title, href, snip in res[:12]:
                if href in seen:
                    continue
                seen.add(href)
                print(f"     * {title}")
                print(f"       {href}")
                if snip:
                    print(f"       {snip[:200]}")
            time.sleep(0.3)
        if not seen:
            print("     (nothing)")
        sys.stdout.flush()
