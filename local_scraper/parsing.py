"""Parse public VolleyStation pages without owning a network transport."""

import re
import sys
from urllib.parse import urljoin

BASE = "https://pomorskie.volleystation.com/pl/phase-6796-pomorska-iii-liga-meska"
SCHEDULE_URL = BASE + "/schedule/"
RESULTS_URL = BASE + "/results/"
STANDINGS_URL = BASE + "/standings/"
MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
    "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8,
    "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
}

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
    # VolleyStation groups match links below date headings (e.g. "25 października 2026, Niedziela").
    for previous in anchor.find_all_previous(re.compile(r"^h[1-6]$")):
        result = parse_date(previous.get_text(" ", strip=True))
        if result:
            return result
    # Fallback for a layout version that wraps each day in a section.
    parent = anchor.parent
    for _ in range(4):
        if not parent:
            break
        result = parse_date(parent.get_text(" ", strip=True)[:160])
        if result:
            return result
        parent = parent.parent
    return None

def parse_matches(soup, source_url):
    matches = []
    for anchor in soup.find_all("a", href=True):
        text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
        prefix = re.match(r"^(?:(?:TV|Na żywo)\s+)?Runda:\s*(\d+)\s+Nr\s+(\d+)\s+(.+)$", text, re.I)
        if not prefix:
            continue
        round_no, match_no, rest = prefix.groups()
        date = heading_date(anchor)
        if not date:
            continue

        # Official VolleyStation labels completed matches with set score (3:0)
        # and scheduled matches with kickoff time (18:00).
        score_match = re.search(r"\s([0-3]):([0-3])\s+", rest)
        if score_match:
            home = rest[:score_match.start()].strip(" ·-")
            away = rest[score_match.end():].strip(" ·-")
            home_sets, away_sets = int(score_match.group(1)), int(score_match.group(2))
            status = 'finished' if max(home_sets,away_sets)==3 else 'live' if home_sets+away_sets or text.casefold().startswith('na żywo ') else 'scheduled'
            time = None
        else:
            time_match = re.search(r"\b(\d{2}:\d{2})\b", rest)
            if not time_match:
                continue
            home = rest[:time_match.start()].strip(" ·-")
            away = rest[time_match.end():].strip(" ·-")
            home_sets, away_sets = None, None
            status, time = "scheduled", time_match.group(1)

        if not home or not away:
            continue
        # Keep source page and round/match number as a stable identity even if
        # VolleyStation's link path changes between page versions.
        matches.append({
            "id": f"{date}-{round_no}-{match_no}",
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
            "source_url": source_url,
            "match_url": urljoin(source_url, anchor.get("href", "")),
        })
    return matches


