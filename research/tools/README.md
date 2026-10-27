# `research/tools/` — one web probe with modes

The folder used to hold fifteen almost identical scripts, each written from the same
template with a different engine or request. They are now **one script**
(`websearch.py`) with a `--mode`, plus the two query lists that fed it
(`q1.txt`, `q2.txt`).

```
python research/tools/websearch.py --mode search --query "minecraft captcha plugin"
python research/tools/websearch.py --mode search --query "..." --engine searx --engine google
python research/tools/websearch.py --mode search --file research/tools/q1.txt
python research/tools/websearch.py --mode code  --query "toString reverse" [--lang python]
python research/tools/websearch.py --mode site  --query "captcha"      # spigotmc.ru
python research/tools/websearch.py --mode site  --page <slug>         # one resource page
python research/tools/websearch.py --mode site  --thread /threads/123 # one forum thread
python research/tools/websearch.py --mode mcref --query "captcha"      # mcreference.com
python research/tools/websearch.py --mode mcref --plugins             # the plugin list
python research/tools/websearch.py --mode mcref --cdx captcha         # wayback CDX
python research/tools/websearch.py --mode gh    --repo owner/repo [--raw path]
python research/tools/websearch.py --mode engines                    # reachability probe
python research/tools/websearch.py --mode dump --engine google --query "..."
python research/tools/websearch.py --mode urls                       # marketplace probe
python research/tools/websearch.py --mode ddgs --query "..."          # the ddgs backends
```

## What replaced what

| old script | mode of `websearch.py` |
|---|---|
| `websearch.py` (searx, google, bing, yandex) | `--mode search` |
| `websearch2.py` (baidu, sogou, qwant, marginalia, searxng, rambler) | `--mode search --engine baidu …` |
| `codesearch.py`, `codesearch2.py` | `--mode code` (`--lang` for the language filter) |
| `spigotru.py`, `spigotru2.py`, `spigotru3.py` | `--mode site` (`--query`, `--page`, `--thread`) |
| `respages.py`, `respages2.py` (screenshots, attachments) | `--mode site --page <slug>` |
| `mcref.py`, `mcref2.py` | `--mode mcref` (`--query`, `--plugins`, `--cdx`) |
| `engines.py`, `engines2.py` | `--mode engines` |
| `engine_probe.py` (save the HTML) | `--mode dump --engine <name>` |
| `probe.py` (marketplace endpoints) | `--mode urls` |
| `ddgs_search.py` | `--mode ddgs` |
| `gh_tree.py` | `--mode gh` |

The spigotmc.ru screenshots are still written to `research/candidates/`.

`$env:PYTHONIOENCODING="utf-8"` is required for the Cyrillic queries — without it the
console encoding breaks the output.
