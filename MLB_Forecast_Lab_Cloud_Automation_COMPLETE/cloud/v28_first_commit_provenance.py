"""Read-only GitHub first-commit provenance audit for frozen MLB originals.

This supplements, but never replaces, the independent official-game denominator.
A JSON timestamp alone is insufficient to certify a prospective forecast:
the first GitHub commit containing that exact immutable prediction must also
precede scheduled first pitch. No 2026 model fitting or record mutations.
"""
from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

START = date(2026, 10, 14)
SETTLEMENT = frozenset(("official_final", "evaluation"))
REPO_PATH = "MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/predictions"


def aware(value):
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("Timezone-aware UTC timestamp required")
    return d.astimezone(timezone.utc)


def original_fields(record):
    if not isinstance(record, dict):
        raise ValueError("Original must be an object")
    return {k: v for k, v in record.items() if k not in SETTLEMENT}


def first_version(repo, filename, get):
    """Find oldest path-changing commit, then read that commit's exact blob.

    Page through the entire history; the newest commit is NOT proof of the
    first saved original. A truncated history must fail, not guess.
    """
    path = REPO_PATH + "/" + filename
    escaped = quote(path, safe="/")
    oldest = None
    for page in range(1, 101):
        commits = get("repos/" + repo + "/commits?path=" + escaped
                      + "&per_page=100&page=" + str(page))
        if not isinstance(commits, list):
            raise ValueError("Invalid GitHub commit history")
        if not commits:
            break
        for commit in commits:
            if not isinstance(commit, dict) or not commit.get("sha"):
                raise ValueError("Malformed GitHub commit")
        oldest = commits[-1]
        if len(commits) < 100:
            break
    else:
        raise ValueError("GitHub history exceeds audit pagination limit")
    if oldest is None:
        raise ValueError("No GitHub first commit for " + filename)
    sha = oldest["sha"]
    commit_time = aware(oldest["commit"]["committer"]["date"])
    item = get("repos/" + repo + "/contents/" + escaped + "?ref=" + quote(sha))
    if not isinstance(item, dict) or item.get("encoding") != "base64":
        raise ValueError("First commit content not available as base64")
    try:
        raw = base64.b64decode(item["content"], validate=False)
        record = json.loads(raw.decode("utf-8"))
    except (KeyError, ValueError, UnicodeError) as exc:
        raise ValueError("Invalid first-commit original") from exc
    return sha, commit_time, record


def verify_one(current, filename, repo, get):
    gid = filename.removesuffix(".json")
    if filename != gid + ".json" or not gid.isdigit():
        raise ValueError("Original filename is not an MLB game ID")
    if str(current.get("game_id")) != gid:
        raise ValueError("Current original game ID mismatch")
    if current.get("forecast_kind") != "original_pregame":
        raise ValueError("Not an immutable original_pregame")
    created = aware(current["forecast_created_utc"])
    start = aware(current["game_start_utc"])
    if not created < start:
        raise ValueError("Current original timestamp is not pre-first-pitch")
    sha, committed, first = first_version(repo, filename, get)
    if original_fields(current) != original_fields(first):
        raise ValueError("Immutable original differs from first GitHub commit")
    if "official_final" in first or "evaluation" in first:
        raise ValueError("First original was already settled")
    if not created <= committed < start:
        raise ValueError("First GitHub commit not within pre-first-pitch window")
    return {"game_id": gid, "first_commit": sha,
            "first_commit_utc": committed.isoformat(),
            "game_start_utc": start.isoformat(), "valid": True}


def audit(folder, repo, get):
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("Prediction folder missing")
    checked, failed, skipped = [], [], []
    for file in sorted(folder.glob("*.json")):
        try:
            current = json.loads(file.read_text(encoding="utf-8"))
            day = date.fromisoformat(str(current["date"]))
            if day < START:
                skipped.append(file.stem)
                continue
            checked.append(verify_one(current, file.name, repo, get))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            failed.append({"filename": file.name, "reason": str(exc)})
    return {"study": "V28 GitHub first-commit original provenance",
            "tracking_start": START.isoformat(), "eligible_originals": len(checked) + len(failed),
            "verified_originals": len(checked), "failed_originals": failed,
            "verified": checked, "pretracking_original_ids": skipped,
            "all_saved_originals_verified": not failed,
            "scope": "Saved original records only; missing games remain in the independent full-cohort denominator",
            "limitations": "Git commit metadata is corroborating evidence, not a cryptographic timestamp. Confirm official scheduled first-pitch time independently.",
            "changes_forecast_probabilities": False}


def github_get(endpoint):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN or GH_TOKEN required for read-only GitHub API")
    request = Request("https://api.github.com/" + endpoint, headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "User-Agent": "MLB-Forecast-Lab-first-commit-research"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--folder", type=Path, default=Path(REPO_PATH))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.repo or args.repo.count("/") != 1:
        parser.error("Pass --repo owner/name")
    result = audit(args.folder, args.repo, github_get)
    rendered = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    if result["failed_originals"]:
        raise SystemExit("First-commit provenance failed closed")


if __name__ == "__main__":
    main()
