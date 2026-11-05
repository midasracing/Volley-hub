#!/usr/bin/env python3
"""Capture source pages and exercise test copies without touching production feeds."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent


def load_scraper(filename):
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), ROOT / "scrapers" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def badge_logos(soup, page_url):
    """Use labelled team badges from HTML; never substitute the league's logo."""
    logos = {}
    for image in soup.select("img[src]"):
        url = urljoin(page_url, image.get("src", ""))
        if not re.fullmatch(r"https://assets\.volleystation\.com/website/teams/\d+/badge\.(?:png|jpe?g|webp|svg)(?:\?.*)?", url, re.I):
            continue
        name = re.sub(r"\s+logo$", "", image.get("alt", "").strip(), flags=re.I)
        if name:
            logos[" ".join(name.split())] = url
    return logos


def check_standings(matches, table):
    played, wins, points = Counter(), Counter(), Counter()
    for match in matches:
        if match.get("status") != "finished":
            continue
        home, away = match["home"], match["away"]
        h, a = match["home_sets"], match["away_sets"]
        played.update((home, away))
        wins[home if h > a else away] += 1
        points[home] += 3 if h == 3 and a < 2 else 2 if h == 3 else 1 if h == 2 else 0
        points[away] += 3 if a == 3 and h < 2 else 2 if a == 3 else 1 if a == 2 else 0
    return [{"team": row["team"], "field": field, "table": row.get(field), "results": values[row["team"]]}
            for row in table for field, values in (("played", played), ("wins", wins), ("points", points))
            if row.get(field) != values[row["team"]]]


def capture(session, name, url, output, offline):
    metadata_path = output / f"{name}.http.json"
    html_path = output / f"{name}.html"
    if offline:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
        return metadata, html
    metadata = {"url": url, "checked_at": datetime.now(timezone.utc).isoformat()}
    html = ""
    try:
        response = session.get(url, timeout=(5, 20))
        metadata.update({
            "status": response.status_code,
            "final_url": response.url,
            "content_type": response.headers.get("Content-Type"),
            "bytes": len(response.content),
            "sha256": hashlib.sha256(response.content).hexdigest(),
        })
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        metadata.update({"title": title, "tables": len(soup.select("table")),
                         "rows": len(soup.select("tr")), "links": len(soup.select("a[href]"))})
        if response.status_code != 200:
            metadata["error"] = f"HTTP {response.status_code}"
        elif any(token in title.casefold() for token in ("just a moment", "access denied", "attention required")):
            metadata["error"] = "Challenge/access-denied page, not league data"
    except requests.RequestException as error:
        metadata["error"] = str(error)
    html_path.write_text(html, encoding="utf-8")
    write_json(metadata_path, metadata)
    return metadata, html


