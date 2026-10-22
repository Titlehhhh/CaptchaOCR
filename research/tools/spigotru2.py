import sys, io, re, os, html, urllib.parse, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
     "Accept": "text/html,application/xhtml+xml"}


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


s = requests.Session()
s.headers.update(H)


def post_search(q):
    url = "https://spigotmc.ru/search/search"
    data = {"keywords": q, "order": "relevance", "search_type": "post"}
    r = s.post(url, data=data, timeout=40)
    print("POST", url, r.status_code, len(r.text), r.url)
    t = r.text
    open(os.path.join(HERE, "_spigotru_post.html"), "w", encoding="utf-8").write(t)
    for m in re.finditer(r'href="(/threads/[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        txt = strip_tags(m.group(2))
        if txt:
            print("   *", txt[:140], "|", m.group(1))


def get_search(q):
    url = "https://spigotmc.ru/search/search?keywords=" + urllib.parse.quote(q)
    r = s.get(url, timeout=40)
    print("GET", url, r.status_code, len(r.text))
    t = r.text
    for m in re.finditer(r'href="(/threads/[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        txt = strip_tags(m.group(2))
        if txt:
            print("   *", txt[:140], "|", m.group(1))


def resource_filter(q):
    # XenForo resources list filter
    url = "https://spigotmc.ru/resources/?q=" + urllib.parse.quote(q)
    r = s.get(url, timeout=40)
    print("RES", url, r.status_code, len(r.text))
    t = r.text
    for m in re.finditer(r'href="(/resources/[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        txt = strip_tags(m.group(2))
        if txt and len(txt) > 3:
            print("   *", txt[:140], "|", m.group(1))


for q in sys.argv[1:]:
    print("#" * 100)
    print("QUERY:", q)
    post_search(q)
    get_search(q)
    resource_filter(q)
