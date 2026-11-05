#!/usr/bin/env python3
"""Independent, read-only audit of the 2026/27 PLS feeds against official HTML.

Run after refresh_tauron.py: python scripts/audit_pls.py
Exit nonzero on any mismatch; never writes to data/*.json.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
import argparse
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin
import json
import re
import sys

from bs4 import BeautifulSoup

SEASON_START = "2026-07-01"
SEASON_END = "2027-06-30"
LEAGUES = (
    ("men", "https://www.tauronliga.pl", "data/tauron.json", 14, 26),
    ("first", "https://www.tauron1liga.pl", "data/tauron1liga.json", 16, 30),
)
HEADERS = {"User-Agent": "KiedySiatka-Audit/1.0", "Accept-Language": "pl-PL,pl;q=0.9"}
errors = []


def check(condition, message):
    if not condition:
        errors.append(message)


def fetch(url):
    with urlopen(Request(url, headers=HEADERS), timeout=30) as response:
        return BeautifulSoup(response.read(), "html.parser")


def clean(node):
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def independent_page_metadata(soup):
    """Extract official detail labels for comparison independently of importer."""
    meta = {}
    sections = ("szczegóły", "informacje o hali", "transmisje")
    for heading in soup.find_all(re.compile(r"^h[1-6]$", re.I)):
        label = clean(heading).casefold()
        if label not in sections:
            continue
        entries = {}
        channels = []
        for node in heading.next_elements:
            node_name = getattr(node, "name", None)
            if node_name and re.fullmatch(r"h[1-6]", node_name, re.I):
                break
            if node_name == "tr":
                cells = node.find_all(["th", "td"], recursive=False)
                if len(cells) >= 2:
                    entries[clean(cells[0]).casefold().rstrip(":")] = clean(cells[1])
            elif node_name == "img" and label == "transmisje":
                channel = (node.get("alt") or node.get("title") or "").strip()
                if channel and ("polsat" in channel.casefold() or "tv" in channel.casefold()):
                    if channel not in channels:
                        channels.append(channel)
        if label == "informacje o hali" and entries.get("nazwa"):
            meta["venue"] = {
                "name": entries["nazwa"],
                "address": entries.get("adres", ""),
                "city": entries.get("miasto", ""),
            }
        if label == "szczegóły":
            if entries.get("termin", "").isdigit():
                meta["term_number"] = int(entries["termin"])
            if entries.get("numer meczu"):
                meta["match_number"] = entries["numer meczu"]
            if entries.get("faza"):
                meta["phase"] = entries["faza"]
        if label == "transmisje" and channels:
            meta["broadcast"] = channels
    return meta


def read_details(url, match):
    soup = fetch(url)
    title = clean(soup.title).casefold()
    if not all(n.casefold() in title for n in (match["home"], match["away"])):
        raise RuntimeError(f"Wrong match detail page for {match['id']}: {title[:100]}")
    expected_wins = (int(match["home_sets"]), int(match["away_sets"]))
    total = sum(expected_wins)
    official_points = None
    if match["status"] == "finished":
        for box in soup.select(".game-result-box"):
            score = [clean(e) for e in box.select(".game-result .game-score")[:2]]
            if score != [str(x) for x in expected_wins]:
                continue
            text = clean(box)
            points = re.search(r"Małe punkty\s*:\s*(.*?)(?:Złoty set\s*:|$)", text, re.I)
            if not points:
                continue
            values = [int(x) for x in re.findall(r"(?<!\d)\d{1,3}(?!\d)", points.group(1))]
            if len(values) < 10:
                continue
            official_points = [f"{values[i]}:{values[i+1]}" for i in range(0, 2 * total, 2)]
            break
    return match["id"], official_points, independent_page_metadata(soup)


def audit(key, base, filename, team_count, round_count, check_details=False):
    data = json.loads(Path(filename).read_text(encoding="utf8"))
    matches = data["matches"]
    expected = team_count * (team_count - 1)
    check(len(matches) == expected, f"{key}: expected exactly {expected} games, got {len(matches)}")
    ids = [str(m["id"]) for m in matches]
    check(len(ids) == len(set(ids)), f"{key}: duplicate match IDs")
    by_id = {str(m["id"]): m for m in matches}
    rounds, appearances, home_count, away_count, pairs = Counter(), Counter(), Counter(), Counter(), Counter()
    id_names = defaultdict(set)
    id_logos = defaultdict(set)
    finished = []
    for match in matches:
        game_id = str(match["id"])
        check(match.get("league") == key, f"{key}:{game_id}: incorrect league code")
        check(match.get("competition") == ("TAURON Liga" if key == "men" else "TAURON 1. Liga"),
              f"{key}:{game_id}: incorrect competition")
        iso = match.get("date_iso") or ""
        check(SEASON_START <= iso <= SEASON_END, f"{key}:{game_id}: date outside 2026/27: {iso!r}")
        if iso:
            try:
                check(datetime.strptime(match["date"], "%d.%m.%Y").date().isoformat() == iso,
                      f"{key}:{game_id}: invalid date pairing")
            except ValueError:
                check(False, f"{key}:{game_id}: unparsable date")
        if match.get("time"):
            check(bool(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", match["time"])),
                  f"{key}:{game_id}: invalid time")
        home, away = match.get("home"), match.get("away")
        check(bool(home and away and home != away), f"{key}:{game_id}: invalid teams")
        for side, team in (("home", home), ("away", away)):
            tid = match.get(side + "_team_id")
            check(bool(tid), f"{key}:{game_id}: missing {side} team ID")
            if tid:
                id_names[tid].add(team)
                if match.get(side + "_logo"):
                    id_logos[tid].add(match[side + "_logo"])
            appearances[team] += 1
        home_count[home] += 1
        away_count[away] += 1
        pairs[tuple(sorted((home, away)))] += 1
        rounds[match.get("round")] += 1
        check(match.get("source_url") == f"{base}/games/action/show/id/{game_id}/nocookies/1.html",
              f"{key}:{game_id}: wrong source URL")
        if match["status"] == "finished":
            finished.append(match)
            scores = match.get("set_scores", [])
            check(len(scores) == match["home_sets"] + match["away_sets"],
                  f"{key}:{game_id}: incomplete points")
            try:
                points = [tuple(map(int, p.split(":"))) for p in scores]
                check(sum(a > b for a,b in points) == match["home_sets"] and
                      sum(a < b for a,b in points) == match["away_sets"],
                      f"{key}:{game_id}: set winner mismatch")
                check(sum(a for a,b in points) == match["home_points"] and
                      sum(b for a,b in points) == match["away_points"],
                      f"{key}:{game_id}: point sum mismatch")
            except Exception:
                check(False, f"{key}:{game_id}: malformed points")

    check(len(set(id_names)) == team_count, f"{key}: expected {team_count} unique club IDs, got {len(id_names)}")
    for team_id,names in id_names.items():
        check(len(names) == 1, f"{key}: club ID {team_id} has multiple names {sorted(names)}")
    check(len(appearances) == team_count, f"{key}: expected {team_count} teams, got {len(appearances)}")
    for name in appearances:
        check(appearances[name] == 2 * (team_count - 1),
              f"{key}: {name!r} plays {appearances[name]} not {2*(team_count-1)} times")
        check(home_count[name] == team_count - 1 and away_count[name] == team_count - 1,
              f"{key}: {name!r} has {home_count[name]} home / {away_count[name]} away")
    for pair, count in pairs.items():
        check(count == 2, f"{key}: team pair {pair} occurs {count} rather than 2 times")
    for round_number in range(1, round_count + 1):
        check(rounds[round_number] == team_count // 2,
              f"{key}: round {round_number} has {rounds[round_number]} games, expected {team_count//2}")

    teams = data.get("teams", [])
    check(len(teams) == team_count, f"{key}: JSON team array has {len(teams)} clubs")
    for team in teams:
        check(bool(team.get("logo")), f"{key}: missing logo for {team.get('name')}")
        check(bool(team.get("id")), f"{key}: missing team ID for {team.get('name')}")
        club_id = str(team.get("id"))
        check(team.get("name") in id_names.get(club_id, set()),
              f"{key}: wrong team name for club ID {club_id}")
        check(team.get("logo") in id_logos.get(club_id, set()),
              f"{key}: logo URL does not match official fixture for club {club_id}")

    soup = fetch(base + "/games/nocookies/1.html")
    cards = soup.select("section[data-game-id]")
    card_ids = [str(c.get("data-game-id")) for c in cards if c.find_parent("section", attrs={"data-round": True})]
    check(set(card_ids) == set(by_id),
          f"{key}: source ID mismatch; missing={sorted(set(card_ids)-set(by_id))[:5]}, extras={sorted(set(by_id)-set(card_ids))[:5]}")
    for card in cards:
        mid = str(card.get("data-game-id"))
        if mid not in by_id:
            continue
        match = by_id[mid]
        # Independently derive round from the official visible heading,
        # not from a potentially over-nested HTML section wrapper.
        h = card.find_previous(
            lambda tag: getattr(tag, "name", None) in ("h2", "h3", "h4", "h5", "h6")
            and re.match(r"^Kolejka\s*:\s*\d+", clean(tag), re.I)
        )
        num = re.search(r"\d+", clean(h)).group() if h else None
        check(h is not None and str(match.get("round")) == num,
              f"{key}:{mid}: wrong round: JSON={match.get('round')}, official={num}")
        for side, cl in (("home", "left"), ("away", "right")):
            name = clean(card.select_one(".game-team." + cl))
            check(name == match[side], f"{key}:{mid}: {side} name mismatch: {name} vs {match[side]}")
            picture = card.select_one(".game-logo." + cl + " img")
            if picture:
                src = picture.get("src") or picture.get("data-src")
                if src:
                    check(match.get(side + "_logo") == urljoin(base, src),
                          f"{key}:{mid}: incorrect official {side} logo")
        game_date = clean(card.select_one(".game-date span"))
        if game_date:
            expected_date = match["date"] + (", " + match["time"] if match.get("time") else "")
            check(game_date == expected_date, f"{key}:{mid}: date/time mismatch {game_date!r} != {expected_date!r}")
        numbers = [clean(x) for x in card.select(".game-result .game-score")[:2]]
        if len(numbers) == 2 and all(re.fullmatch(r"[0-3]", n) for n in numbers):
            check(tuple(map(int,numbers)) == (match["home_sets"], match["away_sets"]),
                  f"{key}:{mid}: score mismatch")
        channel = card.select_one(".game-tv img")
        if channel:
            label = channel.get("title") or channel.get("alt") or ""
            check(label in match.get("broadcast", []),
                  f"{key}:{mid}: channel absent or different: {label!r}")

    # Each completed game is independently cross-checked with PLS. For a
    # full details audit, also check two matches per round including future
    # games to catch missing hall/TV metadata across the entire season.
    sample = {str(m["id"]): m for m in finished}
    if check_details:
        for m in matches:
            raw = m.get("details_checked_at", "")
            try:
                verified = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                check(verified.tzinfo is not None,
                      f"{key}:{m['id']}: details timestamp without timezone")
            except (ValueError, AttributeError, TypeError):
                check(False, f"{key}:{m['id']}: official detail page was never checked")
        for r in range(1, round_count + 1):
            in_round = [m for m in matches if m.get("round") == r]
            for m in (in_round[:1] + in_round[-1:]):
                sample[str(m["id"])] = m

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(read_details, f"{base}/games/action/show/id/{m['id']}/nocookies/1.html", m): m
            for m in sample.values()
        }
        for future in as_completed(futures):
            m = futures[future]
            try:
                mid, official, metadata = future.result()
                record = by_id[mid]
                if m["status"] == "finished":
                    check(official is not None, f"{key}:{mid}: could not read official detail points")
                    if official is not None:
                        check(official == record["set_scores"],
                              f"{key}:{mid}: official set points differ {official} != {record['set_scores']}")
                if check_details:
                    for field in ("term_number", "match_number", "phase"):
                        if field in metadata:
                            check(record.get(field) == metadata[field],
                                  f"{key}:{mid}: {field} mismatch {record.get(field)!r} vs {metadata[field]!r}")
                    if "venue" in metadata:
                        venue = record.get("venue") or {}
                        for field, value in metadata["venue"].items():
                            if value:
                                check(venue.get(field) == value,
                                      f"{key}:{mid}: wrong venue {field}: {venue.get(field)!r} vs {value!r}")
                    if "broadcast" in metadata:
                        check(all(channel in record.get("broadcast", [])
                                  for channel in metadata["broadcast"]),
                              f"{key}:{mid}: incorrect official TV channels")
            except Exception as exc:
                check(False, f"{key}:{m['id']}: detail request error {exc}")

    print(json.dumps({
        "league": key, "fixtures": len(matches), "unique_ids": len(set(ids)),
        "rounds": len(rounds), "clubs": len(id_names), "finished_checked_individually": len(finished),
        "logos": sum(bool(x.get("logo")) for x in teams),
        "venue_coverage": sum(bool(x.get("venue")) for x in matches),
        "broadcast_coverage": sum(bool(x.get("broadcast")) for x in matches),
        "details_checked": sum(bool(x.get("details_checked_at")) for x in matches),
        "details_independently_sampled": len(sample),
        "term_number_coverage": sum(m.get("term_number") is not None for m in matches),
        "match_number_coverage": sum(bool(m.get("match_number")) for m in matches),
        "errors_so_far": len(errors),
    }, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-details", action="store_true")
    args = parser.parse_args()
    for league in LEAGUES:
        try:
            audit(*league, check_details=args.check_details)
        except Exception as exc:
            check(False, f"{args[0]}: audit crashed: {type(exc).__name__}: {exc}")
    for issue in errors:
        print("ERROR:", issue, file=sys.stderr, flush=True)
    if errors:
        raise SystemExit(f"Deep audit FAILED: {len(errors)} discrepancies")
    print("Deep audit PASSED: 422 fixtures, all finished set scores, and requested detail checks verified.", flush=True)


if __name__ == "__main__":
    main()
