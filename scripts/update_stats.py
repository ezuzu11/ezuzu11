#!/usr/bin/env python3
"""
Pulls this account's real GitHub contribution data and writes it straight
into README.md as plain text/ASCII — no external image service involved.

Requires an environment variable GH_TOKEN with at least `read:user` scope
(the default GITHUB_TOKEN in Actions works fine for reading public
contribution data).
"""

import os
import sys
import json
import urllib.request
from datetime import datetime, timedelta

GITHUB_USER = os.environ.get("GH_USERNAME", "ezuzu11")
GH_TOKEN = os.environ.get("GH_TOKEN")
README_PATH = os.environ.get("README_PATH", "README.md")

START_MARKER = "<!-- STATS:START -->"
END_MARKER = "<!-- STATS:END -->"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def fetch_contributions():
    if not GH_TOKEN:
        print("GH_TOKEN not set — cannot query GitHub API.", file=sys.stderr)
        sys.exit(1)

    body = json.dumps({"query": QUERY, "variables": {"login": GITHUB_USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {GH_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": GITHUB_USER,
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    days.sort()
    return calendar["totalContributions"], days


def compute_streaks(days):
    current = 0
    longest = 0
    running = 0
    today = datetime.utcnow().date()

    for date_str, count in days:
        if count > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    # current streak: walk backwards from today (or yesterday if today has no data yet)
    by_date = {d: c for d, c in days}
    cursor = today
    while True:
        key = cursor.isoformat()
        if key not in by_date:
            cursor -= timedelta(days=1)
            continue
        if by_date[key] > 0:
            current += 1
            cursor -= timedelta(days=1)
        else:
            break
    return current, longest


def bar(count, scale):
    if count == 0:
        return "·"
    blocks = min(10, max(1, round(count / scale)))
    return "█" * blocks


def build_table(days, num_days=14):
    recent = days[-num_days:]
    max_count = max((c for _, c in recent), default=1) or 1
    scale = max(1, max_count / 10)

    lines = []
    lines.append("| Date       | Contributions | Activity |")
    lines.append("|------------|---------------|----------|")
    for date_str, count in recent:
        label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d")
        lines.append(f"| {label:<10} | {count:^13} | {bar(count, scale):<10} |")
    return "\n".join(lines)


def main():
    total, days = fetch_contributions()
    current_streak, longest_streak = compute_streaks(days)
    table = build_table(days)
    updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    block = f"""{START_MARKER}
**Total contributions:** {total}  ·  **Current streak:** {current_streak} day(s)  ·  **Longest streak:** {longest_streak} day(s)

{table}

<sub>Last updated: {updated}</sub>
{END_MARKER}"""

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        print("Markers not found in README.md — nothing updated.", file=sys.stderr)
        sys.exit(1)

    before = content.split(START_MARKER)[0]
    after = content.split(END_MARKER)[1]
    new_content = before + block + after

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("README.md updated.")


if __name__ == "__main__":
    main()
