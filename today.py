"""Update dark_mode.svg and light_mode.svg with live GitHub stats.

Environment variables:
    ACCESS_TOKEN  GitHub personal access token (scopes: read:user, repo)
    USER_NAME     GitHub username (default: kronix-k)
"""
import datetime as dt
import os
import re
import sys
import time

import requests

USER = os.environ.get("USER_NAME", "kronix-k")
TOKEN = os.environ.get("ACCESS_TOKEN", "")
HEADERS = {"Authorization": f"bearer {TOKEN}"}
SVG_FILES = ["dark_mode.svg", "light_mode.svg"]
BAR_WIDTH = 319  # width of the full LOC progress bar in the SVG


def graphql(query, variables):
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def get_profile():
    """Return created year, followers, and list of owned non-fork repos."""
    query = """
    query($login: String!, $cursor: String) {
      user(login: $login) {
        createdAt
        followers { totalCount }
        repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          nodes { name stargazerCount }
        }
      }
    }"""
    repos, cursor, created, followers = [], None, None, 0
    while True:
        u = graphql(query, {"login": USER, "cursor": cursor})["user"]
        created = int(u["createdAt"][:4])
        followers = u["followers"]["totalCount"]
        page = u["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return created, followers, repos


def get_contributions(first_year):
    """Return (total commits, total contributions, {date: count})."""
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }"""
    commits = contribs = 0
    days = {}
    for year in range(first_year, dt.date.today().year + 1):
        c = graphql(
            query,
            {
                "login": USER,
                "from": f"{year}-01-01T00:00:00Z",
                "to": f"{year}-12-31T23:59:59Z",
            },
        )["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        contribs += c["contributionCalendar"]["totalContributions"]
        for week in c["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return commits, contribs, days


def current_streak(days):
    """Consecutive days with contributions, ending today (or yesterday)."""
    today = dt.date.today()
    day = today
    if days.get(day.isoformat(), 0) == 0:
        day -= dt.timedelta(days=1)  # today may not have a contribution yet
    streak = 0
    while days.get(day.isoformat(), 0) > 0:
        streak += 1
        day -= dt.timedelta(days=1)
    return streak


def repo_loc(repo_name):
    """Lines added/deleted by USER in one repo, via the stats API."""
    url = f"https://api.github.com/repos/{USER}/{repo_name}/stats/contributors"
    for _ in range(6):
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 202:  # GitHub is still computing the stats
            time.sleep(3)
            continue
        if r.status_code != 200:
            return 0, 0
        add = dele = 0
        for entry in r.json() or []:
            author = entry.get("author") or {}
            if author.get("login", "").lower() == USER.lower():
                for week in entry["weeks"]:
                    add += week["a"]
                    dele += week["d"]
        return add, dele
    return 0, 0


def set_text(svg, el_id, value):
    pattern = re.compile(
        r'(<(?:text|tspan)\b[^>]*\bid="%s"[^>]*>)(.*?)(</(?:text|tspan)>)' % re.escape(el_id),
        re.S,
    )
    new, n = pattern.subn(lambda m: m.group(1) + value + m.group(3), svg)
    if n == 0:
        print(f"warning: element #{el_id} not found", file=sys.stderr)
    return new


def set_bar_width(svg, el_id, width):
    pattern = re.compile(r'(<rect\b[^>]*\bid="%s"[^>]*?\bwidth=")[^"]*(")' % re.escape(el_id))
    return pattern.sub(lambda m: m.group(1) + str(width) + m.group(2), svg)


def update_svgs(stats):
    for path in SVG_FILES:
        if not os.path.exists(path):
            print(f"skip {path}: not found", file=sys.stderr)
            continue
        with open(path, encoding="utf-8") as f:
            svg = f.read()
        svg = set_text(svg, "streak_data", f"{stats['streak']:,}")
        svg = set_text(svg, "star_data", f"{stats['stars']:,}")
        svg = set_text(svg, "repo_data", f"{stats['repos']:,}")
        svg = set_text(svg, "contrib_data", f"{stats['contribs']:,}")
        svg = set_text(svg, "loc_data", f"{stats['loc']:,}")
        svg = set_text(svg, "loc_add", f"++ {stats['add']:,}")
        svg = set_text(svg, "loc_del", f"-- {stats['dele']:,}")
        svg = set_text(svg, "commit_data", f"Commits: {stats['commits']:,}")
        svg = set_text(svg, "follower_data", f"{stats['followers']:,}")
        ratio = stats["loc"] / stats["add"] if stats["add"] else 0
        svg = set_bar_width(svg, "loc_bar", round(BAR_WIDTH * max(0.0, min(1.0, ratio))))
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"updated {path}")


def main():
    if not TOKEN:
        sys.exit("ACCESS_TOKEN is not set")
    first_year, followers, repos = get_profile()
    commits, contribs, days = get_contributions(first_year)
    add = dele = 0
    for repo in repos:
        a, d = repo_loc(repo["name"])
        add += a
        dele += d
    stats = {
        "streak": current_streak(days),
        "stars": sum(r["stargazerCount"] for r in repos),
        "repos": len(repos),
        "contribs": contribs,
        "commits": commits,
        "followers": followers,
        "add": add,
        "dele": dele,
        "loc": add - dele,
    }
    print(stats)
    update_svgs(stats)


if __name__ == "__main__":
    main()
