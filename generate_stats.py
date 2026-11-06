"""Generate assets/github-stats.svg from the GitHub REST API (version 2026-03-10).

Uses:
  GET /users/{user}                              -> followers, public repo count
  GET /users/{user}/repos                        -> stars, forks, repo list
  GET /repos/{user}/{repo}/languages             -> language bytes
  GET /repos/{user}/{repo}/stats/contributors    -> commits authored (Statistics API)
"""
import json, os, sys, time, urllib.request, urllib.error
from html import escape

USER = os.environ.get("GH_USER", "Ashwin-S-10")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = os.environ.get("OUT", "assets/github-stats.svg")
BASE = "https://api.github.com"


def api(path, retries=6):
    """GET a path; retries while GitHub computes statistics (HTTP 202)."""
    req = urllib.request.Request(BASE + path, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "profile-stats-generator",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 202:          # stats not cached yet, job started
                    time.sleep(3 + attempt * 2)
                    continue
                body = r.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as e:
            if e.code in (204, 404, 422):
                return None
            raise
    return None


def paginate(path):
    page, items = 1, []
    while True:
        sep = "&" if "?" in path else "?"
        chunk = api(f"{path}{sep}per_page=100&page={page}") or []
        items += chunk
        if len(chunk) < 100:
            return items
        page += 1


def collect():
    user = api(f"/users/{USER}")
    repos = [r for r in paginate(f"/users/{USER}/repos?type=owner") if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in repos)
    langs, commits = {}, 0
    for r in repos:
        for lang, n in (api(f"/repos/{USER}/{r['name']}/languages") or {}).items():
            langs[lang] = langs.get(lang, 0) + n
        for c in api(f"/repos/{USER}/{r['name']}/stats/contributors") or []:
            if c["author"] and c["author"]["login"].lower() == USER.lower():
                commits += c["total"]
    return {
        "name": user.get("name") or USER,
        "repos": len(repos),
        "stars": stars,
        "commits": commits,
        "followers": user["followers"],
        "langs": sorted(langs.items(), key=lambda kv: -kv[1])[:5],
    }


COLORS = ["#7aa2f7", "#bb9af7", "#7dcfff", "#9ece6a", "#e0af68"]


def render(d):
    total = sum(n for _, n in d["langs"]) or 1
    rows = [("Public repos", d["repos"]), ("Stars earned", d["stars"]),
            ("Total commits", d["commits"]), ("Followers", d["followers"])]
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="210" viewBox="0 0 800 210" role="img" aria-label="GitHub stats">',
         '<style>text{font-family:Segoe UI,Ubuntu,Helvetica,Arial,sans-serif;fill:#c0caf5}'
         '.h{font-size:18px;font-weight:600;fill:#7aa2f7}.l{font-size:14px}.v{font-size:14px;font-weight:700}</style>',
         '<rect x=".5" y=".5" width="799" height="209" rx="8" fill="#1a1b27" stroke="#2f3549"/>',
         f'<text x="30" y="38" class="h">{escape(d["name"])}\'s GitHub Stats</text>',
         '<text x="430" y="38" class="h">Top Languages</text>']
    for i, (label, val) in enumerate(rows):
        y = 78 + i * 32
        s.append(f'<text x="30" y="{y}" class="l">{label}</text>'
                 f'<text x="260" y="{y}" class="v" text-anchor="end">{val}</text>')
    s.append('<rect x="430" y="58" width="340" height="10" rx="5" fill="#2f3549"/>')
    x = 430.0
    for i, (lang, n) in enumerate(d["langs"]):
        w = 340 * n / total
        s.append(f'<rect x="{x:.1f}" y="58" width="{w:.1f}" height="10" fill="{COLORS[i]}"/>')
        x += w
    for i, (lang, n) in enumerate(d["langs"]):
        y = 100 + i * 20
        s.append(f'<circle cx="436" cy="{y-4}" r="5" fill="{COLORS[i]}"/>'
                 f'<text x="450" y="{y}" class="l">{escape(lang)}</text>'
                 f'<text x="770" y="{y}" class="l" text-anchor="end">{100*n/total:.1f}%</text>')
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    data = collect()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(data))
    print("Wrote", OUT, data)
