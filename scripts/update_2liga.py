#!/usr/bin/env python3
"""Fetch the official PZPS II Liga Mężczyzn schedule."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://sedziowie.pzps.pl/system/mecze-II-liga-mezczyzn/"
OUT = Path("data/2liga.json")


def main():
    response = requests.get(
        URL,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; VolleyHub/1.0)"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    matches = []
    teams = set()
    group = ""
    seen = set()

    # The PZPS page lists groups and their match rows in document order.
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "tr"]):
        if node.name != "tr":
            heading = " ".join(node.stripped_strings)
            match_group = re.search(r"Grupa\s+(\d+)", heading, re.I)
            if match_group:
                group = f"Grupa {match_group.group(1)}"
            continue

        cells = [" ".join(td.stripped_strings) for td in node.find_all("td")]
        if len(cells) < 5:
            continue

        date_index = next((i for i, cell in enumerate(cells)
                           if re.search(r"20\d{2}-\d{2}-\d{2}", cell)), None)
        if date_index is None or date_index + 3 >= len(cells):
            continue

        date_match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", cells[date_index])
        if not date_match:
            continue
        year, month, day = date_match.groups()
        date = f"{day}.{month}.{year}"
        time_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", cells[date_index])
        time = f"{int(time_match.group(1)):02d}:{time_match.group(2)}" if time_match else ""

        # Typical PZPS row: number, date/time, home, separator, away, officials...
        home = cells[date_index + 1].strip()
        separator_index = date_index + 2
        away_index = date_index + 3
        if cells[separator_index] not in {"-", "–", "—"}:
            # Fall back to locating the separator in the cells after the date.
            separator_index = next((i for i in range(date_index + 1, len(cells))
                                    if cells[i] in {"-", "–", "—"}), -1)
            if separator_index < 0 or separator_index + 1 >= len(cells):
                continue
            home = cells[separator_index - 1].strip()
            away_index = separator_index + 1
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
            "date": date,
            "time": time,
            "home": home,
            "away": away,
            "home_sets": None,
            "away_sets": None,
            "set_scores": [],
            "status": "scheduled",
            "competition": f"II Liga Mężczyzn · {group}" if group else "II Liga Mężczyzn",
            "group": group,
        })

    if not matches:
        raise RuntimeError("PZPS page loaded, but no match rows were parsed; keeping existing data.")

    matches.sort(key=lambda m: (datetime.strptime(m["date"], "%d.%m.%Y"), m["time"]))
    group_names = sorted({m["group"] for m in matches if m.get("group")}, key=lambda x: int(re.search(r"\d+", x).group()))
    grouped = []
    for group_name in group_names:
        group_matches = [m for m in matches if m.get("group") == group_name]
        group_teams = sorted({name for m in group_matches for name in (m["home"], m["away"])})
        grouped.append({
            "name": group_name,
            "teams": [{"name": name, "logo": ""} for name in group_teams],
            "matches": group_matches,
            "table": [],
        })

    data = {
        "competition": "II Liga Mężczyzn",
        "source": URL,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "groups": grouped,
        "matches": matches,
        "teams": [{"name": name, "logo": ""} for name in sorted(teams)],
        "table": [],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(matches)} fixtures across {len(teams)} teams to {OUT}")


if __name__ == "__main__":
    main()
