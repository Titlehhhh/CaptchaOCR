"""One web-probe tool for the research folder - every old probe is a mode here.

The folder used to hold fifteen almost identical scripts (``websearch.py`` +
``websearch2.py``, ``codesearch.py`` + ``codesearch2.py``, ``respages.py`` +
``respages2.py``, ``spigotru.py``/``2``/``3``, ``mcref.py``/``2``, ``engines.py``/
``2``, ``probe.py``, ``engine_probe.py``, ``ddgs_search.py``, ``gh_tree.py``), each
written from the same template with a different engine or request.  They are now one
script with a ``--mode``:

    python research/tools/websearch.py --mode search --query "minecraft captcha plugin"
    python research/tools/websearch.py --mode search --query "..." --engine searx --engine google
    python research/tools/websearch.py --mode search --file research/tools/q1.txt
    python research/tools/websearch.py --mode code  --query "toString reverse"
    python research/tools/websearch.py --mode code  --query "..." --lang python
    python research/tools/websearch.py --mode site  --query "captcha"          # spigotmc.ru
    python research/tools/websearch.py --mode site  --page <slug>             # one resource page
    python research/tools/websearch.py --mode site  --thread /threads/12345   # one forum thread
    python research/tools/websearch.py --mode mcref --query "captcha"         # mcreference.com
    python research/tools/websearch.py --mode mcref --plugins                 # the plugin list
    python research/tools/websearch.py --mode mcref --cdx captcha             # wayback CDX
    python research/tools/websearch.py --mode gh    --repo owner/repo [--raw path]
    python research/tools/websearch.py --mode engines                        # reachability probe
    python research/tools/websearch.py --mode dump --engine google --query "..."
    python research/tools/websearch.py --mode urls                           # marketplace probe
    python research/tools/websearch.py --mode ddgs   --query "..."            # the ddgs backends

Every mode prints in the compact card format the old scripts printed, so the notes in
``reports/`` stay readable.  ``README.md`` in this folder maps the old file names onto
the modes.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.parse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover
    pass

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HDRS = {
    "User-Agent": UA,
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
JSON_HDRS = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
GH_HDRS = {"User-Agent": "dsh-agent", "Accept": "application/vnd.github+json"}

HERE = os.path.dirname(os.path.abspath(__file__))
#: where the spigotmc.ru scraper saves its pictures
CANDIDATES = os.path.join(os.path.dirname(HERE), "candidates")

SPIGOT = "https://spigotmc.ru"
MCREF = "https://mcreference.com"


# --------------------------------------------------------------------------- helpers

def strip_tags(s: str) -> str:
    """Plain text out of an HTML fragment."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def get(url: str, headers: dict | None = None, timeout: int = 30):
    """GET a URL; returns ``(status, text)`` and never raises."""
    h = dict(HDRS)
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, headers=h, timeout=timeout)
        return r.status_code, r.text
    except Exception as exc:  # noqa: BLE001 - a probe must not die on one host
        return -1, f"__ERR__ {type(exc).__name__}: {str(exc)[:160]}"


def get_json(url: str, headers: dict | None = None, timeout: int = 40):
    """GET a JSON endpoint; returns ``(status, data_or_None)``."""
    h = dict(JSON_HDRS)
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, headers=h, timeout=timeout)
        if r.status_code != 200:
            return r.status_code, None
        return r.status_code, r.json()
    except Exception as exc:  # noqa: BLE001
        return -1, f"__ERR__ {type(exc).__name__}: {str(exc)[:160]}"


def print_hits(engine: str, status, hits, limit: int = 15) -> None:
    """The card format the old probes used: one line per hit, the snippet below."""
    print(f"  -- {engine} ({status}): {len(hits)} hits")
    for title, href, snippet in hits[:limit]:
        print(f"     * {title}")
        print(f"       {href}")
        if snippet:
            print(f"       {snippet[:240]}")


# --------------------------------------------------------------------------- search engines

def searx(q: str):
    st, t = get("https://searx.be/search?q=" + urllib.parse.quote(q) +
                "&format=json&language=all", headers={"Accept": "application/json"})
    if st != 200 or not t.startswith("{"):
        return [], f"status={st}"
    try:
        data = json.loads(t)
    except Exception:  # noqa: BLE001
        return [], "not-json"
    out = [(r.get("title", ""), r.get("url", ""), (r.get("content") or "")[:240])
           for r in data.get("results", [])[:15]]
    return out, "ok"


