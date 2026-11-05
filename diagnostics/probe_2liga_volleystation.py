#!/usr/bin/env python3
"""Compare the five II Liga groups in public VolleyStation HTML with PZPS."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from probe_leagues import ROOT, badge_logos, capture, check_standings, load_scraper, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "probe")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    scraper = load_scraper("update_pomorska3liga.py")
    second = load_scraper("update_2liga.py")
    pzps = json.loads((args.output / "2liga-extracted.json").read_text(encoding="utf-8"))
    pzps_matches = {
        (match.get("group"), match["date"], second.norm(match["home"]), second.norm(match["away"])): match
        for match in pzps["matches"]
    }
    teams_html = (args.output / "2liga-teams.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(teams_html, "html.parser")
    groups = {}
    for anchor in soup.select('a[href*="phase-"]'):
        label = " ".join(anchor.get_text(" ", strip=True).split()).casefold()
        found = re.fullmatch(r"2 liga mężczyzn grupa ([1-5])", label)
        if found:
            url = urljoin("https://2ligamezczyzn.volleystation.com/", anchor["href"])
            groups[found.group(1)] = url.rsplit("/teams/", 1)[0]
    if len(groups) != 5:
        raise RuntimeError(f"Expected five regular-season group links, found {len(groups)}")
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "groups": {}, "errors": []}
    exports = []
    with requests.Session() as session:
        for number, base in sorted(groups.items()):
            parsed = {}
            logos = {}
            for kind in ("schedule", "results", "standings"):
                name = f"2liga-vs-group-{number}-{kind}"
                url = base + f"/{kind}/"
                metadata, html = capture(session, name, url, args.output, args.offline)
                print(f"{name}: {metadata.get('status')}", flush=True)
                if metadata.get("error"):
                    report["errors"].append(f"{name}: {metadata['error']}")
                    parsed[kind] = []
                    continue
                page = BeautifulSoup(html, "html.parser")
                parsed[kind] = scraper.parse_table(page, expected_teams=None) if kind == "standings" else scraper.parse_matches(page, url)
                logos.update(badge_logos(page, url))
                if not parsed[kind]:
                    report["errors"].append(f"{name}: no rows extracted")
            by_id = {}
            for match in parsed["schedule"] + parsed["results"]:
                key = match["match_url"]
                old = by_id.get(key, {})
                by_id[key] = {**old, **match, "time": match.get("time") or old.get("time"),
                              "group": f"Grupa {number}", "competition": "II Liga Mężczyzn"}
            matches = list(by_id.values())
            for match in matches:
                old = pzps_matches.get((f"Grupa {number}", match["date"],
                                        second.norm(match["home"]), second.norm(match["away"])), {})
                if match.get("time"):
                    match["time_source"] = match["source_url"]
                elif old.get("time"):
                    match["time"] = old["time"]
                    match["time_source"] = second.PZPS_URL
                if (match.get("status") == "finished" and old.get("status") == "finished"
                        and (match["home_sets"], match["away_sets"]) == (old["home_sets"], old["away_sets"])):
                    match["set_scores"] = old.get("set_scores", [])
            exports.append({"name": f"Grupa {number}", "matches": matches,
                            "table": parsed["standings"], "logos": logos})
            report["groups"][number] = {
                "schedule": len(parsed["schedule"]), "results": len(parsed["results"]),
                "matches": len(matches), "with_time": sum(bool(match.get("time")) for match in matches),
                "with_set_scores": sum(bool(match.get("set_scores")) for match in matches),
                "standings_rows": len(parsed["standings"]), "logo_urls": len(logos),
                "table_discrepancies": check_standings(matches, parsed["standings"]),
            }
            if report["groups"][number]["table_discrepancies"]:
                report["errors"].append(f"Grupa {number}: standings do not agree with results")
    write_json(args.output / "2liga-volleystation-extracted.json", {"groups": exports})
    write_json(args.output / "2liga-volleystation-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
