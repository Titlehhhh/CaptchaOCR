"""Search spigotmc.ru resources / forum for a query and print compact result cards."""
import sys, io, re, html, urllib.parse, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
BASE = "https://spigotmc.ru"


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()


def get(url):
    try:
        r = requests.get(url, headers=H, timeout=30)
        return r.status_code, r.text
    except Exception as e:
        return -1, f"__ERR__ {type(e).__name__}: {str(e)[:140]}"


def search_resources(q, page=1):
    url = f"{BASE}/resources/?search={urllib.parse.quote(q)}&page={page}"
    st, t = get(url)
    print(f"  [resources] {url} status={st} len={len(t)}")
    if st != 200:
        return
    # resource cards
    for m in re.finditer(r'<div class="resource[^"]*">(.*?)(?=<div class="resource|<div class="pagination|$)', t, re.S):
        blk = m.group(1)
        link = re.search(r'href="(/resources/[^"]+)"', blk)
        title = re.search(r'class="resource-title[^"]*"[^>]*>(.*?)</', blk, re.S)
        desc = re.search(r'class="resource-description[^"]*"[^>]*>(.*?)</div>', blk, re.S)
        author = re.search(r'class="resource-author[^"]*"[^>]*>(.*?)</', blk, re.S)
        if link:
            print("   *", strip_tags(title.group(1)) if title else "?",
                  "|", strip_tags(author.group(1)) if author else "?",
                  "|", BASE + link.group(1))
            if desc:
                print("     ", strip_tags(desc.group(1))[:220])
    # fallback: any link to /resources/ with a number
    seen = set()
    for m in re.finditer(r'href="(/resources/[^"]*\d+[^"]*)"[^>]*>(.*?)</a>', t, re.S):
        if m.group(1) in seen:
            continue
        seen.add(m.group(1))
        txt = strip_tags(m.group(2))
        if txt:
            print("   -", txt[:120], "|", BASE + m.group(1))
    print("   (cards found:", len(seen), ")")


def search_forum(q, page=1):
    url = f"{BASE}/search/?q={urllib.parse.quote(q)}&page={page}"
    st, t = get(url)
    print(f"  [forum] {url} status={st} len={len(t)}")
    if st != 200:
        return
    for m in re.finditer(r'<a[^>]+href="(/threads/[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        txt = strip_tags(m.group(2))
        if txt:
            print("   *", txt[:140], "|", BASE + m.group(1))


if __name__ == "__main__":
    for q in sys.argv[1:]:
        print("=" * 100)
        print("QUERY:", q)
        search_resources(q)
        search_forum(q)
        sys.stdout.flush()
        time.sleep(0.6)
