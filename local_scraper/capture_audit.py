"""Capture public source pages for the reproducible parity audit, locally."""

import argparse
import hashlib
import tempfile
from pathlib import Path

from .engines import CamoufoxBrowser, SeleniumBrowser, Session
from .feed import build_feed, source
from .second import (
    PZPS_RESULTS_URL,
    PZPS_URL,
    VOLLEYSTATION_TEAMS_URL,
    build_second,
    group_configs,
)
from .storage import atomic_json, now


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine", choices=("seleniumbase", "camoufox"), required=True)
    p.add_argument(
        "--output", type=Path, default=Path(".local-scraper/parity-captures")
    )
    p.add_argument("--browser")
    p.add_argument("--camoufox-ca", type=Path)
    p.add_argument("--headless", action="store_true")
    args = p.parse_args()
    folder = args.output / args.engine
    folder.mkdir(parents=True, exist_ok=True)
    manifest = []
    events = {}
    with tempfile.TemporaryDirectory(prefix="volley-audit-") as temporary:
        options = {"profile": Path(temporary) / "profile"}
        if args.engine == "camoufox":
            options["ca_certificate"] = args.camoufox_ca
        browser = (
            SeleniumBrowser if args.engine == "seleniumbase" else CamoufoxBrowser
        )(args.browser, args.headless, **options)
        session = Session(browser, lambda e: events.update({e["url"]: e}), budget=120)

        def fetch(url):
            existing = url in session.cache
            soup = session.fetch(url)
            if not existing:
                name = hashlib.sha256(url.encode()).hexdigest()[:20]
                html = session.cache[url]
                (folder / (name + ".html")).write_text(html, encoding="utf-8")
                manifest.append(
                    {
                        "name": name,
                        "url": url,
                        "status": events[url]["status"],
                        "challenge": False,
                        "captured_at": now(),
                        "sha256": hashlib.sha256(html.encode()).hexdigest(),
                    }
                )
                atomic_json(folder / "capture.json", manifest)
                print(f"{args.engine}: {len(manifest)} dokumentów; {url}", flush=True)
            return soup

        try:
            browser.start()
            teams = fetch(VOLLEYSTATION_TEAMS_URL)
            for _, cfg in sorted(group_configs(teams).items()):
                for kind in ["schedule", "results", "standings"]:
                    fetch(cfg["base"] + "/" + kind + "/")
            for kind in ["schedule", "results", "standings", "teams"]:
                fetch(source.BASE + "/" + kind + "/")
            fetch(PZPS_URL)
            fetch(PZPS_RESULTS_URL)
            build_second(fetch)
            build_feed(fetch, refresh_details=True)
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
