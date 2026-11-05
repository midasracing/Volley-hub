#!/usr/bin/env python3
"""Deep integrity audit of SuperLega and SV.League feeds against TAURON's schema.

Checks local JSON only: no network, no fabricated values, safe for every CI run.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import sys

SCHEMA_KEYS = {
    "id", "league", "competition", "date", "time", "date_iso", "round",
    "round_source_label", "phase", "status", "home", "away",
    "home_sets", "away_sets", "set_scores", "set_points", "home_points",
    "away_points", "current_points", "source_url", "home_team_id",
    "away_team_id", "home_logo", "away_logo", "match_number",
    "term_number", "venue", "details_checked_at", "broadcast",
}


def audit(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    league = data["league"]
    matches = data["matches"]
    teams = data["teams"]
    table = data["table"]
    problems = []
    warnings = []
    team_names = {team["name"] for team in teams}
    if len(teams) != 12 or len(team_names) != 12:
        problems.append(f"Expected 12 distinct clubs, got {len(teams)}")
    expected_games = {"italy": 132, "japan": 264}.get(league)
    if expected_games and len(matches) != expected_games:
        problems.append(f"Expected {expected_games} regular-season games, got {len(matches)}")
    if len({m["id"] for m in matches}) != len(matches):
        problems.append("Duplicate match IDs")
    missing_logos = [t["name"] for t in teams if not t.get("logo")]
    if missing_logos:
        problems.append("Missing logos: " + ", ".join(missing_logos))
    if len(table) != 12 or {row["team"] for row in table} != team_names:
        problems.append("Incomplete table or table team-name mismatch")
    for row in table:
        if row["played"] != row["wins"] + row["losses"]:
            problems.append("Inconsistent played/won/lost standings for " + row["team"])
    statuses = Counter()
    with_points = 0
    without_time = 0
    for match in matches:
        match_id = match.get("id", "?")
        statuses[match["status"]] += 1
        missing = SCHEMA_KEYS - match.keys()
        if missing:
            problems.append(f"{match_id}: missing TAURON keys {sorted(missing)}")
        if match["home"] not in team_names or match["away"] not in team_names:
            problems.append(f"{match_id}: unknown club name")
        if not match.get("home_logo") or not match.get("away_logo"):
            problems.append(f"{match_id}: missing match club badge")
        if not match.get("source_url", "").startswith("https://"):
            problems.append(f"{match_id}: missing source URL")
        if match["date_iso"] != datetime.strptime(match["date"], "%d.%m.%Y").strftime("%Y-%m-%d"):
            problems.append(f"{match_id}: wrong ISO date")
        if not match.get("time"):
            without_time += 1
        if league == "japan" and re.search(r"[\u3040-\u30ff\u3400-\u9fff]", match["home"] + match["away"]):
            problems.append(f"{match_id}: team name not romanized")
        if match["status"] == "finished":
            hs, vs = match["home_sets"], match["away_sets"]
            scores = match["set_scores"]
            if hs is None or vs is None or max(hs, vs) != 3 or len(scores) != hs + vs:
                problems.append(f"{match_id}: incomplete completed-match set breakdown")
            else:
                set_points = match["set_points"]
                if len(set_points) != len(scores):
                    problems.append(f"{match_id}: set point list does not match score list")
                if sum(p["home"] for p in set_points) != match["home_points"] or sum(p["away"] for p in set_points) != match["away_points"]:
                    problems.append(f"{match_id}: total points differ from individual sets")
                if sum(p["home"] > p["away"] for p in set_points) != hs:
                    problems.append(f"{match_id}: home set wins inconsistent")
                if sum(p["away"] > p["home"] for p in set_points) != vs:
                    problems.append(f"{match_id}: away set wins inconsistent")
                with_points += 1
        elif match["status"] == "scheduled":
            if match["set_scores"] or match["set_points"] or match["home_points"] or match["away_points"]:
                problems.append(f"{match_id}: future fixture has fictitious points")
            if match["current_points"] is not None:
                problems.append(f"{match_id}: future fixture has fictitious live points")
        else:
            problems.append(f"{match_id}: unexpected status {match['status']}")
    if league == "japan" and without_time:
        warnings.append(f"{without_time} future matches lack published kickoff time")
    if data.get("table_consistency_warning"):
        warnings.append(data["table_consistency_warning"])
    report = {
        "league": league,
        "matches": len(matches),
        "teams": len(teams),
        "finished": statuses["finished"],
        "scheduled": statuses["scheduled"],
        "finished_with_complete_set_points": with_points,
        "missing_kickoff_times": without_time,
        "logos": len(teams) - len(missing_logos),
        "table_rows": len(table),
        "table_source": data.get("table_source"),
        "issues": problems[:45],
        "warnings": warnings,
        "valid": not problems,
    }
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=Path("diagnostics/artifacts/international-deep-audit.json"))
    args = p.parse_args()
    records = [audit(f"data/{league}.json") for league in ("italy", "japan")]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in records:
        print(json.dumps(r, ensure_ascii=False), flush=True)
    return 0 if all(x["valid"] for x in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
