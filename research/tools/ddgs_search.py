"""Batch DDGS search helper - avoids Windows CLI quoting problems with Cyrillic + quotes."""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from ddgs import DDGS

QUERIES = [
    'minecraft captcha plugin',
]

BACKENDS = ["google", "brave", "duckduckgo", "mojeek", "startpage", "yahoo"]

def run(q, backend):
    try:
        with DDGS() as d:
            return list(d.text(q, max_results=8, backend=backend))
    except Exception as e:
        return [{"error": f"{type(e).__name__}: {e}"}]

for q in QUERIES:
    print("=" * 100)
    print("QUERY:", q)
    for b in BACKENDS:
        res = run(q, b)
        errs = [r for r in res if "error" in r]
        if errs:
            print(f"  [{b}] ERROR {errs[0]['error'][:200]}")
        else:
            print(f"  [{b}] {len(res)} results")
            for r in res[:3]:
                print(f"      {r.get('title')}")
                print(f"      {r.get('href')}")
        time.sleep(0.5)
    sys.stdout.flush()
