"""Fetch spigotmc.ru resource pages + download attachments (screenshots)."""
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


def page(slug):
    url = "https://spigotmc.ru/resources/" + slug
    r = S.get(url, timeout=40)
    t = r.text
    print("=" * 100)
    print(slug, r.status_code, len(t))
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    print("TITLE:", strip_tags(title.group(1)) if title else "?")
    m = re.search(r'class="[^"]*username[^"]*"[^>]*>(.*?)</', t, re.S)
    if m:
        print("AUTHOR:", strip_tags(m.group(1)))
    m = re.search(r'class="[^"]*bbWrapper[^"]*"[^>]*>(.*?)</div>\s*</div>', t, re.S)
    if m:
        print("DESC:", strip_tags(m.group(1))[:2000])
    # attachment links
    atts = []
    for mm in re.finditer(r'href="(https?://[^"]*/attachments?/[^"]+)"', t):
        u = html.unescape(mm.group(1))
        if u not in atts:
            atts.append(u)
    for mm in re.finditer(r'href="(/attachments?/[^"]+)"', t):
        u = "https://spigotmc.ru" + html.unescape(mm.group(1))
        if u not in atts:
            atts.append(u)
    print("ATTACHMENTS:", len(atts))
    slugname = re.sub(r"[^a-zA-Z0-9]+", "_", slug)
    for i, u in enumerate(atts[:10]):
        try:
            d = S.get(u, timeout=40)
            ct = d.headers.get("Content-Type", "")
            print(f"   [{i}] {u} -> {d.status_code} {ct} {len(d.content)}")
            if d.status_code == 200 and d.content[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"GIF8"):
                ext = ".png" if d.content[:4] == b"\x89PNG" else (".jpg" if d.content[:2] == b"\xff\xd8" else ".gif")
                p = os.path.join(OUT, f"{slugname}_{i}{ext}")
                open(p, "wb").write(d.content)
                print("      saved", p)
        except Exception as e:
            print(f"   [{i}] {u} EXC {e}")


for a in sys.argv[1:]:
    try:
        page(a)
    except Exception as e:
        print(a, "EXC", type(e).__name__, str(e)[:200])
    sys.stdout.flush()
    time.sleep(0.6)
