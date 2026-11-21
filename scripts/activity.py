#!/usr/bin/env python3
"""Write data/activity.json: my public GitHub activity, for Vaani.

Vaani, the assistant on roydonsequeira.com, reads this file so it can answer
"what has he been working on?" with current facts. It holds public data only:
pull requests in public repositories, pushes to my public repositories and
those repositories' descriptions. No commit messages, comments, emails, tokens
or anything from a private repository: every query asks for public data, so a
token only raises the rate limit. In the workflow that is its own GITHUB_TOKEN;
run locally without one.

Standard library only; runs daily in .github/workflows/readme-sync.yml.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "roydonsequeira")
OUT = Path(__file__).resolve().parent.parent / "data" / "activity.json"
IST = timezone(timedelta(hours=5, minutes=30))
DAYS = 7     # days listed one by one
LIMIT = 8    # items per list
# Strings that look like credentials. Public titles shouldn't hold any; an item
# that does is dropped rather than passed to a language model.
SECRET = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}"
                    r"|xox[abprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|(?i:password|passwd|secret)\s*[:=]")


def api(path: str):
    req = urllib.request.Request(f"https://api.github.com{path}", headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"{USER}-activity"})
    if token := os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def search(query: str) -> tuple[list[dict], int]:
    items, page = [], 1
    while True:
        q = urllib.parse.quote(f"{query} author:{USER} -user:{USER}")
        res = api(f"/search/issues?q={q}&sort=created&order=desc&per_page=100&page={page}")
        items += res["items"]
        if len(res["items"]) < 100:
            return items, res["total_count"]
        page += 1


def clean(text: str | None, limit: int) -> str:
    text = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", text or "")).strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def day(stamp: str) -> str:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(IST).date().isoformat()


def safe(*texts: str) -> bool:
    return not any(SECRET.search(t) for t in texts)


def pull(item: dict) -> dict:
    return {"repo": item["repository_url"].split("/repos/", 1)[1], "title": clean(item["title"], 120),
            "url": item["html_url"]}


def main() -> None:
    now = datetime.now(timezone.utc)
    today = now.astimezone(IST).date()
    first_day = (today - timedelta(days=DAYS - 1)).isoformat()

    # is:public keeps private repositories out even if a token could see them.
    merged, _ = search("is:pr is:public is:merged")
    opened_now, open_total = search("is:pr is:public is:open")
    merged = [m for m in merged if safe(m["title"])]
    by_repo = Counter(pull(m)["repo"] for m in merged)

    repos = [r for r in api(f"/users/{USER}/repos?type=owner&sort=pushed&per_page=100")
             if r.get("visibility") == "public" and not (r["private"] or r["fork"] or r["archived"])
             and r["name"].lower() != USER.lower() and safe(r["description"] or "")]
    own = {r["full_name"] for r in repos}

    days: dict[str, dict[str, list]] = defaultdict(lambda: {"merged": [], "opened": [], "pushed": []})
    for m in merged:
        if (d := day(m["pull_request"]["merged_at"])) >= first_day:
            days[d]["merged"].append(pull(m))
    for item in (search("is:pr is:public")[0] if DAYS else []):
        if (d := day(item["created_at"])) >= first_day and safe(item["title"]):
            days[d]["opened"].append(pull(item))
        elif d < first_day:
            break  # newest first
    pushes: dict[str, Counter] = defaultdict(Counter)
    for page in (1, 2, 3):
        events = api(f"/users/{USER}/events/public?per_page=100&page={page}")
        for e in events:
            if e["type"] == "PushEvent" and e.get("public") and e["repo"]["name"] in own:
                if (d := day(e["created_at"])) >= first_day:
                    # Push events no longer carry commit counts, so this counts pushes.
                    pushes[d][e["repo"]["name"].split("/", 1)[1]] += 1
        if len(events) < 100 or day(events[-1]["created_at"]) < first_day:
            break
    for d, counts in pushes.items():
        days[d]["pushed"] = [{"repo": r, "pushes": k} for r, k in counts.most_common()]

    feed = {
        "schema": 1,
        "about": "Public GitHub activity of github.com/" + USER + ", written daily for Vaani on roydonsequeira.com. "
                 "Dates are in India time (UTC+05:30).",
        "as_of": today.isoformat(),
        "generated_at": now.strftime("%Y-%m-%dT%H:%MZ"),
        "upstream": {
            "merged": len(merged), "open": open_total, "projects": len(by_repo),
            "since": min((day(m["pull_request"]["merged_at"]) for m in merged), default=None),
            "by_project": [{"repo": r, "merged": k} for r, k in sorted(by_repo.items(), key=lambda kv: (-kv[1], kv[0]))],
        },
        "days": [{"date": d, **{k: v[:LIMIT] for k, v in days[d].items()}} for d in sorted(days, reverse=True)],
        "open_pull_requests": [{**pull(i), "opened": day(i["created_at"])} for i in opened_now
                               if safe(i["title"])][:LIMIT],
        "repositories": [{"name": r["name"], "url": r["html_url"], "description": clean(r["description"], 160),
                          "language": r["language"], "stars": r["stargazers_count"], "pushed": day(r["pushed_at"])}
                         for r in repos[:5]],
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(feed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{OUT.relative_to(OUT.parent.parent)}: {len(merged)} merged, {open_total} open, "
          f"{len(feed['days'])} active days since {first_day}")


if __name__ == "__main__":
    main()
