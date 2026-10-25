#!/usr/bin/env python3
"""Fetch II Liga fixtures from PZPS and results/standings from VolleyTime."""
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PZPS_URL = "https://sedziowie.pzps.pl/system/mecze-II-liga-mezczyzn/"
VOLLEYTIME_URL = "https://volleytime.pl/rozgrywki/2-liga/grupa-{group}/"
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


def parse_volleytime_group(group_number):
    url = VOLLEYTIME_URL.format(group=group_number)
    response = requests.get(url, timeout=30, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    standings = []
    heading = next((h for h in soup.find_all(["h2", "h3"]) if re.search(rf"Tabela\s+grupy\s+{group_number}\b", clean(h.get_text(" ", strip=True)), re.I)), None)
    table = heading.find_next("table") if heading else soup.find("table")
    if table:
        for row in table.find_all("tr"):
            cells = [clean(c.get_text(" ", strip=True)) for c in row.find_all(["th", "td"])]
            if len(cells) < 7:
                continue
            # Common layout: rank, team, played, wins, losses, sets, small points, points.
            rank_match = re.search(r"\d+", cells[0])
            if any(c.strip().lower() in {"team", "drużyna", "drużyny", "pkt", "punkty", "#", "miejsce"} for c in cells[:2]):
                continue
            if rank_match and len(cells) >= 8:
                rank = int(rank_match.group())
                offset = 1
            elif len(cells) >= 7 and re.search(r"\d+\s*:\s*\d+", cells[4]):
                # Some tables omit the explicit rank cell in the first row.
                rank = len(standings) + 1
                offset = 0
            else:
                continue
            try:
                sets = re.search(r"(\d+)\s*:\s*(\d+)", cells[4 + offset])
                small = re.search(r"(\d+)\s*:\s*(\d+)", cells[5 + offset])
                points_cell = cells[6 + offset]
                standings.append({
                    "rank": rank,
                    "team": cells[0 + offset],
                    "played": int(re.sub(r"\D", "", cells[1 + offset]) or 0),
                    "wins": int(re.sub(r"\D", "", cells[2 + offset]) or 0),
                    "losses": int(re.sub(r"\D", "", cells[3 + offset]) or 0),
                    "sets_for": int(sets.group(1)) if sets else 0,
                    "sets_against": int(sets.group(2)) if sets else 0,
                    "points_for": int(small.group(1)) if small else 0,
                    "points_against": int(small.group(2)) if small else 0,
                    "points": int(re.sub(r"\D", "", points_cell) or 0),
                })
            except (ValueError, IndexError):
                continue

    results = []
    for h3 in soup.find_all(["h3", "h4"]):
        title = clean(h3.get_text(" ", strip=True))
        if " vs " not in title.lower():
            continue
        home, away = re.split(r"\s+vs\s+", title, maxsplit=1, flags=re.I)
        # Walk up to a compact match card; avoid taking text from the whole page.
        card = h3
        card_text = title
        for _ in range(4):
            if card.parent is None:
                break
            card = card.parent
            card_text = clean(card.get_text(" ", strip=True))
            if re.search(r"\b\d{1,2}\.\d{2}\b", card_text) and re.search(r"\b\d\s*:\s*\d\b", card_text):
                break
        date_match = re.search(r"\b(\d{1,2})\.(\d{2})(?:\s+[A-Za-ząćęłńóśźż]+)?(?:\s+(\d{1,2}:\d{2}))?", card_text, re.I)
        score_match = re.search(r"\b([0-3])\s*:\s*([0-3])\s+((?:\d{1,2}:\d{1,2})(?:\s*,\s*\d{1,2}:\d{1,2}){2,4})", card_text)
        if not date_match or not score_match:
            continue
        day, month, clock = date_match.groups()
        year = 2026 if int(month) >= 8 else 2027
        scores = re.findall(r"\d{1,2}:\d{1,2}", score_match.group(3))
        results.append({
            "home": home, "away": away, "date": f"{int(day):02d}.{month}.{year}",
            "time": clock or "", "home_sets": int(score_match.group(1)),
            "away_sets": int(score_match.group(2)), "set_scores": scores,
        })
    return standings, results


def main():
    matches, teams = parse_pzps()
    groups = []
    for number in range(1, 6):
        group_name = f"Grupa {number}"
        try:
            table, results = parse_volleytime_group(number)
            for result in results:
                pair = {norm(result["home"]), norm(result["away"])}
                candidates = [m for m in matches if m.get("group") == group_name and {norm(m["home"]), norm(m["away"])} == pair]
                if not candidates:
                    # Some providers use shortened sponsor names; match by unique normalized team prefixes.
                    candidates = [m for m in matches if m.get("group") == group_name and
                                  ((norm(m["home"]) in pair or any(n.startswith(norm(m["home"])[:12]) for n in pair)) and
                                   (norm(m["away"]) in pair or any(n.startswith(norm(m["away"])[:12]) for n in pair)))]
                if candidates:
                    match = candidates[0]
                    match.update({k: result[k] for k in ("home_sets", "away_sets", "set_scores")})
                    match["status"] = "finished"
            group_matches = [m for m in matches if m.get("group") == group_name]
            group_teams = sorted({name for m in group_matches for name in (m["home"], m["away"])})
            groups.append({"name": group_name, "teams": [{"name": n, "logo": ""} for n in group_teams],
                           "matches": group_matches, "table": table, "results_source": url if False else VOLLEYTIME_URL.format(group=number)})
            print(f"{group_name}: {len(group_matches)} fixtures, {sum(m['status']=='finished' for m in group_matches)} results, {len(table)} table rows")
        except Exception as exc:
            group_matches = [m for m in matches if m.get("group") == group_name]
            group_teams = sorted({name for m in group_matches for name in (m["home"], m["away"])})
            groups.append({"name": group_name, "teams": [{"name": n, "logo": ""} for n in group_teams],
                           "matches": group_matches, "table": [], "results_source": VOLLEYTIME_URL.format(group=number), "error": str(exc)})
            print(f"Warning: {group_name} results/table unavailable: {exc}")

    data = {
        "competition": "II Liga Mężczyzn",
        "source": PZPS_URL,
        "results_source": "https://volleytime.pl/rozgrywki/2-liga/",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "groups": groups,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(matches)} fixtures across {len(teams)} teams to {OUT}")


if __name__ == "__main__":
    main()
