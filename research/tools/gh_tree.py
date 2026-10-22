import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests

H = {"User-Agent": "dsh-agent", "Accept": "application/vnd.github+json"}


def tree(repo, branch="main", rec=True):
    url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive={1 if rec else 0}"
    r = requests.get(url, headers=H, timeout=40)
    print(f"--- {repo}@{branch} status={r.status_code}")
    if r.status_code != 200:
        print(r.text[:200]); return []
    out = []
    for t in r.json().get("tree", []):
        if t["type"] == "blob":
            out.append(t["path"])
            print(f"   {t.get('size',0):8d}  {t['path']}")
    return out


def raw(repo, path, branch="main"):
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    r = requests.get(url, headers={"User-Agent": "dsh-agent"}, timeout=40)
    print("=" * 100)
    print(f"### {repo}/{path}  status={r.status_code}")
    print(r.text[:20000])


if __name__ == "__main__":
    for a in sys.argv[1:]:
        if a.startswith("raw:"):
            repo, path = a[4:].split("|", 1)
            raw(repo, path)
        else:
            tree(a)
        time.sleep(1.0)
