#!/usr/bin/env python3
"""
Scrape real daily contribution counts from GitHub's public, unauthenticated
contributions endpoint and fetch public profile / repository metadata into
data/contributions.json and data/profile.json.

Run daily by .github/workflows/update-profile-art.yml.
"""
import collections
import datetime
import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GH_PROFILE_USER", "3boudi")
CONTRIB_URL = f"https://github.com/users/{USERNAME}/contributions"
API_BASE = "https://api.github.com"

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")
CONTRIB_PATH = os.path.join(DATA_DIR, "contributions.json")
PROFILE_PATH = os.path.join(DATA_DIR, "profile.json")


def gh_headers():
    h = {
        "User-Agent": "3boudi-profile-readme-bot/1.0",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fetch_days():
    resp = requests.get(
        CONTRIB_URL,
        headers={"User-Agent": "3boudi-profile-readme-bot/1.0"},
        timeout=30,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        print("no calendar cells found -- github markup may have changed", file=sys.stderr)
        sys.exit(1)

    days = []
    for td in cells:
        date = td.get("data-date")
        if not date:
            continue
        td_id = td.get("id")
        tooltip_el = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
        text = tooltip_el.get_text(strip=True) if tooltip_el else ""
        if re.search(r"no contributions", text, re.I):
            count = 0
        else:
            m = re.match(r"(\d+)", text)
            count = int(m.group(1)) if m else 0
        days.append(
            {
                "date": date,
                "count": count,
                "level": int(td.get("data-level") or 0),
            }
        )

    days.sort(key=lambda d: d["date"])
    return days


def compute_current_streak(days):
    idx = len(days) - 1
    if idx >= 0 and days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet -- don't break an active streak on it
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days):
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_contributions_data(days):
    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"])
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    return {
        "username": USERNAME,
        "generated_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total_contributions": total,
        "active_days": active_days,
        "avg_per_active_day": round(total / active_days, 1) if active_days else 0,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly_list,
        "days": days,
    }


def fetch_profile_data():
    headers = gh_headers()
    u_resp = requests.get(f"{API_BASE}/users/{USERNAME}", headers=headers, timeout=20)
    u_resp.raise_for_status()
    user = u_resp.json()

    repos = []
    page = 1
    while True:
        r_resp = requests.get(
            f"{API_BASE}/users/{USERNAME}/repos",
            params={"per_page": 100, "page": page, "sort": "updated"},
            headers=headers,
            timeout=20,
        )
        r_resp.raise_for_status()
        batch = r_resp.json()
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    original_repos = [r for r in repos if not r.get("fork")]
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    original_stars = sum(r.get("stargazers_count", 0) for r in original_repos)

    lang_counts = collections.Counter(
        r["language"] for r in original_repos if r.get("language")
    )

    created_year = int((user.get("created_at") or "2022-01-01")[:4])
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    years_on_github = max(1, now_utc.year - created_year)

    repo_map = {}
    for r in repos:
        repo_map[r["name"]] = {
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "language": r.get("language"),
            "homepage": r.get("homepage") or "",
            "description": r.get("description") or "",
            "updated_at": r.get("updated_at") or "",
        }

    return {
        "username": USERNAME,
        "generated_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "name": user.get("name") or "Amin Halitim",
        "public_repos": user.get("public_repos", len(repos)),
        "original_repos": len(original_repos),
        "total_stars": total_stars,
        "original_stars": original_stars,
        "followers": user.get("followers", 0),
        "created_year": created_year,
        "years_on_github": years_on_github,
        "languages": dict(lang_counts.most_common()),
        "repos": repo_map,
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    days = fetch_days()
    contrib_data = build_contributions_data(days)
    with open(CONTRIB_PATH, "w", encoding="utf-8") as f:
        json.dump(contrib_data, f, indent=2)
    print(
        f"wrote data/contributions.json: {contrib_data['total_contributions']} contributions, "
        f"active {contrib_data['active_days']}, current streak {contrib_data['current_streak']['length']}, "
        f"longest streak {contrib_data['longest_streak']['length']}"
    )

    try:
        profile_data = fetch_profile_data()
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2)
        print(
            f"wrote data/profile.json: {profile_data['original_repos']} original repos, "
            f"{profile_data['total_stars']} stars, {profile_data['years_on_github']} years"
        )
    except Exception as e:
        print(f"warning: profile metadata fetch failed ({e}); keeping existing data/profile.json", file=sys.stderr)


if __name__ == "__main__":
    main()
