#!/usr/bin/env python3
"""Refresh men's top-tier volleyball fixtures/results and standings from the official TAURON Liga site."""
import datetime
import html
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from bs4 import BeautifulSoup

BASE = "https://www.tauronliga.pl"
GAMES_URL = BASE + "/games/nocookies/1.html"
TABLE_URL = BASE + "/table/nocookies/1.html"
HEADERS = {
    "User-Agent": "VolleyHub/1.0 (+https://github.com/midasracing/Volley-hub)",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}

# Canonical names as displayed in Volley Hub. Include known variants used by the official site.
TEAM_ALIASES = {
    "BOGDANKA LUK Lublin": ["BOGDANKA LUK Lublin", "Bogdanka LUK Lublin", "LKPS Lublin"],
    "Barkom Każany Lwów": ["Barkom Każany Lwów", "Jastrzębie Barkom", "Jastrzebie Barkom"],
    "GKS Katowice": ["GKS Katowice"],
    "PGE Projekt Warszawa": ["PGE Projekt Warszawa", "Projekt Warszawa"],
    "PGE GiEK Skra Bełchatów": ["PGE GiEK Skra Bełchatów", "PGE GiEK Skra Belchatów", "Skra Bełchatów"],
    "Indykpol AZS Olsztyn": ["Indykpol AZS Olsztyn", "Energa Indykpol AZS Olsztyn"],
    "Aluron CMC Warta Zawiercie": ["Aluron CMC Warta Zawiercie"],
    "Steam Hemarpol Norwid Częstochowa": ["Steam Hemarpol Norwid Częstochowa", "NEONET Norwid Częstochowa", "Norwid Częstochowa"],
    "Cuprum Stilon Gorzów": ["Cuprum Stilon Gorzów", "Stilon Gorzów"],
    "Ślepsk Malow Suwałki": ["Ślepsk Malow Suwałki"],
    "ChKS Chełm": ["Podziemia Kredowe ChKS Chełm", "ChKS Chełm"],
    "Asseco Resovia Rzeszów": ["Asseco Resovia Rzeszów"],
    "Trefl Gdańsk": ["Trefl Gdańsk", "Energa Trefl Gdańsk"],
    "ZAKSA Kędzierzyn-Koźle": ["ZAKSA Kędzierzyn-Koźle", "ZAKSA Kedzierzyn-Kozle"],
}
ALIASES = sorted(
    ((alias, canonical) for canonical, aliases in TEAM_ALIASES.items() for alias in aliases),
    key=lambda item: len(item[0]), reverse=True
)

def norm(value):
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()

