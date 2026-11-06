#!/usr/bin/env python3
"""Offline, read-only quality audit for Polish II and Pomorska III men's leagues.

The audit compares official-source snapshots with the TAURON match schema,
but never fabricates missing source data or silently repairs inconsistent tables.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

BASE_MATCH_FIELDS = {
    "id", "league", "competition", "date", "time", "date_iso",
    "round", "round_source_label", "phase", "status", "home", "away",
    "home_sets", "away_sets", "set_scores", "set_points",
    "home_points", "away_points", "current_points", "source_url",
    "home_team_id", "away_team_id", "home_logo", "away_logo",
    "match_number", "term_number", "venue", "details_checked_at", "broadcast",
}


def expected_standings(matches, teams):
    rows = {team: dict(played=0, wins=0, losses=0, points=0, sets_for=0, sets_against=0)
            for team in teams}
    for match in matches:
        if match.get("status") != "finished":
            continue
        h, a = match["home"], match["away"]
        if h not in rows or a not in rows:
            continue
        hs, as_ = match.get("home_sets"), match.get("away_sets")
        if not isinstance(hs, int) or not isinstance(as_, int):
            continue
        home, away = rows[h], rows[a]
        home["played"] += 1
        away["played"] += 1
        home["wins"] += int(hs > as_)
        away["wins"] += int(as_ > hs)
        home["losses"] += int(hs < as_)
        away["losses"] += int(as_ < hs)
        home["sets_for"] += hs
        home["sets_against"] += as_
        away["sets_for"] += as_
        away["sets_against"] += hs
        home["points"] += 3 if hs == 3 and as_ <= 1 else 2 if hs == 3 else 1 if hs == 2 else 0
        away["points"] += 3 if as_ == 3 and hs <= 1 else 2 if as_ == 3 else 1 if as_ == 2 else 0
    return rows


def audit_group(group):
    matches = group["matches"]
    teams = group["teams"]
    table = group.get("table", [])
    names = {team["name"] for team in teams}
    issues, warnings = [], []
    status = Counter(match.get("status") for match in matches)
    complete_results = 0
    missing_kickoff = 0
    bad_score_ids = []
    seen = set()
    match_key_collisions = []
    incomplete_schema = 0
    for match in matches:
        key = (match["date"], match["home"], match["away"])
        if key in seen:
            match_key_collisions.append(key)
        seen.add(key)
        if match["home"] not in names or match["away"] not in names:
            issues.append(f"Unregistered team in fixture {key}")
        try:
            date = datetime.strptime(match["date"], "%d.%m.%Y")
        except (ValueError, KeyError):
            issues.append(f"Invalid date in fixture {key}")
            continue
        if not match.get("time"):
            missing_kickoff += 1
        elif not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", match["time"]):
            issues.append(f"Invalid kickoff time {key}")
        if BASE_MATCH_FIELDS - match.keys():
            incomplete_schema += 1
        if match.get("status") == "finished":
            hs, vs = match.get("home_sets"), match.get("away_sets")
            sets = match.get("set_scores") or []
            if not isinstance(hs, int) or not isinstance(vs, int) or max(hs, vs) != 3:
                issues.append(f"Invalid final sets {key}")
                continue
            points = []
            for score in sets:
                found = re.fullmatch(r"(\d{1,2}):(\d{1,2})", score)
                if not found:
                    issues.append(f"Malformed set score in {key}: {score}")
                    continue
                h, a = map(int, found.groups())
                if h == a or max(h, a) < 15 or max(h, a) > 40:
                    issues.append(f"Implausible set score {score} in {key}")
                points.append((h, a))
            if len(points) != hs + vs:
                bad_score_ids.append(key)
            elif sum(h > a for h, a in points) != hs or sum(a > h for h, a in points) != vs:
                issues.append(f"Final sets do not match set scores {key}")
            else:
                complete_results += 1
        elif match.get("status") == "scheduled":
            if match.get("set_scores") or match.get("current_points") is not None:
                issues.append(f"Scheduled fixture contains fabricated points: {key}")
        else:
            issues.append(f"Unknown match status in {key}")
    if match_key_collisions:
        issues.append(f"{len(match_key_collisions)} duplicate same-day fixtures")
    if bad_score_ids:
        warnings.append(f"{len(bad_score_ids)} completed games have incomplete set breakdown")
    derived = expected_standings(matches, names)
    mismatches = []
    for row in table:
        name = row.get("team")
        if name not in derived:
            issues.append(f"Unknown table team: {name}")
            continue
        diff = {field: {"published": row.get(field), "from_finished_matches": derived[name][field]}
                for field in ("played", "wins", "losses", "points", "sets_for", "sets_against")
                if row.get(field) != derived[name][field]}
        if diff:
            mismatches.append({"team": name, "diff": diff})
    if len(table) != len(teams):
        issues.append(f"Missing standings rows: {len(table)} / {len(teams)}")
    # A source table may include played games absent from a lagging fixture
    # snapshot; report differences as discrepancies rather than rewrite them.
    if mismatches:
        warnings.append(f"{len(mismatches)} table rows differ from the finished fixture snapshot")
    return {
        "group": group["name"],
        "matches": len(matches),
        "teams": len(teams),
        "logos": sum(bool(team.get("logo")) for team in teams),
        "finished": status["finished"],
        "scheduled": status["scheduled"],
        "finished_with_full_set_scores": complete_results,
        "missing_kickoff": missing_kickoff,
        "matches_missing_tauron_schema_fields": incomplete_schema,
        "table_rows": len(table),
        "table_discrepancies": len(mismatches),
        "table_examples": mismatches[:3],
        "finished_without_full_set_scores": [
            {"date": date, "home": home, "away": away}
            for date, home, away in bad_score_ids[:8]
        ],
        "issues": issues[:20],
        "warnings": warnings,
    }


def audit_feeds(second, third):
    groups = second.get("groups", [])
    if len(groups) != 5:
        raise ValueError(f"Expected 5 II Liga groups, got {len(groups)}")
    second_reports = [audit_group(group) for group in groups]
    third_report = audit_group({
        "name": "Pomorska III Liga",
        "matches": third.get("matches", []),
        "teams": third.get("teams", []),
        "table": third.get("table", []),
    })
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "second": {"updated_at": second.get("updated_at"), "groups": second_reports},
        "third": {"updated_at": third.get("updated_at"), "groups": [third_report]},
        "notes": [
            "Snapshot data only; live points unavailable.",
            "Table differences are not auto-corrected because fixture/result snapshots can lag.",
            "All league snapshots are preserved until an authorized upstream update succeeds.",
        ],
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--second", type=Path, default=Path("data/2liga.json"))
    parser.add_argument("--third", type=Path, default=Path("data/pomorska3liga.json"))
    parser.add_argument("--output", type=Path, default=Path("diagnostics/artifacts/lower-leagues-audit.json"))
    args = parser.parse_args()
    data = audit_feeds(
        json.loads(args.second.read_text(encoding="utf-8")),
        json.loads(args.third.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for category in ("second", "third"):
        for group in data[category]["groups"]:
            print(json.dumps({category: group}, ensure_ascii=False), flush=True)
    # This is an evidence collection job: known source defects are reported,
    # not disguised as parser crashes.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
