#!/usr/bin/env python3
"""Fetch II Liga fixtures, results and standings from the official PZPS referee system."""
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PZPS_URL = "https://sedziowie.pzps.pl/system/mecze-II-liga-mezczyzn/"
PZPS_RESULTS_URL = "https://sedziowie.pzps.pl/system//index.php?mode=12&type=9"
OUT = Path("data/2liga.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VolleyHub/1.0)"}


def clean(value):
    return " ".join(value.replace("\xa0", " ").split())


def norm(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", value)


def parse_pzps():
    response = requests.get(PZPS_URL, timeout=30, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    matches, teams, group = [], set(), ""
    seen = set()
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "tr"]):
        if node.name != "tr":
            heading = clean(" ".join(node.stripped_strings))
            found = re.search(r"Grupa\s+(\d+)", heading, re.I)
            if found:
                group = f"Grupa {found.group(1)}"
            continue
        cells = [clean(td.get_text(" ", strip=True)) for td in node.find_all("td")]
        if len(cells) < 5:
            continue
        date_index = next((i for i, cell in enumerate(cells) if re.search(r"20\d{2}-\d{2}-\d{2}", cell)), None)
        if date_index is None or date_index + 3 >= len(cells):
            continue
        dm = re.search(r"(20\d{2})-(\d{2})-(\d{2})", cells[date_index])
        if not dm:
            continue
        year, month, day = dm.groups()
        date = f"{day}.{month}.{year}"
        tm = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", cells[date_index])
        time = f"{int(tm.group(1)):02d}:{tm.group(2)}" if tm else ""
        home = cells[date_index + 1].strip()
        sep = date_index + 2
        away_index = date_index + 3
        if cells[sep] not in {"-", "–", "—"}:
            sep = next((i for i in range(date_index + 1, len(cells)) if cells[i] in {"-", "–", "—"}), -1)
            if sep < 1 or sep + 1 >= len(cells):
                continue
            home, away_index = cells[sep - 1].strip(), sep + 1
        away = cells[away_index].strip()
        if not home or not away or home.lower() in {"pauzuje", "bye"} or away.lower() in {"pauzuje", "bye"}:
            continue
        if home.lower() in {"i", "ii", "kw"} or away.lower() in {"i", "ii", "kw"}:
            continue
        key = (group, date, time, home, away)
        if key in seen:
            continue
        seen.add(key)
        teams.update((home, away))
        matches.append({
            "date": date, "time": time, "home": home, "away": away,
            "home_sets": None, "away_sets": None, "set_scores": [],
            "status": "scheduled",
            "competition": f"II Liga Mężczyzn · {group}" if group else "II Liga Mężczyzn",
            "group": group,
        })
    if not matches:
        raise RuntimeError("PZPS page loaded, but no match rows were parsed.")
    matches.sort(key=lambda m: (datetime.strptime(m["date"], "%d.%m.%Y"), m["time"]))
    return matches, teams