def get(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as response:
        final_host = urlparse(response.geturl()).hostname or ""
        if not final_host.endswith("tauronliga.pl"):
            raise RuntimeError(f"Official PlusLiga URL redirected to unexpected host: {final_host}")
        return response.read()

def team_in(text):
    lower = text.casefold()
    for alias, canonical in ALIASES:
        if alias.casefold() in lower:
            return canonical
    return None

def team_names_in_node(node):
    names = []
    for img in node.find_all("img"):
        alt = norm(img.get("alt", "")) + " " + norm(img.get("title", ""))
        name = team_in(alt)
        if name and name not in names:
            names.append(name)
    # Some site cards expose team names as text rather than image alt text.
    text = norm(node.get_text(" ", strip=True))
    for alias, canonical in ALIASES:
        if alias.casefold() in text.casefold() and canonical not in names:
            names.append(canonical)
    return names

def parse_date(text):
    # Official fixtures use numeric dates like '16.10.2026, 17:30'.
    match = re.search(r'\\b(\\d{1,2}\\.\\d{1,2}\\.\\d{4})\\s*,?\\s*(\\d{1,2}:\\d{2})?', text)
    if match:
        return match.group(1), match.group(2)
    # Fallback for pages showing a Polish weekday/month without the year.
    match = re.search(
        r'(?:(?:poniedziałek|wtorek|środa|czwartek|piątek|sobota|niedziela),?\\s+)?'
        r'(\\d{1,2}\\s+[a-ząćęłńóśźż]+)(?:,?\\s+(\\d{1,2}:\\d{2}))?',
        text, re.I
    )
    return (match.group(1), match.group(2)) if match else (None, None)
def parse_matches(soup):
    found = {}
    for img in soup.find_all("img"):
        name = team_in(norm(img.get("alt", "")) + " " + norm(img.get("title", "")))
        if not name:
            continue
        node = img
        for _ in range(8):
            node = node.parent
            if not node:
                break
            text = norm(node.get_text(" ", strip=True))
            if len(text) > 1800:
                continue
            names = team_names_in_node(node)
            if len(names) != 2:
                continue
            # Team names occur in match order; the match score is between them.
            p1 = text.casefold().find(names[0].casefold())
            p2 = text.casefold().find(names[1].casefold(), p1 + len(names[0])) if p1 >= 0 else -1
            if p1 < 0 or p2 < 0:
                # Retry using alias positions in the actual text.
                positions = []
                for alias, canonical in ALIASES:
                    pos = text.casefold().find(alias.casefold())
                    if pos >= 0 and canonical in names:
                        positions.append((pos, canonical, len(alias)))
                positions.sort()
                unique = []
                for pos, canonical, length in positions:
                    if not unique or canonical != unique[-1][1]:
                        unique.append((pos, canonical, length))
                if len(unique) < 2:
                    continue
                (p1, home, l1), (p2, away, l2) = unique[:2]
            else:
                home, away = names[0], names[1]
                l1 = len(names[0])
            if p2 <= p1:
                continue
            middle = text[p1 + l1:p2].strip()
            score = re.match(r"^([0-3])\s+([0-3])(?:\s+|$)", middle)
            placeholder = bool(re.search(r"···|…|[-–—]", middle))
            if not score and not placeholder:
                continue
            if score:
                home_sets, away_sets = int(score.group(1)), int(score.group(2))
                tail = middle[score.end():]
                nums = [int(x) for x in re.findall(r"(?<!\d)\d{1,2}(?!\d)", tail)]
                set_scores = []
                for i in range(0, min(len(nums), 10) - 1, 2):
                    a, b = nums[i], nums[i + 1]
                    if a == 0 and b == 0:
                        continue
                    if a >= 0 and b >= 0:
                        set_scores.append(f"{a}:{b}")
                status = "finished" if max(home_sets, away_sets) >= 3 else "scheduled"
            else:
                home_sets = away_sets = 0
                set_scores = []
                status = "scheduled"
            date, time = parse_date(text)
            key = (date or "", time or "", home, away, home_sets, away_sets, tuple(set_scores))
            found[key] = {
                "date": date or "Termin do potwierdzenia",
                "time": time,
                "status": status,
                "home": home,
                "away": away,
                "home_sets": home_sets,
                "away_sets": away_sets,
                "set_scores": set_scores,
            }
            break
    return list(found.values())

def parse_table(soup):
    rows = []
    for tr in soup.select("tr"):
        cells = [norm(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"], recursive=False)]
        if not cells:
            continue
        team = next((canonical for alias, canonical in ALIASES if any(alias.casefold() in c.casefold() for c in cells)), None)
        if not team:
            continue
        nums = []
        for cell in cells:
            value = cell.replace(" ", "")
            if re.fullmatch(r"\d+", value):
                nums.append(int(value))
        if len(nums) < 8:
            continue
        # Official table order: rank, league points, played, wins, losses,
        # sets won/lost and points won/lost, followed by scoreline counts.
        if len(nums) < 9:
            continue
        rows.append({
            "rank": nums[0],
            "team": team,
            "points": nums[1],
            "played": nums[2],
            "wins": nums[3],
            "losses": nums[4],
            "sets_for": nums[5],
            "sets_against": nums[6],
            "points_for": nums[7],
            "points_against": nums[8],
        })
    unique = {}
    for row in rows:
        unique.setdefault(row["team"], row)
    return list(unique.values())

def main():
    games = BeautifulSoup(get(GAMES_URL), "html.parser")
    matches = parse_matches(games)
    if len(matches) < 8:
        raise RuntimeError(f"Only {len(matches)} men's TAURON Liga matches parsed; refusing to overwrite feed.")

    # Table page may redirect incorrectly on the upstream site. Never replace good data
    # with an unrelated women's table or an empty table.
    try:
        table_soup = BeautifulSoup(get(TABLE_URL), "html.parser")
        standings = parse_table(table_soup)
        if len(standings) < 8:
            raise RuntimeError(f"Only {len(standings)} standings rows parsed.")
    except Exception as exc:
        print(f"WARNING: Could not refresh PlusLiga standings; keeping existing table data: {exc}")
        # Do not retain a stale table from another competition/source.
        standings = []

    payload = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "matches": matches,
        "table": standings,
        "source": BASE,
        "competition": "TAURON Liga (mężczyźni)",
    }
    path = Path("data/tauron.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {len(matches)} men's TAURON Liga matches and {len(standings)} standings rows.")

if __name__ == "__main__":
    main()