def google(q: str):
    st, t = get("https://www.google.com/search?q=" + urllib.parse.quote(q) + "&num=20&hl=ru")
    if st != 200:
        return [], f"status={st}"
    out, seen = [], set()
    for m in re.finditer(r'<a href="(/url\?q=[^"&]+[^"]*)"[^>]*>(.*?)</a>', t, re.S):
        href = urllib.parse.unquote(re.search(r"q=([^&]+)", m.group(1)).group(1))
        title = strip_tags(m.group(2))
        if title and href.startswith("http") and href not in seen:
            seen.add(href)
            out.append((title, href, ""))
    if not out:
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>\s*<h3[^>]*>(.*?)</h3>', t, re.S):
            out.append((strip_tags(m.group(2)), html.unescape(m.group(1)), ""))
    return out, "ok"


def bing(q: str):
    st, t = get("https://www.bing.com/search?q=" + urllib.parse.quote(q) + "&count=20&setlang=ru")
    if st != 200:
        return [], f"status={st}"
    out = []
    for blk in re.findall(r'<li class="b_algo".*?(?=<li class="b_algo"|</ol>)', t, re.S):
        m = re.search(r"<h2>\s*<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", blk, re.S)
        if not m:
            continue
        sn = ""
        ms = re.search(r'<p class="b_(?:lineclamp\d|paractl)?[^"]*"[^>]*>(.*?)</p>', blk, re.S)
        if ms:
            sn = strip_tags(ms.group(1))
        out.append((strip_tags(m.group(2)), html.unescape(m.group(1)), sn[:240]))
    return out, "ok"


def yandex(q: str):
    st, t = get("https://yandex.ru/search/?text=" + urllib.parse.quote(q))
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*OrganicTitle-Link[^"]*"[^>]*>(.*?)</a>',
            t, re.S):
        out.append((strip_tags(m.group(2)), html.unescape(m.group(1)), ""))
    if not out:
        for m in re.finditer(r'class="Link"[^>]*href="(https?://[^"]+)"', t):
            out.append(("", html.unescape(m.group(1)), ""))
    return out, "ok"