def parse_pzps_results(matches):
    """Parse played scores and standings from the official PZPS results page."""
    response = requests.get(PZPS_RESULTS_URL, timeout=30, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    # Rows on this page contain: match id, ISO date, home, separator, away, set score.
    for row in soup.find_all("tr"):
        cells = [clean(td.get_text(" ", strip=True)) for td in row.find_all("td")]
        if len(cells) < 6:
            continue
        date_index = next((i for i, cell in enumerate(cells) if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", cell)), None)
        if date_index is None or date_index + 4 >= len(cells):
            continue
        home = cells[date_index + 1].strip()
        away_index = date_index + 3
        if cells[date_index + 2] not in {"-", "–", "—"}:
            sep = next((i for i in range(date_index + 1, len(cells)) if cells[i] in {"-", "–", "—"}), -1)
            if sep < 1 or sep + 1 >= len(cells):
                continue
            home, away_index = cells[sep - 1], sep + 1
        away = cells[away_index].strip()
        score_cell = " ".join(cells[away_index + 1:])
        set_match = re.search(r"\b([0-3])\s*:\s*([0-3])\b", score_cell)
        if not home or not away or not set_match:
            continue
        year, month, day = cells[date_index].split("-")
        results.append({
            "date": f"{day}.{month}.{year}", "home": home, "away": away,
            "home_sets": int(set_match.group(1)), "away_sets": int(set_match.group(2)),
            "set_scores": re.findall(r"\b\d{1,2}\s*:\s*\d{1,2}\b", score_cell)[1:]
        })

    # Match results onto the fixture list by team pair. PZPS occasionally uses
    # a leading zero/spacing variation in team names, so compare normalized names.
    for result in results:
        pair = {norm(result["home"]), norm(result["away"])}
        candidates = [m for m in matches
                      if {norm(m["home"]), norm(m["away"])} == pair]
        if not candidates:
            candidates = [m for m in matches
                          if all(any(n.startswith(norm(team)[:12]) or norm(team).startswith(n[:12])
                                     for n in (norm(m["home"]), norm(m["away"])))
                                 for team in (result["home"], result["away"]))]
        if candidates:
            match = next((m for m in candidates if m["date"] == result["date"]), candidates[0])
            match.update({k: result[k] for k in ("home_sets", "away_sets", "set_scores")})
            match["status"] = "finished" if result["home_sets"] + result["away_sets"] > 0 else "scheduled"

    # Parse standings tables when the page exposes them. Keep rows grouped by
    # team membership from the fixture list; do not fabricate standings.
    tables_by_group = {f"Grupa {i}": [] for i in range(1, 6)}
    team_group = {}
    for match in matches:
        if match.get("group"):
            team_group[norm(match["home"])] = match["group"]
            team_group[norm(match["away"])] = match["group"]
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        header_text = " ".join(clean(c.get_text(" ", strip=True)).lower()
                                for row in rows[:2] for c in row.find_all(["th", "td"]))
        # Only parse a table that looks like a league standings table.
        if not any(word in header_text for word in ("mecze", "mecz", "zwyci", "poraż", "poraz", "punkty", "pkt", "stosunek")):
            continue
        for row in rows:
            cells = [clean(c.get_text(" ", strip=True)) for c in row.find_all(["th", "td"])]
            if len(cells) < 5:
                continue
            team_cell = next((c for c in cells if norm(c) in team_group), None)
            if not team_cell:
                continue
            group = team_group[norm(team_cell)]
            nums = [int(c) for c in cells if re.fullmatch(r"\d+", c)]
            ratios = [tuple(map(int, match.groups())) for c in cells
                      for match in [re.fullmatch(r"(\d+)\s*:\s*(\d+)", c)] if match]
            if len(nums) < 3:
                continue
            tables_by_group[group].append({
                "rank": nums[0] if nums[0] <= 20 else len(tables_by_group[group]) + 1,
                "team": team_cell,
                "played": nums[1] if len(nums) > 1 else 0,
                "wins": nums[2] if len(nums) > 2 else 0,
                "losses": nums[3] if len(nums) > 3 else 0,
                "sets_for": ratios[0][0] if ratios else 0,
                "sets_against": ratios[0][1] if ratios else 0,
                "points_for": ratios[1][0] if len(ratios) > 1 else 0,
                "points_against": ratios[1][1] if len(ratios) > 1 else 0,
                "points": nums[-1] if nums else 0,
            })
    for group in tables_by_group:
        seen = set()
        tables_by_group[group] = [r for r in tables_by_group[group]
                                  if not (norm(r["team"]) in seen or seen.add(norm(r["team"])))]
        tables_by_group[group].sort(key=lambda r: r["rank"])
    return tables_by_group

def main():
    matches, teams = parse_pzps()
    tables_by_group = parse_pzps_results(matches)
    groups = []
    for number in range(1, 6):
        group_name = f"Grupa {number}"
        group_matches = [m for m in matches if m.get("group") == group_name]
        group_teams = sorted({name for m in group_matches for name in (m["home"], m["away"])})
        table = tables_by_group.get(group_name, [])
        groups.append({
            "name": group_name,
            "teams": [{"name": n, "logo": ""} for n in group_teams],
            "matches": group_matches,
            "table": table,
            "results_source": PZPS_RESULTS_URL,
        })
        print(f"{group_name}: {len(group_matches)} fixtures, {sum(m['status']=='finished' for m in group_matches)} results, {len(table)} table rows")

    data = {
        "competition": "II Liga Mężczyzn",
        "source": PZPS_URL,
        "results_source": PZPS_RESULTS_URL,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "groups": groups,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(matches)} fixtures across {len(teams)} teams to {OUT}")


if __name__ == "__main__":
    main()
