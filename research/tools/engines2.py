import sys, io, re, json, html, urllib.parse, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

Q = urllib.parse.quote("капча minecraft плагин")

CAND = {
    "rambler": "https://nova.rambler.ru/search?query=" + Q,
    "qwant_api": "https://api.qwant.com/v3/search/web?q=" + Q + "&count=10&locale=ru_RU&offset=0&device=desktop&safesearch=1",
    "qwant_web": "https://www.qwant.com/?q=" + Q + "&t=web",
    "ecosia": "https://www.ecosia.org/search?q=" + Q,
    "marginalia": "https://search.marginalia.nu/search?query=" + Q,
    "gibiru": "https://gibiru.com/results.html?q=" + Q,
    "rightdao": "https://rightdao.com/search?q=" + Q,
    "searx_be": "https://searx.be/search?q=" + Q,
    "searxng_priv": "https://priv.au/search?q=" + Q,
    "searxng_be": "https://searx.be/search?q=" + Q + "&language=ru",
    "searchcode": "https://searchcode.com/?q=" + Q,
    "yep": "https://yep.com/web?q=" + Q,
    "lycos": "https://search.lycos.com/web/?q=" + Q,
    "ask": "https://www.ask.com/web?q=" + Q,
    "baidu": "https://www.baidu.com/s?wd=" + Q,
    "sogou": "https://www.sogou.com/web?query=" + Q,
    "mailru": "https://go.mail.ru/search?q=" + Q,
    "bing_img": "https://www.bing.com/images/search?q=" + Q,
}

for name, u in CAND.items():
    try:
        r = requests.get(u, headers=H, timeout=25)
        body = r.text
        n_links = len(set(re.findall(r'href="(https?://[^"]+)"', body)))
        print(f"{name:14s} {r.status_code} len={len(body):7d} links={n_links}")
    except Exception as e:
        print(f"{name:14s} EXC {type(e).__name__}: {str(e)[:100]}")
    sys.stdout.flush()
