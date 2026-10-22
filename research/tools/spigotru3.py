import sys, io, re, html, urllib.parse, time, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
     "Accept": "text/html,application/xhtml+xml"}
BASE = "https://spigotmc.ru"


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


S = requests.Session()
S.headers.update(H)


def search(q):
    url = f"{BASE}/search/search?keywords=" + urllib.parse.quote(q)
    r = S.get(url, timeout=40)
    t = r.text
    seen = set()
    out = []
    for m in re.finditer(r'href="(/threads/[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        txt = strip_tags(m.group(2))
        href = m.group(1)
        if not txt or href in seen:
            continue
        seen.add(href)
        out.append((txt, href))
    return out


def thread(url, limit=6000):
    r = S.get(BASE + url, timeout=40)
    t = r.text
    # first post body
    m = re.search(r'<div class="bbWrapper">(.*?)</div>\s*</div>', t, re.S)
    body = strip_tags(m.group(1)) if m else strip_tags(t)
    return r.status_code, body[:limit]


mode = sys.argv[1]
if mode == "s":
    for q in sys.argv[2:]:
        print("=" * 100)
        print("QUERY:", q)
        res = search(q)
        if not res:
            print("   (no threads)")
        for txt, href in res[:25]:
            print("   *", txt[:130], "|", href)
        sys.stdout.flush()
        time.sleep(0.5)
elif mode == "t":
    for u in sys.argv[2:]:
        st, body = thread(u)
        print("=" * 100)
        print("THREAD:", u, st)
        print(body)
        sys.stdout.flush()
        time.sleep(0.5)
