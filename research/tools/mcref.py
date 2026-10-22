"""Explore mcreference.com plugin mirror + wayback CDX for spigot captcha resources."""
import sys, io, re, html, urllib.parse, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()


mode = sys.argv[1]

if mode == "mcref":
    r = requests.get("https://mcreference.com/plugins", headers=H, timeout=30)
    t = r.text
    print("status", r.status_code, len(t))
    links = sorted(set(re.findall(r'href="(/plugins/[^"]+)"', t)))
    print("plugin links:", len(links))
    for l in links[:60]:
        print("  ", l)
    # any search form / api
    for m in re.finditer(r'<form[^>]*action="([^"]+)"[^>]*>', t):
        print("FORM:", m.group(1))
    for m in re.finditer(r'(/api/[A-Za-z0-9_\-/\.?=&]+)', t):
        print("API:", m.group(1))

elif mode == "cdx":
    # wayback CDX: spigotmc.org resource urls containing captcha
    q = sys.argv[2] if len(sys.argv) > 2 else "captcha"
    url = ("http://web.archive.org/cdx/search/cdx?url=spigotmc.org/resources*"
           f"&output=json&collapse=urlkey&fl=original&limit=200000"
           f"&filter=original:.*(?i){q}.*")
    r = requests.get(url, headers=H, timeout=120)
    print("status", r.status_code, len(r.text))
    print(r.text[:20000])

elif mode == "cdx2":
    q = sys.argv[2] if len(sys.argv) > 2 else "captcha"
    url = ("http://web.archive.org/cdx/search/cdx?url=spigotmc.org/resources*"
           f"&output=json&collapse=urlkey&fl=original&limit=100000")
    r = requests.get(url, headers=H, timeout=180)
    print("status", r.status_code, len(r.text))
    rows = json.loads(r.text)
    urls = [row[0] for row in rows[1:]]
    print("total archived resource urls:", len(urls))
    hits = [u for u in urls if q.lower() in u.lower()]
    print(f"matching '{q}':", len(hits))
    for u in hits[:400]:
        print("  ", u)
