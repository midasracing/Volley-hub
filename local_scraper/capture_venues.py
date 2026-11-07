"""Capture public venue documents for the separate, read-only venue audit."""

import argparse
import hashlib
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .engines import is_challenge
from .storage import atomic_json, now, read_json

USER_AGENT = "KiedySiatkaVenueAudit/1.0"
HOSTS = {"sedziowie.pzps.pl", "pwzps.arbitergo.pl", "pomorskie.volleystation.com"}


def capture(output, third_feed):
    """No retry or challenge solving; errors leave a resumable manifest."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    last = {}
    robots = {}
    manifests = {}

    def get(url, folder, name):
        host = urlsplit(url).hostname
        if urlsplit(url).scheme != "https" or host not in HOSTS:
            raise ValueError("Nieoczekiwane źródło")
        folder.mkdir(parents=True, exist_ok=True)
        if folder not in manifests:
            manifests[folder] = read_json(folder / "capture.json") or []
        manifest = manifests[folder]
        previous = next((m for m in manifest if m["url"] == url), None)
        target = folder / (name + ".html")
        if previous and target.exists():
            raw = target.read_bytes()
            if hashlib.sha256(raw).hexdigest() != previous["sha256"]:
                raise ValueError("Uszkodzony zapis źródłowy")
            return BeautifulSoup(raw, "html.parser")
        if host not in robots:
            robots_url = f"https://{host}/robots.txt"
            result = session.get(robots_url, timeout=30, allow_redirects=False)
            if result.status_code not in (200, 404):
                raise RuntimeError(
                    f"Nie odczytano robots.txt: HTTP {result.status_code}"
                )
            policy = RobotFileParser(robots_url)
            policy.parse(result.text.splitlines() if result.status_code == 200 else [])
            robots[host] = policy
            last[host] = time.monotonic()
        policy = robots[host]
        if not policy.can_fetch(USER_AGENT, url):
            raise RuntimeError("Adres wyłączony z odczytu w robots.txt")
        delay = max(
            5 if host.endswith("volleystation.com") else 1,
            policy.crawl_delay(USER_AGENT) or 0,
        )
        if host in last:
            time.sleep(max(0, delay - (time.monotonic() - last[host])))
        last[host] = time.monotonic()
        result = session.get(url, timeout=30, allow_redirects=False)
        if result.status_code != 200 or is_challenge(result.text, result.headers):
            atomic_json(
                folder / "error.json",
                {
                    "url": url,
                    "status": result.status_code,
                    "retry_after": result.headers.get("Retry-After"),
                    "at": now(),
                },
            )
            raise RuntimeError(
                f"Odczyt zatrzymany: HTTP {result.status_code}; bez ponowienia"
            )
        target.write_bytes(result.content)
        manifest.append(
            {
                "url": url,
                "name": name,
                "status": 200,
                "captured_at": now(),
                "sha256": hashlib.sha256(result.content).hexdigest(),
            }
        )
        atomic_json(folder / "capture.json", manifest)
        if len(manifest) % 20 == 0:
            print(f"{folder.name}: {len(manifest)} dokumentów", flush=True)
        return BeautifulSoup(result.content, "html.parser")

    try:
        base = "https://sedziowie.pzps.pl"
        soup = get(
            base + "/system/mecze-II-liga-mezczyzn/", output / "pzps-all", "fixtures"
        )
        urls = list(
            dict.fromkeys(
                urljoin(base, a["href"]).replace("/system//", "/system/")
                for a in soup.select('a[href*="/mecz/"]')
            )
        )
        if not 1 <= len(urls) <= 600:
            raise ValueError("Nieoczekiwana liczba meczów w indeksie PZPS")
        for url in urls:
            identifier = re.search(r"/mecz/(\d+)/$", url)
            if not identifier:
                raise ValueError("Nieoczekiwany adres meczu")
            get(url, output / "pzps-all", "match-" + identifier[1])
        get(
            "https://pwzps.arbitergo.pl/delegation/List.jsf",
            output / "third-check",
            "arbitergo",
        )
        # Re-read match headers referenced by public current III liga delegates.
        # Capturing all 72 VS pages is unnecessary for testing that discrepancy.
        today = now()[:10]
        for match in read_json(third_feed)["matches"]:
            if (
                match.get("date_iso")
                and abs(
                    (
                        date.fromisoformat(match["date_iso"])
                        - date.fromisoformat(today)
                    ).days
                )
                <= 1
            ):
                get(match["source_url"], output / "third-check", match["id"])
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path(".local-scraper/venue-captures")
    )
    parser.add_argument(
        "--third-feed", type=Path, default=Path("data/pomorska3liga.json")
    )
    args = parser.parse_args()
    capture(args.output, args.third_feed)


if __name__ == "__main__":
    main()
