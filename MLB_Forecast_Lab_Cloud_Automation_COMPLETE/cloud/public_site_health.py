"""External HTTP checks for the *public* Pages site, not just deployment status.

Pages can report a successful artifact deployment before its URL is reachable.
This checks actual HTML and its same-origin published forecast JSON. Only a
GitHub-generated Pages URL supplied from the deploy job is checked in CI.
"""
from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


MAX_BYTES = 6_000_000


def fetch(url):
    request = Request(url, headers={
        "User-Agent": "MLB-Forecast-Lab-public-deployment-health/1.0",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"})
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError("HTTP status " + str(response.status))
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Page payload exceeds safe size limit")
        return body


def check(base_url, *, fetcher=None):
    """Fail closed on 404s, wrong HTML, missing JSON, or broken relative paths."""
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("No Pages deployment URL was returned")
    u = urlsplit(base_url)
    if u.scheme != "https" or not u.hostname or u.username or u.password:
        raise ValueError("Invalid HTTPS Pages deployment URL")
    if u.query or u.fragment:
        raise ValueError("Pages deployment URL must be a clean site directory")
    base = base_url.rstrip("/") + "/"
    retrieve = fetcher or fetch
    markup = retrieve(base)
    if not isinstance(markup, bytes) or b"MLB Forecast Lab" not in markup:
        raise ValueError("Public index page is not the MLB Forecast Lab")
    api = urljoin(base, "data.json")
    if urlsplit(api).netloc != u.netloc:
        raise ValueError("Unexpected cross-origin data URL")
    published = json.loads(retrieve(api).decode("utf-8"))
    if not isinstance(published, dict):
        raise ValueError("Public data.json is not a JSON object")
    if not isinstance(published.get("predictions"), list):
        raise ValueError("Public data.json has no forecast collection")
    if not isinstance(published.get("updated_utc"), str):
        raise ValueError("Public data.json has no refresh timestamp")
    if not isinstance(published.get("full_distribution_validation"), dict):
        raise ValueError("Public data.json has no V17 distribution validation")
    return {"status": "reachable", "site": base, "data_url": api,
            "forecasts": len(published["predictions"]),
            "last_data_refresh_utc": published["updated_utc"]}


def retry(base_url, *, attempts=15, delay_seconds=20, checker=None, sleeper=None):
    """Give the Pages CDN time to propagate; never count a 404 as success."""
    if attempts < 1 or delay_seconds < 0:
        raise ValueError("Invalid retry policy")
    checker = checker or check
    sleeper = sleeper or time.sleep
    failures = []
    for number in range(1, attempts + 1):
        try:
            result = checker(base_url)
            return {**result, "attempt": number}
        except (HTTPError, URLError, OSError, ValueError, UnicodeError,
                TypeError, json.JSONDecodeError) as exc:
            failures.append(f"{type(exc).__name__}: {str(exc)[:180]}")
            print(f"Pages public check {number}/{attempts} failed: {failures[-1]}", flush=True)
            if number < attempts:
                sleeper(delay_seconds)
    raise RuntimeError(f"Public Pages still inaccessible after {attempts} attempts: {failures[-1]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--attempts", type=int, default=15)
    parser.add_argument("--delay-seconds", type=float, default=20.)
    args = parser.parse_args()
    print(json.dumps(retry(args.url, attempts=args.attempts,
                           delay_seconds=args.delay_seconds), indent=2))


if __name__ == "__main__":
    main()
