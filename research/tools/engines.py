import sys, io, re, html, urllib.parse, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

tests = {
    "ddg_lite": "https://lite.duckduckgo.com/lite/?q={q}",
    "ddg_html": "https://html.duckduckgo.com/html/?q={q}",
    "ddg_get": "https://duckduckgo.com/html/?q={q}",
    "mojeek": "https://www.mojeek.com/search?q={q}",
    "startpage": "https://www.startpage.com/sp/search?query={q}",
    "brave": "https://search.brave.com/search?q={q}",
    "yandex_ru": "https://yandex.ru/search/?text={q}",
    "google": "https://www.google.com/search?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "bing_ru": "https://www.bing.com/search?q={q}&setlang=ru&cc=ru",
    "searx": "https://searx.be/search?q={q}&format=json",
    "marginalia": "https://search.marginalia.nu/search?query={q}",
    "rightdao": "https://rightdao.com/search?q={q}",
    "gibiru": "https://gibiru.com/results.html?q={q}",
    "search_maven": "https://search.maven.org/solrsearch/select?q={q}&rows=20&wt=json",
}

q = urllib.parse.quote("minecraft captcha plugin")
for name, tpl in tests.items():
    url = tpl.format(q=q)
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        body = r.text
        print(f"{name:14s} status={r.status_code} len={len(body)}")
    except Exception as e:
        print(f"{name:14s} EXC {type(e).__name__}: {str(e)[:120]}")
    sys.stdout.flush()
