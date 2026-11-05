#!/usr/bin/env python3
"""Import public men's SuperLega and SV.League schedules into Kiedy Siatka feeds.

These are periodic fixture/result snapshots, NOT a source of live points or odds.
Only public HTTP; 403/errors fail cleanly and preserve the last good JSON.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ITALY_URL = "https://ww2.legavolley.it/Calendario.asp"
JAPAN_URL = "https://www.svleague.jp/match/sv/men/"
ITALIAN_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5,
    "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10,
    "novembre": 11, "dicembre": 12,
}
HEADERS = {"User-Agent": "KiedySiatka/1.0 (public volleyball fixture reader)"}
TIMEOUT = (6, 25)
MAX_DAY_REQUESTS = 105
WARSAW = ZoneInfo("Europe/Warsaw")
TOKYO = ZoneInfo("Asia/Tokyo")


def clean(value):
    return " ".join(value.split())


def get_html(session, url, params=None):
    response = session.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    if len(response.content) > 1_500_000:
        raise RuntimeError("Fixture response is unexpectedly large")
    text = response.text
    if not text.strip() or any(token in text.lower() for token in (
        "sorry, you have been blocked", "just a moment...", "verify you are human"
    )):
        raise RuntimeError("No fixture content (possibly an access challenge)")
    return text


def parse_italian_heading(value):
    pattern = (r"(\d+)[ªº]\s+Giornata\s+(Andata|Ritorno).*?"
               r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})\s+Ore\s+(\d{1,2}:\d{2})")
    found = re.search(pattern, clean(value), re.I)
    if not found:
        return None
    round_num, phase, day, month, year, hour = found.groups()
    month_num = ITALIAN_MONTHS.get(month.casefold())
    if not month_num:
        return None
    date = datetime(int(year), month_num, int(day))
    return date, hour, int(round_num), phase.casefold()


def parse_italy(html):
    soup = BeautifulSoup(html, "html.parser")
    matches = []
    for table in soup.select("table#GareGiornata"):
        rows = table.select("tr")
        if not rows:
            continue
        header = parse_italian_heading(rows[0].get_text(" ", strip=True))
        if not header:
            continue
        date, default_time, round_num, phase = header
        for row in rows[1:]:
            cells = row.find_all("td", recursive=False)
            if len(cells) < 7:
                continue
            number = clean(cells[0].get_text(" ", strip=True))
            home = clean(cells[1].get_text(" ", strip=True))
            away = clean(cells[3].get_text(" ", strip=True))
            if not number.isdigit() or not home or not away:
                continue
            raw_score = clean(cells[2].get_text(" ", strip=True))
            score = re.fullmatch(r"([0-3])-([0-3])", raw_score)
            home_sets = away_sets = None
            status = "scheduled"
            if score:
                left, right = map(int, score.groups())
                if max(left, right) == 3 and 3 <= left + right <= 5:
                    home_sets, away_sets, status = left, right, "finished"
            note = clean(cells[6].get_text(" ", strip=True))
            kickoff = date
            hour = default_time
            override = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+Ore\s+(\d{1,2}:\d{2})", note, re.I)
            if override:
                day, month, year, hour = override.groups()
                kickoff = datetime(int(year), int(month), int(day))
            else:
                override_hour = re.search(r"\bOre\s+(\d{1,2}:\d{2})", note, re.I)
                if override_hour:
                    hour = override_hour.group(1)
            game_link = cells[2].get("onclick", "")
            game = re.search(r"IdGara=(\d+)", game_link, re.I)
            match_id = f"it-{game.group(1)}" if game else f"it-{kickoff.year}-{phase}-{number}"
            matches.append({
                "id": match_id,
                "competition": "SuperLega Credem Banca",
                "group": f"Kolejka {round_num}" + (" · rewanże" if phase == "ritorno" else ""),
                "date": kickoff.strftime("%d.%m.%Y"),
                "time": hour,
                "home": home,
                "away": away,
                "status": status,
                "home_sets": home_sets,
                "away_sets": away_sets,
                "set_scores": [],
                "current_points": None,
            })
    if not matches:
        raise RuntimeError("No Italian SuperLega match rows found")
    return matches


def italy_feed(session, season):
    matches = []
    for phase in (1, 2):
        html = get_html(session, ITALY_URL, {
            "Anno": season, "IdCampionato": 999, "IdFase": phase,
        })
        part = parse_italy(html)
        if len(part) < 40:
            raise RuntimeError(f"Incomplete SuperLega schedule, phase {phase}: {len(part)} games")
        matches.extend(part)
    return build_feed("italy", "SuperLega Credem Banca", ITALY_URL, matches)


def parse_japan_month_days(html):
    soup = BeautifulSoup(html, "html.parser")
    days = set()
    for node in soup.select(".div_day[id]"):
        found = re.fullmatch(r"div_day_(\d{1,2})", node["id"])
        if found:
            days.add(int(found.group(1)))
    return sorted(days)


def japan_months(html):
    soup = BeautifulSoup(html, "html.parser")
    season_option = soup.select_one("#select-year option[selected]")
    if not season_option or not (season_option.get("value") or "").isdigit():
        raise RuntimeError("Missing current SV.League season")
    season = int(season_option["value"])
    months = set()
    for option in soup.select("#select-ym option[value]"):
        found = re.fullmatch(r"(20\d\d):(\d{1,2})", option["value"])
        if found:
            year, month = map(int, found.groups())
            if year in (season, season + 1) and 1 <= month <= 12:
                months.add((year, month))
    if not months:
        raise RuntimeError("No season months in SV.League calendar")
    return season, sorted(months)


def japanese_time(date, hhmm):
    if not hhmm:
        return date.strftime("%d.%m.%Y"), ""
    if not re.fullmatch(r"\d{1,2}:\d{2}", hhmm):
        raise RuntimeError(f"Bad Japanese match time: {hhmm!r}")
    hours, minutes = map(int, hhmm.split(":"))
    if hours > 23 or minutes > 59:
        raise RuntimeError("Invalid match time")
    local = date.replace(hour=hours, minute=minutes, tzinfo=TOKYO)
    polish = local.astimezone(WARSAW)
    return polish.strftime("%d.%m.%Y"), polish.strftime("%H:%M")


def parse_japan_day(html, year, month, day):
    """The public mode=ajax endpoint returns sibling dt/dd elements."""
    soup = BeautifulSoup(html, "html.parser")
    # Ajax HTML has no <dl> wrapper; include normal page fixtures for tests.
    root = soup.select_one("#match-list") or soup
    headings = root.find_all("dt")
    details = root.find_all("dd")
    if len(headings) != len(details):
        raise RuntimeError(f"SV.League dt/dd count mismatch: {len(headings)}/{len(details)}")
    results = []
    fixture_date = datetime(year, month, day)
    for heading, detail in zip(headings, details):
        teams = detail.select("ul.reset > li")
        if len(teams) != 2:
            raise RuntimeError("Unrecognized SV.League home/away layout")
        names = [clean(team.select_one("b").get_text(" ", strip=True)) if team.select_one("b") else "" for team in teams]
        if not all(names):
            raise RuntimeError("SV.League game without both team names")
        link = detail.select_one('a[href*="/match/detail/"]')
        found = re.search(r"/match/detail/(\d+)/?", link.get("href", "")) if link else None
        if not found:
            raise RuntimeError("SV.League game has no canonical match ID")
        raw_hour = detail.select_one(".time em")
        raw_hour = clean(raw_hour.get_text(" ", strip=True)) if raw_hour else ""
        date, hour = japanese_time(fixture_date, raw_hour)
        values = [[clean(span.get_text(" ", strip=True)) for span in team.select(".game span")] for team in teams]
        complete = len(values[0]) >= 6 and len(values[1]) >= 6 and values[0][5].isdigit() and values[1][5].isdigit()
        status = "scheduled"
        home_sets = away_sets = None
        scores = []
        if complete:
            a, b = int(values[0][5]), int(values[1][5])
            if max(a, b) == 3 and 3 <= a + b <= 5:
                status, home_sets, away_sets = "finished", a, b
                for h, a_point in zip(values[0][:5], values[1][:5]):
                    if h.isdigit() and a_point.isdigit():
                        scores.append(f"{h}:{a_point}")
                if len(scores) != a + b:
                    scores = []
        round_text = clean(heading.get_text(" ", strip=True))
        round_num = re.search(r"第\s*(\d+)\s*節", round_text)
        game_num = re.search(r"GAME\s*(\d+)", round_text, re.I)
        group = f"Kolejka {round_num.group(1)}" if round_num else ""
        if game_num:
            group += f" · mecz {game_num.group(1)}"
        logos = [urljoin(JAPAN_URL, team.select_one("img")["src"]) if team.select_one("img[src]") else "" for team in teams]
        results.append({
            "id": "jp-" + found.group(1),
            "competition": "SV.League Men",
            "group": group,
            "date": date,
            "time": hour,
            "home": names[0],
            "away": names[1],
            "home_sets": home_sets,
            "away_sets": away_sets,
            "set_scores": scores,
            "status": status,
            "current_points": None,
            "team_logos": logos,
        })
    return results


def japan_feed(session, max_days=MAX_DAY_REQUESTS, pause=0.4):
    index_html = get_html(session, JAPAN_URL)
    season, months = japan_months(index_html)
    matches = []
    requests_made = 0
    for year, month in months:
        page = get_html(session, JAPAN_URL, {"s": season, "y": year, "m": month})
        days = parse_japan_month_days(page)
        for day in days:
            requests_made += 1
            if requests_made > max_days:
                raise RuntimeError("SV.League day request cap reached; refusing partial feed")
            html = get_html(session, JAPAN_URL, {
                "s": season, "y": year, "m": month, "d": day, "mode": "ajax",
            })
            matches.extend(parse_japan_day(html, year, month, day))
            if pause:
                time.sleep(pause)
    if len(matches) < 60:
        raise RuntimeError(f"Suspiciously incomplete SV.League calendar: {len(matches)} games")
    return build_feed("japan", "SV.League Men", JAPAN_URL, matches)


def build_feed(league, competition, url, matches):
    unique = {}
    logo_by_name = {}
    for match in matches:
        logos = match.pop("team_logos", ["", ""])
        for name, logo in zip((match["home"], match["away"]), logos):
            if logo and name not in logo_by_name:
                logo_by_name[name] = logo
        previous = unique.get(match["id"])
        if previous and previous != match:
            raise RuntimeError("Duplicate match ID with inconsistent data")
        unique[match["id"]] = match
    matches = list(unique.values())
    matches.sort(key=lambda m: (datetime.strptime(m["date"], "%d.%m.%Y"), m["time"], m["id"]))
    if not matches:
        raise RuntimeError("Empty calendar")
    teams = [{"name":name, "logo":logo_by_name.get(name, "")}
             for name in sorted({name for m in matches for name in (m["home"], m["away"])})]
    return {
        "league": league,
        "competition": competition,
        "source": url,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "teams": teams,
        "table": [],
        "matches": matches,
    }


def write_feed(path, feed):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    # League pages sometimes omit a past kickoff time once results are posted.
    previous_by_id = {m["id"]: m for m in previous.get("matches", [])} if isinstance(previous, dict) else {}
    for match in feed["matches"]:
        old = previous_by_id.get(match["id"], {})
        if not match["time"] and old.get("time"):
            match["time"] = old["time"]
            match["date"] = old["date"]
    if isinstance(previous, dict):
        old_body = {k: v for k, v in previous.items() if k != "updated_at"}
        new_body = {k: v for k, v in feed.items() if k != "updated_at"}
        if old_body == new_body:
            print(f"{path}: no changes")
            return False
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(feed, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    print(f"{path}: wrote {len(feed['matches'])} matches / {len(feed['teams'])} teams")
    return True


def current_season():
    now = datetime.now(timezone.utc).astimezone(WARSAW)
    return now.year if now.month >= 7 else now.year - 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Official SuperLega or SV.League men's schedule")
    parser.add_argument("--league", choices=("italy", "japan"), required=True)
    parser.add_argument("--season", type=int, default=current_season())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-days", type=int, default=MAX_DAY_REQUESTS)
    parser.add_argument("--pause", type=float, default=0.4)
    args = parser.parse_args(argv)
    if not (2020 <= args.season <= 2100) or not (1 <= args.max_days <= 200) or not (0.2 <= args.pause <= 5):
        parser.error("Invalid season, max-days or pause")
    output = args.output or Path("data") / (args.league + ".json")
    try:
        with requests.Session() as session:
            session.headers.update(HEADERS)
            if args.league == "italy":
                feed = italy_feed(session, args.season)
            else:
                feed = japan_feed(session, args.max_days, args.pause)
        write_feed(output, feed)
    except (requests.RequestException, RuntimeError, ValueError, OSError) as error:
        print(f"Official league import failed: {error}", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
