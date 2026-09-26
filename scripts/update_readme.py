#!/usr/bin/env python3
"""Refresh the "Recently shipped" table in README.md from the GitHub API.

Lists my most recently pushed public repositories between the
<!-- recent-repos:start --> and <!-- recent-repos:end --> markers. Dates are
absolute, so the README only changes when a repository actually does.
Standard library only; runs daily in .github/workflows/readme-sync.yml.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "roydonsequeira")
README = Path(__file__).resolve().parent.parent / "README.md"
SKIP = {USER.lower(), "sequeira-roy"}  # profile / config repos, not projects
LIMIT = 6
START, END = "<!-- recent-repos:start -->", "<!-- recent-repos:end -->"


def api(path: str):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"{USER}-readme-sync"},
    )
    if token := os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def recent_repos() -> list[dict]:
    repos = api(f"/users/{USER}/repos?type=owner&sort=pushed&per_page=100")
    repos = [r for r in repos
             if not (r["fork"] or r["archived"] or r["private"]) and r["name"].lower() not in SKIP]
    repos.sort(key=lambda r: r["pushed_at"], reverse=True)
    return repos[:LIMIT]


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def table(repos: list[dict]) -> str:
    rows = ["| Project | What it is | Last push |", "| --- | --- | --- |"]
    for r in repos:
        pushed = datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00"))
        meta = " · ".join(filter(None, [r["language"], f"★ {r['stargazers_count']}" if r["stargazers_count"] else ""]))
        meta = f"<br><sub>{meta}</sub>" if meta else ""
        rows.append(
            f"| [**{r['name']}**]({r['html_url']}){meta} | {cell(r['description'] or '—')} | "
            f"<code>{pushed:%Y-%m-%d}</code> |"
        )
    return "\n".join(rows)


def main() -> None:
    readme = README.read_text(encoding="utf-8")
    block = f"{START}\n{table(recent_repos())}\n{END}"
    updated, count = re.subn(re.escape(START) + r".*?" + re.escape(END), lambda _: block, readme, flags=re.S)
    if count != 1:
        raise SystemExit(f"expected one {START} ... {END} block in README.md, found {count}")
    if updated != readme:
        README.write_text(updated, encoding="utf-8", newline="\n")
        print("README.md updated")
    else:
        print("README.md already current")


if __name__ == "__main__":
    main()
