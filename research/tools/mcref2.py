"""Fetch mcreference plugin pages and print their descriptions."""
import sys, io, re, html, urllib.parse, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
     "Accept": "text/html,application/xhtml+xml"}


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def search(q):
    r = requests.get("https://mcreference.com/search?q=" + urllib.parse.quote(q), headers=H, timeout=40)
    return sorted(set(re.findall(r'href="(/plugins/[^."]+)"', r.text)))


def page(slug):
    r = requests.get("https://mcreference.com" + slug, headers=H, timeout=40)
    t = r.text
    title = ""
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    if m:
        title = strip_tags(m.group(1))
    # description block
    desc = ""
    for pat in (r'class="[^"]*resource-description[^"]*"[^>]*>(.*?)</div>',
                r'<meta name="description" content="([^"]*)"',
                r'class="[^"]*description[^"]*"[^>]*>(.*?)</div>'):
        m = re.search(pat, t, re.S)
        if m:
            desc = strip_tags(m.group(1))
            if len(desc) > 60:
                break
    # body text for keyword scan
    body = strip_tags(re.sub(r"(?s)<(script|style).*?</\1>", " ", t))
    kws = []
    for kw in ("250", "150", "пропис", "картинк", "изображен", "в чат", "чат", "цифр",
               "русск", "Cyrillic", "числ", "слов", "карта", "map", "изображ"):
        if kw.lower() in body.lower():
            kws.append(kw)
    return title, desc[:700], kws, len(body)


slugs = sys.argv[1:]
for s in slugs:
    try:
        title, desc, kws, n = page(s)
        print("=" * 100)
        print(s, "|", title)
        print("  KW:", ",".join(kws))
        print("  ", desc)
    except Exception as e:
        print(s, "EXC", type(e).__name__, str(e)[:150])
    sys.stdout.flush()
    time.sleep(0.4)
