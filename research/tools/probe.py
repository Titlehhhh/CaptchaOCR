"""Probe marketplace / archive endpoints for availability."""
import sys, io, urllib.parse, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

urls = [
    "https://www.spigotmc.org/search/search?keywords=" + urllib.parse.quote("капча"),
    "https://www.spigotmc.org/resources/1.captcha.1/",
    "https://spigotmc.ru/resources/?search=" + urllib.parse.quote("капча"),
    "https://spigotmc.ru/search/?q=" + urllib.parse.quote("капча"),
    "https://mcreference.com/plugins",
    "https://www.craftit.ru/",
    "https://modrinth.com/plugin?query=captcha",
    "https://hangar.papermc.io/",
    "http://web.archive.org/web/2023/https://www.spigotmc.org/resources/1.captcha.1/",
    "https://api.spigotmc.org/",
    "https://hub.spigotmc.org/",
    "https://www.minecraftforum.ru/",
    "https://mcorep.ru/",
    "https://dandynes.ru/",
]

for u in urls:
    try:
        r = requests.get(u, headers=H, timeout=25, allow_redirects=True)
        print(f"{r.status_code} {len(r.text):8d}  {u}")
    except Exception as e:
        print(f"EXC {type(e).__name__:20s} {u}  {str(e)[:90]}")
    sys.stdout.flush()
    time.sleep(0.4)