def baidu(q: str):
    st, t = get("https://www.baidu.com/s?wd=" + urllib.parse.quote(q) + "&rn=20")
    if st != 200:
        return [], f"status={st}"
    out = []
    pat = (r'<div[^>]*class="result[^"]*c-container[^"]*"(.*?)(?=<div[^>]*class="result[^"]*c-container|$)')
    for m in re.finditer(pat, t, re.S):
        block = m.group(1)
        a = re.search(r'<a[^>]+href="(http[^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if a:
            out.append((strip_tags(a.group(2))[:140], html.unescape(a.group(1)),
                        strip_tags(block)[:200]))
    return out, "ok"


def sogou(q: str):
    st, t = get("https://www.sogou.com/web?query=" + urllib.parse.quote(q))
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(
            r'<h3[^>]*class="vr-title"[^>]*>(.*?)</h3>(.*?)(?=<h3[^>]*class="vr-title"|$)', t, re.S):
        a = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', m.group(1), re.S)
        if a:
            out.append((strip_tags(a.group(2))[:140], html.unescape(a.group(1)),
                        strip_tags(m.group(2))[:200]))
    return out, "ok"


def qwant(q: str):
    st, t = get("https://www.qwant.com/?q=" + urllib.parse.quote(q) + "&t=web")
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(r'"url":"(https?:[^"]+)","(?:[^"]*?)"title":"(.*?)"', t):
        out.append((m.group(2)[:140], m.group(1), ""))
    return out, "ok"


def marginalia(q: str):
    st, t = get("https://search.marginalia.nu/search?query=" + urllib.parse.quote(q))
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', t, re.S):
        out.append((strip_tags(m.group(2))[:140], html.unescape(m.group(1)), ""))
    for m in re.finditer(
            r'<a[^>]+class="[^"]*title[^"]*"[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        out.append((strip_tags(m.group(2))[:140], html.unescape(m.group(1)), ""))
    return out, "ok"


def searxng(q: str):
    st, t = get("https://priv.au/search?q=" + urllib.parse.quote(q))
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(r'<h3>\s*<a href="(https?://[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        out.append((strip_tags(m.group(2))[:140], html.unescape(m.group(1)), ""))
    for m in re.finditer(r'<article[^>]*>.*?<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        out.append((strip_tags(m.group(2))[:140], html.unescape(m.group(1)), ""))
    return out, "ok"


def rambler(q: str):
    st, t = get("https://nova.rambler.ru/search?query=" + urllib.parse.quote(q))
    if st != 200:
        return [], f"status={st}"
    out = []
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        txt = strip_tags(m.group(2))
        if txt and len(txt) > 12:
            out.append((txt[:140], html.unescape(m.group(1)), ""))
    return out, "ok"


ENGINES = {
    "searx": searx, "google": google, "bing": bing, "yandex": yandex,
    "baidu": baidu, "sogou": sogou, "qwant": qwant, "marginalia": marginalia,
    "searxng": searxng, "rambler": rambler,
}
DEFAULT_ENGINES = ["searx", "google", "bing", "yandex"]


def mode_search(args) -> int:
    queries = list(args.query or [])
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            queries += fh.read().splitlines()
    engines = args.engine or DEFAULT_ENGINES
    if not queries:
        print("nothing to search: give --query or --file", file=sys.stderr)
        return 2
    for q in queries:
        q = q.strip()
        if not q or q.startswith("#"):
            continue
        print("=" * 100)
        print("QUERY:", q)
        seen = set()
        for name in engines:
            fn = ENGINES.get(name)
            if fn is None:
                print(f"  [{name}] unknown engine")
                continue
            try:
                hits, status = fn(q)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{name}] EXC {type(exc).__name__}: {exc}")
                continue
            fresh = [(t, h, s) for (t, h, s) in hits
                     if re.sub(r"[?#].*", "", h) not in seen]
            seen.update(re.sub(r"[?#].*", "", h) for (_, h, _) in fresh)
            print_hits(name, status, fresh)
            time.sleep(0.4)
        if not seen:
            print("     (nothing)")
        sys.stdout.flush()
    return 0


# --------------------------------------------------------------------------- code search

def mode_code(args) -> int:
    queries = list(args.query or [])
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            queries += fh.read().splitlines()
    if not queries:
        print("nothing to search: give --query or --file", file=sys.stderr)
        return 2
    for q in queries:
        print("#" * 100)
        print("QUERY:", q)
        # -- grep.app
        url = "https://grep.app/api/search?q=" + urllib.parse.quote(q)
        if args.lang:
            url += "&filter[lang][0]=" + urllib.parse.quote(args.lang)
        st, data = get_json(url)
        print("== grep.app:", st)
        if isinstance(data, dict):
            hits = data.get("hits", {})
            print("  total:", hits.get("total"))
            for h in hits.get("hits", [])[:25]:
                repo = h.get("repo", {})
                path = h.get("path", {})
                repo = repo.get("raw") if isinstance(repo, dict) else repo
                path = path.get("raw") if isinstance(path, dict) else path
                sn = h.get("content", {})
                sn = sn.get("snippet", "") if isinstance(sn, dict) else str(sn)
                print("  ", repo, "|", path)
                print("      ", re.sub(r"<[^>]+>", "", sn).replace("\n", " ")[:300])
        else:
            print("  ", str(data)[:200])
        # -- sourcegraph
        url = ("https://sourcegraph.com/.api/search/stream?q=" +
               urllib.parse.quote(q) + "&v=V3&t=standard&display=60")
        st, t = get(url, headers={"Accept": "text/event-stream"}, timeout=120)
        print("== sourcegraph:", st, len(t) if isinstance(t, str) else 0)
        seen = set()
        for line in (t or "").splitlines():
            if not line.startswith("data: "):
                continue
            try:
                d = json.loads(line[6:])
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(d, list):
                continue
            for m in d:
                repo, path = m.get("repository"), m.get("path")
                if not repo or (repo, path) in seen:
                    continue
                seen.add((repo, path))
                print("  ", repo, "|", path)
                for cm in (m.get("chunkMatches") or [])[:3]:
                    txt = re.sub(r"<[^>]+>", "", cm.get("content", ""))
                    print("      ", txt.replace("\n", " ")[:300])
        print("  matches:", len(seen))
        time.sleep(1.2)
        sys.stdout.flush()
    return 0


# --------------------------------------------------------------------------- spigotmc.ru

def spigot_resources(q: str):
    url = f"{SPIGOT}/resources/?search={urllib.parse.quote(q)}"
    st, t = get(url)
    print(f"  [resources] {url} status={st} len={len(t)}")
    if st != 200:
        return
    seen = set()
    pat = r'<div class="resource[^"]*">(.*?)(?=<div class="resource|<div class="pagination|$)'
    for m in re.finditer(pat, t, re.S):
        block = m.group(1)
        link = re.search(r'href="(/resources/[^"]+)"', block)
        title = re.search(r'class="resource-title[^"]*"[^>]*>(.*?)</', block, re.S)
        desc = re.search(r'class="resource-description[^"]*"[^>]*>(.*?)</div>', block, re.S)
        author = re.search(r'class="resource-author[^"]*"[^>]*>(.*?)</', block, re.S)
        if link:
            print("   *", strip_tags(title.group(1)) if title else "?",
                  "|", strip_tags(author.group(1)) if author else "?",
                  "|", SPIGOT + link.group(1))
            if desc:
                print("     ", strip_tags(desc.group(1))[:220])
    for m in re.finditer(r'href="(/resources/[^"]*\d+[^"]*)"[^>]*>(.*?)</a>', t, re.S):
        if m.group(1) in seen:
            continue
        seen.add(m.group(1))
        txt = strip_tags(m.group(2))
        if txt:
            print("   -", txt[:120], "|", SPIGOT + m.group(1))
    print("   (cards found:", len(seen), ")")


def spigot_threads(q: str):
    """The XenForo search endpoint - the one that actually answers on spigotmc.ru."""
    url = f"{SPIGOT}/search/search?keywords={urllib.parse.quote(q)}"
    st, t = get(url, timeout=40)
    print(f"  [threads] {url} status={st} len={len(t)}")
    if st != 200:
        return
    seen = set()
    for m in re.finditer(r'href="(/threads/[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        href, txt = m.group(1), strip_tags(m.group(2))
        if not txt or href in seen:
            continue
        seen.add(href)
        print("   *", txt[:140], "|", href)


def spigot_forum(q: str):
    url = f"{SPIGOT}/search/?q={urllib.parse.quote(q)}"
    st, t = get(url)
    print(f"  [forum] {url} status={st} len={len(t)}")
    if st != 200:
        return
    for m in re.finditer(r'<a[^>]+href="(/threads/[^"]+)"[^>]*>(.*?)</a>', t, re.S):
        txt = strip_tags(m.group(2))
        if txt:
            print("   *", txt[:140], "|", SPIGOT + m.group(1))


def spigot_page(slug: str):
    """One resource page: title, author, description, screenshots and attachments."""
    url = f"{SPIGOT}/resources/{slug}"
    st, t = get(url, timeout=40)
    print("=" * 100)
    print(slug, st, len(t))
    if st != 200:
        return
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    print("TITLE:", strip_tags(title.group(1)) if title else "?")
    m = re.search(r'class="[^"]*username[^"]*"[^>]*>(.*?)</', t, re.S)
    if m:
        print("AUTHOR:", strip_tags(m.group(1)))
    m = re.search(r'class="[^"]*message-body[^"]*"[^>]*>(.*?)</article>', t, re.S)
    if not m:
        m = re.search(r'class="[^"]*bbWrapper[^"]*"[^>]*>(.*?)</div>\s*</div>', t, re.S)
    if m:
        print("DESC:", strip_tags(m.group(1))[:2000])
    images, attachments = [], []
    for mm in re.finditer(r'(?:src|data-src)="(https?://[^"]+\.(?:png|jpg|jpeg|gif|webp))"', t, re.I):
        u = html.unescape(mm.group(1))
        if "spigotmc" in u and "avatar" in u:
            continue
        if u not in images:
            images.append(u)
    for mm in re.finditer(r'href="((?:https?://[^"]*)?/attachments?/[^"]+)"', t):
        u = html.unescape(mm.group(1))
        if u.startswith("/"):
            u = SPIGOT + u
        if u not in attachments:
            attachments.append(u)
    os.makedirs(CANDIDATES, exist_ok=True)
    slugname = re.sub(r"[^a-zA-Z0-9]+", "_", slug)
    print("IMAGES:")
    for i, u in enumerate(images[:12]):
        try:
            d = requests.get(u, headers=HDRS, timeout=40)
            if d.status_code == 200 and len(d.content) > 1500:
                ext = os.path.splitext(urllib.parse.urlparse(u).path)[1] or ".png"
                path = os.path.join(CANDIDATES, f"{slugname}_{i}{ext}")
                with open(path, "wb") as fh:
                    fh.write(d.content)
                print(f"   [{i}] {u}  -> {path} ({len(d.content)} bytes)")
            else:
                print(f"   [{i}] {u}  (status {d.status_code}, {len(d.content)} bytes)")
        except Exception as exc:  # noqa: BLE001
            print(f"   [{i}] {u}  EXC {exc}")
    print("ATTACHMENTS:", len(attachments))
    for i, u in enumerate(attachments[:10]):
        try:
            d = requests.get(u, headers=HDRS, timeout=40)
            ct = d.headers.get("Content-Type", "")
            print(f"   [{i}] {u} -> {d.status_code} {ct} {len(d.content)}")
            if d.status_code == 200 and d.content[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"GIF8"):
                ext = ".png" if d.content[:4] == b"\x89PNG" else (
                    ".jpg" if d.content[:2] == b"\xff\xd8" else ".gif")
                path = os.path.join(CANDIDATES, f"{slugname}_att{i}{ext}")
                with open(path, "wb") as fh:
                    fh.write(d.content)
                print("      saved", path)
        except Exception as exc:  # noqa: BLE001
            print(f"   [{i}] {u} EXC {exc}")


def spigot_thread(url: str):
    """One forum thread: its first post."""
    st, t = get(SPIGOT + url, timeout=40)
    print("=" * 100)
    print("THREAD:", url, st)
    m = re.search(r'<div class="bbWrapper">(.*?)</div>\s*</div>', t or "", re.S)
    body = strip_tags(m.group(1)) if m else strip_tags(t or "")
    print(body[:6000])


def mode_site(args) -> int:
    if args.page:
        spigot_page(args.page)
        return 0
    if args.thread:
        spigot_thread(args.thread)
        return 0
    if not args.query:
        print("give --query, --page or --thread", file=sys.stderr)
        return 2
    for q in args.query:
        print("=" * 100)
        print("QUERY:", q)
        spigot_resources(q)
        spigot_threads(q)
        spigot_forum(q)
        time.sleep(0.6)
        sys.stdout.flush()
    return 0


# --------------------------------------------------------------------------- mcreference

def mode_mcref(args) -> int:
    if args.plugins:
        st, t = get(f"{MCREF}/plugins")
        print("status", st, len(t))
        links = sorted(set(re.findall(r'href="(/plugins/[^"]+)"', t)))
        print("plugin links:", len(links))
        for link in links[:60]:
            print("  ", link)
        for m in re.finditer(r'<form[^>]*action="([^"]+)"[^>]*>', t):
            print("FORM:", m.group(1))
        return 0
    if args.cdx:
        url = ("http://web.archive.org/cdx/search/cdx?url=spigotmc.org/resources*"
               "&output=json&collapse=urlkey&fl=original&limit=100000")
        st, t = get(url, timeout=180)
        print("status", st, len(t) if isinstance(t, str) else 0)
        try:
            rows = json.loads(t)
        except Exception:  # noqa: BLE001
            print((t or "")[:20000])
            return 1
        urls = [row[0] for row in rows[1:]]
        print("total archived resource urls:", len(urls))
        hits = [u for u in urls if args.cdx.lower() in u.lower()]
        print(f"matching '{args.cdx}':", len(hits))
        for u in hits[:400]:
            print("  ", u)
        return 0
    if not args.query:
        print("give --query, --plugins or --cdx", file=sys.stderr)
        return 2
    for q in args.query:
        st, t = get(f"{MCREF}/search?q={urllib.parse.quote(q)}", timeout=40)
        print("=" * 100)
        print("QUERY:", q, "status", st)
        for slug in sorted(set(re.findall(r'href="(/plugins/[^."]+)"', t)))[:40]:
            st2, t2 = get(MCREF + slug, timeout=40)
            title = ""
            m = re.search(r"<title>(.*?)</title>", t2, re.S)
            if m:
                title = strip_tags(m.group(1))
            desc = ""
            for pat in (r'class="[^"]*resource-description[^"]*"[^>]*>(.*?)</div>',
                        r'<meta name="description" content="([^"]*)"',
                        r'class="[^"]*description[^"]*"[^>]*>(.*?)</div>'):
                m = re.search(pat, t2, re.S)
                if m:
                    desc = strip_tags(m.group(1))
                    if len(desc) > 60:
                        break
            print("   *", slug, "|", title)
            if desc:
                print("     ", desc[:700])
            time.sleep(0.4)
    return 0


# --------------------------------------------------------------------------- GitHub

def gh_tree(repo: str, branch: str = "main"):
    url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    st, t = get(url, headers=GH_HDRS, timeout=40)
    print(f"--- {repo}@{branch} status={st}")
    if st != 200:
        print((t or "")[:200])
        return 1
    try:
        data = json.loads(t)
    except Exception:  # noqa: BLE001
        print((t or "")[:200])
        return 1
    for node in data.get("tree", []):
        if node.get("type") == "blob":
            print(f"   {node.get('size', 0):8d}  {node.get('path')}")
    return 0


def gh_raw(repo: str, path: str, branch: str = "main"):
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    st, t = get(url, headers={"User-Agent": "dsh-agent"}, timeout=40)
    print("=" * 100)
    print(f"### {repo}/{path}  status={st}")
    print((t or "")[:20000])
    return 0


def mode_gh(args) -> int:
    if not args.repo:
        print("give --repo", file=sys.stderr)
        return 2
    if args.raw:
        return gh_raw(args.repo, args.raw, args.branch)
    return gh_tree(args.repo, args.branch)


# --------------------------------------------------------------------------- probes

#: the endpoints the engine probes try
ENGINE_URLS = {
    "ddg_lite": "https://lite.duckduckgo.com/lite/?q={q}",
    "ddg_html": "https://html.duckduckgo.com/html/?q={q}",
    "mojeek": "https://www.mojeek.com/search?q={q}",
    "startpage": "https://www.startpage.com/sp/search?query={q}",
    "brave": "https://search.brave.com/search?q={q}",
    "google": "https://www.google.com/search?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "searx_be": "https://searx.be/search?q={q}",
    "marginalia": "https://search.marginalia.nu/search?query={q}",
    "rightdao": "https://rightdao.com/search?q={q}",
    "gibiru": "https://gibiru.com/results.html?q={q}",
    "search_maven": "https://search.maven.org/solrsearch/select?q={q}&rows=20&wt=json",
    "qwant_api": "https://api.qwant.com/v3/search/web?q={q}&count=10&locale=ru_RU",
    "qwant_web": "https://www.qwant.com/?q={q}&t=web",
    "ecosia": "https://www.ecosia.org/search?q={q}",
    "searxng_be": "https://priv.au/search?q={q}",
    "searchcode": "https://searchcode.com/?q={q}",
    "yep": "https://yep.com/web?q={q}",
    "lycos": "https://search.lycos.com/web/?q={q}",
    "ask": "https://www.ask.com/web?q={q}",
    "baidu": "https://www.baidu.com/s?wd={q}",
    "sogou": "https://www.sogou.com/web?query={q}",
    "mailru": "https://go.mail.ru/search?q={q}",
    "bing_img": "https://www.bing.com/images/search?q={q}",
    "yandex": "https://yandex.ru/search/?text={q}",
    "rambler": "https://nova.rambler.ru/search?query={q}",
}

#: the marketplace / archive endpoints the availability probe tries
SITE_URLS = [
    "https://www.spigotmc.org/search/search?keywords={q}",
    "https://www.spigotmc.org/resources/1.captcha.1/",
    "https://spigotmc.ru/resources/?search={q}",
    "https://spigotmc.ru/search/?q={q}",
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


def mode_engines(args) -> int:
    q = urllib.parse.quote(args.query[0] if args.query else "minecraft captcha plugin")
    for name, tpl in ENGINE_URLS.items():
        st, t = get(tpl.format(q=q), timeout=25)
        print(f"{name:14s} status={st} len={len(t) if isinstance(t, str) else 0}"
              f"{' (error)' if st < 0 else ''}")
        sys.stdout.flush()
    return 0


def mode_urls(args) -> int:
    q = urllib.parse.quote(args.query[0] if args.query else "captcha")
    for u in SITE_URLS:
        url = u.format(q=q)
        st, t = get(url, timeout=25)
        print(f"{st:4d} {len(t) if isinstance(t, str) else 0:8d}  {url}")
        sys.stdout.flush()
        time.sleep(0.4)
    return 0


def mode_dump(args) -> int:
    """Save the HTML of one engine, so a parser can be written against it."""
    name = args.engine[0] if args.engine else "google"
    url = ENGINE_URLS.get(name)
    if url is None:
        print(f"unknown engine: {name}", file=sys.stderr)
        return 2
    q = urllib.parse.quote(args.query[0] if args.query else "minecraft captcha plugin spigot")
    st, t = get(url.format(q=q), timeout=30)
    print(st, len(t) if isinstance(t, str) else 0)
    path = os.path.join(HERE, f"_{name}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(t or "")
    print("saved", path)
    return 0


def mode_ddgs(args) -> int:
    """The ddgs backends, batched (the CLI quoting breaks on Cyrillic)."""
    try:
        from ddgs import DDGS
    except ImportError:
        print("ddgs is not installed: pip install ddgs", file=sys.stderr)
        return 2
    backends = args.backend or ["google", "brave", "duckduckgo", "mojeek", "startpage", "yahoo"]
    queries = args.query or ["minecraft captcha plugin"]
    for q in queries:
        print("=" * 100)
        print("QUERY:", q)
        for backend in backends:
            try:
                with DDGS() as d:
                    res = list(d.text(q, max_results=8, backend=backend))
            except Exception as exc:  # noqa: BLE001
                print(f"  [{backend}] ERROR {type(exc).__name__}: {str(exc)[:200]}")
                continue
            print(f"  [{backend}] {len(res)} results")
            for r in res[:3]:
                print(f"      {r.get('title')}")
                print(f"      {r.get('href')}")
            time.sleep(0.5)
        sys.stdout.flush()
    return 0


# --------------------------------------------------------------------------- cli

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="websearch.py",
        description="One web-probe tool: search engines, code search, spigotmc.ru, "
                    "mcreference, GitHub and the availability probes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="modes: search, code, site, mcref, gh, engines, dump, urls, ddgs")
    ap.add_argument("--mode", default="search",
                    choices=["search", "code", "site", "mcref", "gh", "engines", "dump",
                             "urls", "ddgs"],
                    help="what to probe (default: search)")
    ap.add_argument("--query", action="append", default=[],
                    help="a query; repeat it for several")
    ap.add_argument("--file", default="",
                    help="a file with one query per line")
    ap.add_argument("--engine", action="append", default=[],
                    help="search engine (search mode) or the engine to dump (dump mode)")
    ap.add_argument("--lang", default="",
                    help="language filter for grep.app (code mode)")
    ap.add_argument("--page", default="",
                    help="a spigotmc.ru resource slug (site mode)")
    ap.add_argument("--thread", default="",
                    help="a spigotmc.ru thread path (site mode)")
    ap.add_argument("--plugins", action="store_true",
                    help="list the mcreference plugins (mcref mode)")
    ap.add_argument("--cdx", default="",
                    help="wayback CDX query for spigotmc.org resources (mcref mode)")
    ap.add_argument("--repo", default="",
                    help="owner/repo (gh mode)")
    ap.add_argument("--branch", default="main", help="branch (gh mode)")
    ap.add_argument("--raw", default="",
                    help="a file path inside the repo (gh mode)")
    ap.add_argument("--backend", action="append", default=[],
                    help="a ddgs backend (ddgs mode)")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    mode = args.mode
    if mode == "search":
        return mode_search(args)
    if mode == "code":
        return mode_code(args)
    if mode == "site":
        return mode_site(args)
    if mode == "mcref":
        return mode_mcref(args)
    if mode == "gh":
        return mode_gh(args)
    if mode == "engines":
        return mode_engines(args)
    if mode == "dump":
        return mode_dump(args)
    if mode == "urls":
        return mode_urls(args)
    if mode == "ddgs":
        return mode_ddgs(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
