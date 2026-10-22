"""Dump engine HTML structure to build parsers."""
import sys, io, re, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

which = sys.argv[1]
q = urllib.parse.quote(sys.argv[2] if len(sys.argv) > 2 else "minecraft captcha plugin spigot")

if which == "yandex":
    r = requests.get("https://yandex.ru/search/?text=" + q, headers=H, timeout=30)
    print(r.status_code, len(r.text))
    open(r"C:\Users\Title\Projects\CapthaModel\research\tools\_yandex.html", "w", encoding="utf-8").write(r.text)
    print("saved")
elif which == "google":
    r = requests.get("https://www.google.com/search?q=" + q + "&num=20&hl=ru", headers=H, timeout=30)
    print(r.status_code, len(r.text))
    open(r"C:\Users\Title\Projects\CapthaModel\research\tools\_google.html", "w", encoding="utf-8").write(r.text)
    print("saved")
elif which == "bing":
    r = requests.get("https://www.bing.com/search?q=" + q + "&count=20&setlang=ru", headers=H, timeout=30)
    print(r.status_code, len(r.text))
    open(r"C:\Users\Title\Projects\CapthaModel\research\tools\_bing.html", "w", encoding="utf-8").write(r.text)
    print("saved")
elif which == "startpage":
    r = requests.get("https://www.startpage.com/sp/search?query=" + q, headers=H, timeout=30)
    print(r.statusstatus if False else r.status_code, len(r.text))
    open(r"C:\Users\Title\Projects\CapthaModel\research\tools\_startpage.html", "w", encoding="utf-8").write(r.text)
    print("saved")
