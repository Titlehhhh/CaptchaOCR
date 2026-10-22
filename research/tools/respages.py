"""Fetch spigotmc.ru resource pages: description + screenshots, save images."""
import sys, io, re, os, html, urllib.parse, time, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
     "Accept": "text/html,application/xhtml+xml"}
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "candidates")
os.makedirs(OUT, exist_ok=True)
S = requests.Session()
S.headers.update(H)


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def fetch(url):
    r = S.get(url, timeout=40)
    return r.status_code, r.text


def page(slug):
    url = "https://spigotmc.ru/resources/" + slug
    st, t = fetch(url)
    print("=" * 100)
    print(slug, st, len(t))
    if st != 200:
        return
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    print("TITLE:", strip_tags(title.group(1)) if title else "?")
    # author
    for m in re.finditer(r'href="(/users/[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        pass
    m = re.search(r'class="[^"]*username[^"]*"[^>]*>(.*?)</', t, re.S)
    if m:
        print("AUTHOR:", strip_tags(m.group(1)))
    # description block
    m = re.search(r'class="[^"]*message-body[^"]*"[^>]*>(.*?)</article>', t, re.S)
    if not m:
        m = re.search(r'class="[^"]*bbWrapper[^"]*"[^>]*>(.*?)</div>\s*</div>', t, re.S)
    if m:
        print("DESC:", strip_tags(m.group(1))[:1500])
    # images
    imgs = []
    for mm in re.finditer(r'(?:src|data-src)="(https?://[^"]+\.(?:png|jpg|jpeg|gif|webp))"', t, re.I):
        u = html.unescape(mm.group(1))
        if "spigotmc" in u and "avatar" in u:
            continue
        if u not in imgs:
            imgs.append(u)
    print("IMAGES:")
    slugname = re.sub(r"[^a-zA-Z0-9]+", "_", slug)
    for i, u in enumerate(imgs[:12]):
        try:
            d = S.get(u, timeout=40)
            if d.status_code == 200 and len(d.content) > 1500:
                ext = os.path.splitext(urllib.parse.urlparse(u).path)[1] or ".png"
                p = os.path.join(OUT, f"{slugname}_{i}{ext}")
                open(p, "wb").write(d.content)
                print(f"   [{i}] {u}  -> {p} ({len(d.content)} bytes)")
            else:
                print(f"   [{i}] {u}  (status {d.status_code}, {len(d.content)} bytes)")
        except Exception as e:
            print(f"   [{i}] {u}  EXC {e}")


for a in sys.argv[1:]:
    try:
        page(a)
    except Exception as e:
        print(a, "EXC", type(e).__name__, str(e)[:200])
    sys.stdout.flush()
    time.sleep(0.6)
