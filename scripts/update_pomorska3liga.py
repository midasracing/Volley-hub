#!/usr/bin/env python3
"""Fetch Pomorska III Liga Męska from the official VolleyStation schedule and results pages."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

BASE = "https://pomorskie.volleystation.com/pl/phase-6796-pomorska-iii-liga-meska"
SCHEDULE_URL = BASE + "/schedule/"
RESULTS_URL = BASE + "/results/"
STANDINGS_URL = BASE + "/standings/"
OUT = Path("data/pomorska3liga.json")
MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
    "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8,
    "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
}
def fetch(url):
    """Load public VolleyStation pages in Chromium, allowing normal JS challenges."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(locale="pl-PL")
            response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            page.wait_for_timeout(5000)
            title = page.title()
            body = page.locator("body").inner_text(timeout=10000)
            if response and response.status == 403:
                raise RuntimeError(f"VolleyStation HTTP 403 for {url}; title={title!r}; body={body[:250]!r}")
            if "Just a moment..." in title or "Verify you are human" in body:
                raise RuntimeError(f"Cloudflare challenge did not clear for {url}; runner may not be allowed.")
            return BeautifulSoup(page.content(), "html.parser")
        finally:
            browser.close()

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
        prefix = re.match(r"^(?:TV\s+)?Runda:\s*(\d+)\s+Nr\s+(\d+)\s+(.+)$", text, re.I)
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
            status, time = "finished", None
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
        })
    return matches

def parse_table(soup):
    rows = []
    for row in soup.select("table tr"):
        cells = [re.sub(r"\s+", " ", cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"], recursive=False)]
        if len(cells) < 9 or not cells[0].isdigit():
            continue
        try:
            played, points, wins = int(cells[2]), int(cells[3]), int(cells[4])
            rows.append({
                "rank": int(cells[0]), "team": cells[1], "played": played,
                "points": points, "wins": wins, "losses": max(0, played - wins),
                "sets_for": int(cells[5]), "sets_against": int(cells[6]),
                "points_for": int(cells[7]), "points_against": int(cells[8]),
            })
        except (ValueError, IndexError):
            continue
    return rows

def load_previous(path):
    """Keep the last good data available if the official site temporarily fails."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main():
    previous = load_previous(OUT)
    # IMPORTANT: VolleyStation separates upcoming fixtures (/schedule/) from
    # played results (/results/). Both pages must be read to build a full calendar.
    schedule = parse_matches(fetch(SCHEDULE_URL), SCHEDULE_URL)
    results = parse_matches(fetch(RESULTS_URL), RESULTS_URL)
    by_id = {match["id"]: match for match in results}
    by_id.update({match["id"]: match for match in schedule})
    matches = list(by_id.values())
    if not matches:
        raise RuntimeError("No recognizable matches found on official VolleyStation schedule or results pages; refusing to overwrite existing data.")

    try:
        standings = parse_table(fetch(STANDINGS_URL))
        if len(standings) < 8:
            raise RuntimeError(f"only {len(standings)} standings rows parsed")
    except Exception as exc:
        print(f"Warning: standings unavailable, keeping previous table: {exc}", file=sys.stderr)
        standings = previous.get("table", [])

    matches.sort(key=lambda m: (
        datetime.strptime(m["date"], "%d.%m.%Y"),
        m["time"] or "99:99",
        m["round"],
        m["match_number"],
    ))
    teams = sorted({name for match in matches for name in (match["home"], match["away"])}, key=str.casefold)
    data = {
        "league": "pomorska3liga",
        "competition": "Pomorska III Liga Męska",
        "source": SCHEDULE_URL,
        "results_source": RESULTS_URL,
        "standings_source": STANDINGS_URL,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "teams": [{"name": name, "logo": ""} for name in teams],
        "matches": matches,
        "table": standings,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(matches)} matches ({len(results)} from results, {len(schedule)} from schedule), {len(teams)} teams; standings rows: {len(standings)}")

if __name__ == "__main__":
    main()
