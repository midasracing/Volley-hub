#!/usr/bin/env python3
"""Fetch Pomorska III Liga Męska only from its official VolleyStation phase."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://pomorskie.volleystation.com/pl/phase-6796-pomorska-iii-liga-meska"
SCHEDULE_URL = BASE + "/schedule/"
STANDINGS_URL = BASE + "/standings/"
OUT = Path("data/pomorska3liga.json")
MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
    "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8,
    "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
}

def fetch(url):
    response = requests.get(url, timeout=30, headers={"User-Agent": "VolleyHub/1.0 (public fixtures reader)"})
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")

def parse_date(text):
    match = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", text.lower())
    if not match:
        return None
    day, month_name, year = match.groups()
    month = MONTHS.get(month_name)
    if not month:
        return None
    return f"{int(day):02d}.{month:02d}.{year}"

def heading_date(anchor):
    for previous in anchor.find_all_previous(re.compile(r"^h[1-6]$")):
        result = parse_date(previous.get_text(" ", strip=True))
        if result:
            return result
    # Some VolleyStation page versions put the date into a parent section.
    parent = anchor.parent
    for _ in range(4):
        if not parent:
            break
        result = parse_date(parent.get_text(" ", strip=True)[:100])
        if result:
            return result
        parent = parent.parent
    return None

def parse_matches(soup):
    matches = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
        prefix = re.match(r"^(?:TV\s+)?Runda:\s*(\d+)\s+Nr\s+(\d+)\s+(.+)$", text, re.I)
        if not prefix:
            continue
        round_no, match_no, rest = prefix.groups()
        date = heading_date(anchor)
        if not date:
            continue

        # A played match has a set score such as 3:0; an unplayed match has
        # a kickoff time such as 18:00. Requiring two digits in the hour
        # distinguishes the time from a volleyball set score.
        score_match = re.search(r"\s([0-3]):([0-3])\s+", rest)
        if score_match:
            home = rest[:score_match.start()].strip(" ·-")
            away = rest[score_match.end():].strip(" ·-")
            home_sets, away_sets = int(score_match.group(1)), int(score_match.group(2))
            status, time = "finished", None
        else:
            time_match = re.search(r"\b(\d{2}:\d{2})\b", rest)
            if not time_match:
                continue
            home = rest[:time_match.start()].strip(" ·-")
            away = rest[time_match.end():].strip(" ·-")
            home_sets, away_sets = 0, 0
            status, time = "scheduled", time_match.group(1)

        if not home or not away:
            continue
        href_id = re.search(r"(?:match|game|event)[-/=](\d+)", anchor["href"], re.I)
        match_id = href_id.group(1) if href_id else f"{date}-{match_no}-{home}-{away}"
        key = (date, home, away)
        if key in seen:
            continue
        seen.add(key)
        matches.append({
            "id": match_id,
            "competition": "Pomorska III Liga Męska",
            "date": date,
            "time": time,
            "status": status,
            "home": home,
            "away": away,
            "home_sets": home_sets,
            "away_sets": away_sets,
            "set_scores": [],
            "current_points": None,
            "round": int(round_no),
            "match_number": int(match_no),
            "source_url": SCHEDULE_URL,
        })
    matches.sort(key=lambda m: (datetime.strptime(m["date"], "%d.%m.%Y"), m["time"] or "99:99", m["match_number"]))
    return matches

def parse_table(soup):
    table = []
    for row in soup.select("table tr"):
        cells = [re.sub(r"\s+", " ", cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"], recursive=False)]
        if len(cells) < 9 or not cells[0].isdigit():
            continue
        try:
            played, points, wins = int(cells[2]), int(cells[3]), int(cells[4])
            table.append({
                "rank": int(cells[0]), "team": cells[1], "played": played,
                "points": points, "wins": wins, "losses": max(0, played - wins),
                "sets_for": int(cells[5]), "sets_against": int(cells[6]),
                "points_for": int(cells[7]), "points_against": int(cells[8]),
            })
        except (ValueError, IndexError):
            continue
    return table

def main():
    schedule = fetch(SCHEDULE_URL)
    matches = parse_matches(schedule)
    if not matches:
        raise RuntimeError("VolleyStation returned no recognizable fixtures; refusing to overwrite the last good data.")
    try:
        standings = parse_table(fetch(STANDINGS_URL))
    except Exception as exc:
        print(f"Warning: standings unavailable, keeping schedule only: {exc}", file=sys.stderr)
        standings = []

    teams = sorted({name for m in matches for name in (m["home"], m["away"])}, key=str.casefold)
    data = {
        "league": "pomorska3liga",
        "competition": "Pomorska III Liga Męska",
        "source": SCHEDULE_URL,
        "standings_source": STANDINGS_URL,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "teams": [{"name": name, "logo": ""} for name in teams],
        "matches": matches,
        "table": standings,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(matches)} matches and {len(teams)} teams; standings rows: {len(standings)}")

if __name__ == "__main__":
    main()