def parse_match_detail(soup):
    """Read kickoff time and individual set scores from an official match page."""
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    kickoff = None
    patterns = [
        r"(?:godzina rozpoczęcia|godzina meczu|początek meczu|rozpoczęcie|start meczu|match start|kick.?off|data i godzina|termin meczu)[^0-9]{0,80}(\d{1,2}:\d{2})",
        r"(?:data|termin)[^0-9]{0,50}\d{1,2}[. /-]\d{1,2}[. /-]\d{4}[^0-9]{0,80}(\d{1,2}:\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            hour, minute = match.group(1).split(":")
            kickoff = f"{int(hour):02d}:{minute}"
            break
    if not kickoff:
        # Match detail pages may display the kickoff as a standalone time rather
        # than next to a Polish label; use the first valid clock token in the page.
        time_match = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", text)
        if time_match:
            kickoff = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"

    if not kickoff:
        # Some versions keep the kickoff in structured metadata rather than visible text.
        for node in soup.select("[datetime], time, [data-start-time], [data-kickoff]"):
            candidate = " ".join(str(node.get(attr, "")) for attr in ("datetime", "data-start-time", "data-kickoff"))
            candidate += " " + node.get_text(" ", strip=True)
            time_match = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", candidate)
            if time_match:
                kickoff = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
                break

    # Match pages render each team's points in paired .team-points-row
    # containers. Each .set-points element is one set's points, not a "25:18"
    # string, so pair the home and away rows by set index.
    set_scores = []
    raw_pairs = []
    team_rows = soup.select(".team-points-row")
    home_row = next((row for row in team_rows if "home" in row.get("class", [])), None)
    away_row = next((row for row in team_rows if "away" in row.get("class", [])), None)

    if home_row and away_row:
        home_points = [
            node.get_text(" ", strip=True)
            for node in home_row.select(".set-points")
        ]
        away_points = [
            node.get_text(" ", strip=True)
            for node in away_row.select(".set-points")
        ]
        for home_value, away_value in zip(home_points, away_points):
            if home_value.isdigit() and away_value.isdigit():
                a, b = int(home_value), int(away_value)
                raw_pairs.append((a,b))
                if a != b:
                    set_scores.append(f"{a}:{b}")


    result={"time": kickoff, "set_scores": set_scores}
    if home_row and away_row:
        for side,row in [('home',home_row),('away',away_row)]:
            value=row.select_one('.match-points')
            if value and value.get_text(strip=True).isdigit():result[side+'_sets']=int(value.get_text(strip=True))
        if 'home_sets' in result and 'away_sets' in result and max(result['home_sets'],result['away_sets'])<3:
            count=result['home_sets']+result['away_sets']
            result['set_scores']=[f'{a}:{b}' for a,b in raw_pairs[:count]]
            result['current_points']=f'{raw_pairs[count][0]}:{raw_pairs[count][1]}' if len(raw_pairs)>count else None
    return result

def parse_table(soup, expected_teams=9):
    rows = []
    for row in soup.select("table tr"):
        cells = [
            re.sub(r"\s+", " ", cell.get_text(" ", strip=True))
            for cell in row.find_all(["td", "th"], recursive=False)
        ]
        # VolleyStation standings rows contain 18 cells:
        # rank, team, points, matches, sets won/lost, points won/lost,
        # ratios, then match-result counts (3-0, 3-1, 3-2, 2-3, 1-3, 0-3).
        if len(cells) < 18 or not cells[0].isdigit():
            continue
        try:
            rank = int(cells[0])
            points = int(cells[2])
            played = int(cells[3])
            sets_for, sets_against = int(cells[6]), int(cells[7])
            points_for, points_against = int(cells[8]), int(cells[9])
            result_counts = [int(value) for value in cells[12:18]]
            wins = sum(result_counts[:3])
            losses = sum(result_counts[3:])
            rows.append({
                "rank": rank, "team": cells[1], "played": played,
                "points": points, "wins": wins, "losses": losses,
                "sets_for": sets_for, "sets_against": sets_against,
                "points_for": points_for, "points_against": points_against,
            })
        except (ValueError, IndexError) as exc:
            print(f"Skipping invalid standings row {cells[:4]!r}: {exc}", file=sys.stderr)
    if rows and expected_teams is not None and len(rows) != expected_teams:
        print(f"Warning: expected {expected_teams} standings rows, parsed {len(rows)}", file=sys.stderr)
    return rows

def parse_team_logos(soup, page_url, known_logos=None, *, fetch_page):
    """Extract team logos from standings and team profile links."""
    logos = dict(known_logos or {})

    def extract_url(node):
        for attr in ("src", "data-src", "data-lazy-src", "data-original", "data-image", "href"):
            value = (node.get(attr) or "").strip()
            if value and not value.startswith("data:") and not value.startswith("javascript:"):
                return urljoin(page_url, value)
        for attr in ("srcset", "data-srcset"):
            value = (node.get(attr) or "").strip()
            if value:
                candidate = value.split(",")[0].strip().split()[0]
                if candidate and not candidate.startswith("data:"):
                    return urljoin(page_url, candidate)
        style = node.get("style", "")
        match = re.search(r"url\(['\"]?([^)'\"]+)", style)
        return urljoin(page_url, match.group(1).strip()) if match else ""

    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        team_cell = cells[1]
        name = re.sub(r"\s+", " ", team_cell.get_text(" ", strip=True)).strip()
        if not name or name.isdigit() or name.lower() in {"drużyna", "team"}:
            continue
        candidates = team_cell.select("img, source, [style*='background'], a")
        if not candidates:
            candidates = row.select("img, source, [style*='background']")
        for node in candidates:
            src = extract_url(node)
            if src and re.search(r"\.(?:svg|png|jpe?g|webp)(?:[?#].*)?$", src, re.I):
                logos[name] = src
                break

    # VolleyStation often links each team name to its own profile; logos can be
    # exposed there even when the standings table itself contains no image node.
    for anchor in soup.select('a[href*="/teams/"]'):
        href = urljoin(page_url, anchor.get("href", ""))
        if href.rstrip("/").endswith("/teams"):
            continue
        name = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip()
        # Some layouts wrap the badge in a link and keep the team name elsewhere
        # in the same standings row; use that row's team cell as a fallback.
        if not name:
            row = anchor.find_parent("tr")
            cells = row.find_all(["td", "th"], recursive=False) if row else []
            if len(cells) >= 2:
                name = re.sub(r"\s+", " ", cells[1].get_text(" ", strip=True)).strip()
        if not name or not href or name in logos:
            continue
        try:
            team_soup = fetch_page(href)
        except Exception as exc:
            print(f"Warning: couldn't inspect team profile for logo {name!r}: {exc}", file=sys.stderr)
            continue

        # The official badge can be embedded in JSON/script markup instead of an <img>.
        # Search the raw profile HTML first for VolleyStation's canonical badge URL.
        html_text = str(team_soup).replace(r"\/", "/").replace(r"\u002F", "/")
        badge_match = re.search(
            r"(?:https?:)?//assets\.volleystation\.com/website/teams/\d+/badge\.png(?:[?#][^\s\"'<>]*)?",
            html_text,
            re.I,
        )
        if badge_match:
            logos[name] = urljoin(href, badge_match.group(0))
            print(f"Team logo mapped: {name} -> {logos[name]}", flush=True)
            continue

        image_candidates = []
        for selector in (
            'meta[property="og:image"]', 'meta[name="twitter:image"]',
            'img[alt*="logo" i]', 'img[class*="logo" i]',
            'img[src]', 'img[data-src]', 'img[data-lazy-src]',
            'img[data-original]', 'img[data-image]', 'img[srcset]',
            '[style*="background-image"]',
        ):
            image_candidates.extend(team_soup.select(selector))
        for node in image_candidates:
            if node.name == "meta":
                src = urljoin(href, (node.get("content") or "").strip())
            else:
                src = extract_url(node)
            if not src or not re.search(r"\.(?:svg|png|jpe?g|webp)(?:[?#].*)?$", src, re.I):
                continue
            if any(token in src.lower() for token in ("flag", "avatar", "default", "placeholder")):
                continue
            logos[name] = src
            print(f"Team logo mapped: {name} -> {src}", flush=True)
            break

    return logos