def inspect(league, output, offline=False):
    second = load_scraper("update_2liga.py")
    third = load_scraper("update_pomorska3liga.py")
    pages = {}
    if league in ("all", "2liga"):
        pages.update({"2liga-schedule": second.PZPS_URL, "2liga-results": second.PZPS_RESULTS_URL,
                      "2liga-teams": second.VOLLEYSTATION_TEAMS_URL})
    if league in ("all", "3liga"):
        pages.update({"3liga-schedule": third.SCHEDULE_URL, "3liga-results": third.RESULTS_URL,
                      "3liga-standings": third.STANDINGS_URL})
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "offline": offline,
              "pages": {}, "extraction": {}, "errors": []}
    captured = {}
    with requests.Session() as session:
        session.headers.update(second.HEADERS)
        for name, url in pages.items():
            metadata, html = capture(session, name, url, output, offline)
            report["pages"][name] = metadata
            print(f"{name}: {metadata.get('status', 'no response')}; {metadata.get('title', '')}", flush=True)
            if metadata.get("error"):
                report["errors"].append(f"{name}: {metadata['error']}")
            else:
                captured[name] = html

    if league in ("all", "2liga"):
        # The original PZPS parsers fetch internally. Replay only the captured pages,
        # so parsing does not issue extra requests or accidentally use old feeds.
        def replay_get(url, **kwargs):
            name = next((key for key, value in pages.items() if value == url), None)
            if name not in captured:
                raise RuntimeError(f"No successful capture for {url}")
            return SimpleNamespace(text=captured[name], raise_for_status=lambda: None)

        try:
            with patch.object(second.requests, "get", side_effect=replay_get):
                matches, teams = second.parse_pzps()
                tables = second.parse_pzps_results(matches)
            groups = Counter(match.get("group") for match in matches)
            logos = badge_logos(BeautifulSoup(captured.get("2liga-teams", ""), "html.parser"),
                                second.VOLLEYSTATION_TEAMS_URL)
            result = {"matches": matches, "tables_by_group": tables, "logos": logos}
            write_json(output / "2liga-extracted.json", result)
            report["extraction"]["2liga"] = {
                "matches": len(matches), "teams": len(teams), "groups": dict(groups),
                "finished": sum(match.get("status") == "finished" for match in matches),
                "with_time": sum(bool(match.get("time")) for match in matches),
                "logo_urls": len(logos),
                "standings_rows": {group: len(rows) for group, rows in tables.items()},
                "invalid_finished_scores": [match for match in matches if match.get("status") == "finished"
                                            and max(match["home_sets"], match["away_sets"]) != 3],
            }
            if any(not rows for rows in tables.values()):
                report["errors"].append("2liga: at least one group has no extracted standings")
        except Exception as error:
            report["errors"].append(f"2liga extraction: {type(error).__name__}: {error}")

    if league in ("all", "3liga"):
        extracted = {}
        for name, html in captured.items():
            if not name.startswith("3liga-"):
                continue
            try:
                soup = BeautifulSoup(html, "html.parser")
                rows = third.parse_table(soup) if name.endswith("standings") else third.parse_matches(soup, pages[name])
                extracted[name] = rows
                write_json(output / f"{name}-extracted.json", rows)
                if not rows:
                    report["errors"].append(f"{name}: HTTP 200 but parser extracted no rows")
            except Exception as error:
                report["errors"].append(f"{name} extraction: {type(error).__name__}: {error}")
        report["extraction"]["3liga"] = {name: len(rows) for name, rows in extracted.items()}
        if "3liga-schedule" in extracted and "3liga-results" in extracted:
            by_id = {match["id"]: match for match in extracted["3liga-schedule"]}
            for result in extracted["3liga-results"]:
                previous = by_id.get(result["id"], {})
                by_id[result["id"]] = {**previous, **result, "time": result.get("time") or previous.get("time")}
            matches = list(by_id.values())
            logos = badge_logos(BeautifulSoup(captured["3liga-schedule"], "html.parser"), third.SCHEDULE_URL)
            logos.update(badge_logos(BeautifulSoup(captured["3liga-results"], "html.parser"), third.RESULTS_URL))
            with requests.Session() as session:
                for match in matches:
                    if match.get("time") or not match.get("match_url"):
                        continue
                    name = "3liga-detail-" + match["match_url"].rstrip("/").rsplit("/", 1)[-1]
                    try:
                        metadata, html = capture(session, name, match["match_url"], output, offline)
                        report["pages"][name] = metadata
                        print(f"{name}: {metadata.get('status', 'no response')}", flush=True)
                        if metadata.get("error"):
                            report["errors"].append(f"{name}: {metadata['error']}")
                            continue
                        detail = third.parse_match_detail(BeautifulSoup(html, "html.parser"))
                        match["time"] = detail["time"]
                        match["set_scores"] = detail["set_scores"]
                    except (OSError, ValueError) as error:
                        report["errors"].append(f"{name}: {error}")
            write_json(output / "3liga-extracted.json", {
                "matches": matches, "table": extracted.get("3liga-standings", []), "logos": logos,
            })
            report["extraction"]["3liga"].update({
                "matches": len(matches), "with_time": sum(bool(match.get("time")) for match in matches),
                "logo_urls": len(logos),
                "with_set_scores": sum(bool(match.get("set_scores")) for match in matches),
                "table_discrepancies": check_standings(matches, extracted.get("3liga-standings", [])),
            })
            if report["extraction"]["3liga"]["table_discrepancies"]:
                report["errors"].append("3liga: standings do not agree with extracted results")

    write_json(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", choices=("all", "2liga", "3liga"), default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "probe")
    parser.add_argument("--offline", action="store_true", help="Replay captures already in --output")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = inspect(args.league, args.output, args.offline)
    print(json.dumps(report["extraction"], ensure_ascii=False, indent=2))
    for error in report["errors"]:
        print(error, file=sys.stderr)
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
