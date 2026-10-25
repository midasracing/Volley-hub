#!/usr/bin/env python3
"""Refresh men's top-tier volleyball fixtures/results and standings from the official TAURON Liga site."""
import datetime
import html
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse, urljoin
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

def extract_team_logos(*soups):
    """Collect official team logo URLs from team images on official league pages."""
    logos = {}
    for soup in soups:
        for img in soup.find_all("img"):
            label = norm(img.get("alt", "")) + " " + norm(img.get("title", ""))
            team = team_in(label)
            if not team:
                continue
            src = norm(img.get("src", "") or img.get("data-src", "") or img.get("data-lazy-src", ""))
            if not src or src.startswith("data:"):
                continue
            logos.setdefault(team, urljoin(BASE, src))
    return [{"name": name, "logo": logo} for name, logo in sorted(logos.items())]

def parse_date(text):
    """Parse only known Polish calendar formats; never mistake set scores for dates."""
    months = {
        "sty": 1, "stycznia": 1, "lut": 2, "lutego": 2,
        "mar": 3, "marca": 3, "kwi": 4, "kwietnia": 4,
        "maj": 5, "maja": 5, "cze": 6, "czerwca": 6,
        "lip": 7, "lipca": 7, "sie": 8, "sierpnia": 8,
        "wrz": 9, "września": 9, "paź": 10, "października": 10,
        "lis": 11, "listopada": 11, "gru": 12, "grudnia": 12,
    }
    # Numeric full date, e.g. 16.10.2026, 17:30.
    match = re.search(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s*,?\s*(\d{1,2}:\d{2}))?(?!\d)", text)
    if match:
        day, month, year, clock = match.groups()
        try:
            parsed = datetime.date(int(year), int(month), int(day))
            return parsed.strftime("%d.%m.%Y"), clock
        except ValueError:
            return None, None

    # Official TAURON fixture labels: "sobota, 17 paź, 18:00".
    match = re.search(
        r"(?i)(?:poniedziałek|wtorek|środa|czwartek|piątek|sobota|niedziela)?"
        r"\s*,?\s*(\d{1,2})\s+([a-ząćęłńóśźż]+)"
        r"\.?\s*,?\s*(\d{1,2}:\d{2})?",
        text
    )
    if not match:
        return None, None
    day, month_name, clock = match.groups()
    month_name = month_name.casefold().rstrip(".")
    month = months.get(month_name)
    if not month:
        return None, None
    # The current competition season is 2026/27.
    year = 2026 if month >= 7 else 2027
    try:
        parsed = datetime.date(year, month, int(day))
        return parsed.strftime("%d.%m.%Y"), clock
    except ValueError:
        return None, None

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
            # Only parse the actual fixture section. Some official cards append a
            # reversed head-to-head block labelled "Wyniki pierwszego meczu".
            # Do not let that historical block become a second fixture.
            primary_text = re.split(r"(?i)wyniki pierwszego meczu", text, maxsplit=1)[0].strip()
            if not primary_text:
                continue
            names = team_names_in_node(node)
            # Parent containers may contain both the current fixture and the
            # historical head-to-head. Resolve the two teams only from the part
            # before that heading instead of discarding the whole card.
            if len(names) != 2:
                positions = []
                for alias, canonical in ALIASES:
                    pos = primary_text.casefold().find(alias.casefold())
                    if pos >= 0:
                        positions.append((pos, canonical, len(alias)))
                positions.sort()
                unique = []
                for pos, canonical, length in positions:
                    if not any(existing[1] == canonical for existing in unique):
                        unique.append((pos, canonical, length))
                if len(unique) >= 2:
                    names = [unique[0][1], unique[1][1]]
                else:
                    continue
            # Team names occur in match order; the match score is between them.
            text = primary_text
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
                if max(home_sets, away_sets) >= 3:
                    status = "finished"
                elif home_sets > 0 or away_sets > 0 or set_scores:
                    # A partial set tally / points means the match has started.
                    # Do not leave an in-progress fixture labelled as scheduled.
                    status = "live"
                else:
                    status = "scheduled"
            else:
                home_sets = away_sets = 0
                set_scores = []
                status = "scheduled"
            date, time = parse_date(text)
            # The date label is often a sibling of the team/score container, not inside it.
            # Walk backwards through nearby document text to find the nearest official date label.
            if not date:
                for previous_text in node.find_all_previous(string=True):
                    candidate_date, candidate_time = parse_date(norm(str(previous_text)))
                    if candidate_date:
                        date, time = candidate_date, candidate_time
                        break
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
    # A fixture is identified by its actual date, kickoff and unordered team pair.
    # Historical head-to-head snippets are excluded above, before fixture parsing,
    # so they cannot introduce last-season matches or overwrite current home/away order.
    grouped = {}
    for match in found.values():
        pair = tuple(sorted((match["home"], match["away"])))
        key = (match["date"], match.get("time") or "", pair)
        # Prefer completed scorelines, then the candidate with the most set scores.
        # A real 0:3 result is valid; the zeroes in the per-set placeholders are not.
        quality = (
            1 if match["status"] == "finished" else 0,
            len(match.get("set_scores", [])),
            sum(1 for score in match.get("set_scores", []) if score != "0:0"),
        )
        previous = grouped.get(key)
        if previous is None or quality > previous[0]:
            grouped[key] = (quality, match)
    return [entry[1] for entry in grouped.values()]

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

    team_logos = extract_team_logos(games, table_soup if "table_soup" in locals() else games)
    payload = {
        "teams": team_logos,
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
