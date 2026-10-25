#!/usr/bin/env python3
"""Refresh men's volleyball fixtures/results and standings from the official league sites.

Leagues:
  men    -> TAURON Liga          (tauronliga.pl)   -> data/tauron.json
  first  -> TAURON 1. Liga       (tauron1liga.pl)  -> data/tauron1liga.json

Usage:
  python scripts/refresh_tauron.py                 # all leagues
  python scripts/refresh_tauron.py --league men    # only the top tier
  python scripts/refresh_tauron.py --league first  # only 1. Liga
"""

import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "VolleyHub/1.0 (+https://github.com/midasracing/Volley-hub)",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}

TZ = ZoneInfo("Europe/Warsaw")

# Team ids come from the official links (/teams/id/93.html). They are stable even
# when a sponsor changes a club name. Canonical names are the ones Volley Hub shows.
MEN_TEAM_IDS = {
    2: "Aluron CMC Warta Zawiercie",
    3: "Asseco Resovia Rzeszów",
    8: "Barkom Każany Lwów",
    18: "GKS Katowice",
    21: "ZAKSA Kędzierzyn-Koźle",
    24: "Indykpol AZS Olsztyn",
    28: "Cuprum Stilon Gorzów",
    45: "BOGDANKA LUK Lublin",
    56: "Ślepsk Malow Suwałki",
    61: "PGE GiEK Skra Bełchatów",
    62: "PGE Projekt Warszawa",
    71: "Steam Hemarpol Norwid Częstochowa",
    78: "Trefl Gdańsk",
    93: "ChKS Chełm",
}

# Extra spellings, used as a fallback when a name is not found through a team link.
MEN_ALIASES = {
    "BOGDANKA LUK Lublin": ["BOGDANKA LUK Lublin", "Bogdanka LUK Lublin", "LKPS Lublin"],
    "Barkom Każany Lwów": ["Barkom Każany Lwów", "Jastrzębie Barkom", "Jastrzebie Barkom"],
    "GKS Katowice": ["GKS Katowice"],
    "PGE Projekt Warszawa": ["PGE Projekt Warszawa", "Projekt Warszawa"],
    "PGE GiEK Skra Bełchatów": ["PGE GiEK Skra Bełchatów", "PGE GiEK Skra Belchatów", "Skra Bełchatów"],
    "Indykpol AZS Olsztyn": ["Indykpol AZS Olsztyn", "Energa Indykpol AZS Olsztyn"],
    "Aluron CMC Warta Zawiercie": ["Aluron CMC Warta Zawiercie"],
    "Steam Hemarpol Norwid Częstochowa": [
        "Steam Hemarpol Norwid Częstochowa", "NEONET Norwid Częstochowa", "Norwid Częstochowa",
    ],
    "Cuprum Stilon Gorzów": ["Cuprum Stilon Gorzów", "Stilon Gorzów"],
    "Ślepsk Malow Suwałki": ["Ślepsk Malow Suwałki"],
    "ChKS Chełm": ["Podziemia Kredowe ChKS Chełm", "ChKS Chełm"],
    "Asseco Resovia Rzeszów": ["Asseco Resovia Rzeszów"],
    "Trefl Gdańsk": ["Trefl Gdańsk", "Energa Trefl Gdańsk"],
    "ZAKSA Kędzierzyn-Koźle": ["ZAKSA Kędzierzyn-Koźle", "ZAKSA Kedzierzyn-Kozle"],
}

LEAGUES = {
    "men": {
        "base": "https://www.tauronliga.pl",
        "out": "data/tauron.json",
        "competition": "TAURON Liga (mężczyźni)",
        "team_ids": MEN_TEAM_IDS,
        "aliases": MEN_ALIASES,
    },
    # 1. Liga: team names are read straight from the site (no fixed list needed).
    "first": {
        "base": "https://www.tauron1liga.pl",
        "out": "data/tauron1liga.json",
        "competition": "TAURON 1. Liga (mężczyźni)",
        "team_ids": {},
        "aliases": {},
    },
}


def norm(value):
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def get(url, base):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as response:
        final_host = urlparse(response.geturl()).hostname or ""
        allowed = (urlparse(base).hostname or "").removeprefix("www.")
        if final_host != allowed and not final_host.endswith("." + allowed):
            raise RuntimeError(f"{url} redirected to unexpected host: {final_host}")
        return response.read()


def load_previous(path):
    """Previously saved file, so a failed refresh never wipes good data."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build_aliases(cfg, *soups):
    """List of (name as written on the page, canonical name), longest names first.

    Names are discovered from team links (/teams/id/N), so renamed clubs and the
    whole 1. Liga work without maintaining a list by hand.
    """
    mapping = {}
    for canonical, names in cfg["aliases"].items():
        for name in names:
            mapping[name] = canonical
    for soup in soups:
        if soup is None:
            continue
        for link in soup.find_all("a", href=True):
            found = re.search(r"/teams/id/(\d+)", link["href"])
            if not found:
                continue
            name = norm(link.get_text(" ", strip=True))
            if not name:
                img = link.find("img")
                name = norm((img.get("alt") or img.get("title") or "")) if img else ""
            if not name or len(name) > 60:
                continue
            team_id = int(found.group(1))
            if team_id in cfg["team_ids"]:
                mapping[name] = cfg["team_ids"][team_id]
            else:
                mapping.setdefault(name, name)
    return sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True)


def team_in(text, aliases):
    lower = text.casefold()
    for alias, canonical in aliases:
        if alias.casefold() in lower:
            return canonical
    return None


def team_names_in_node(node, aliases):
    names = []
    for img in node.find_all("img"):
        alt = norm(img.get("alt", "")) + " " + norm(img.get("title", ""))
        name = team_in(alt, aliases)
        if name and name not in names:
            names.append(name)
    # Some site cards expose team names as text rather than image alt text.
    text = norm(node.get_text(" ", strip=True))
    for alias, canonical in aliases:
        if alias.casefold() in text.casefold() and canonical not in names:
            names.append(canonical)
    return names


def extract_team_logos(base, aliases, *soups):
    """Collect official team logo URLs from team images on official league pages."""
    logos = {}
    for soup in soups:
        if soup is None:
            continue
        for img in soup.find_all("img"):
            label = norm(img.get("alt", "")) + " " + norm(img.get("title", ""))
            team = team_in(label, aliases)
            if not team:
                continue
            src = norm(img.get("src", "") or img.get("data-src", "") or img.get("data-lazy-src", ""))
            if not src or src.startswith("data:"):
                continue
            logos.setdefault(team, urljoin(base, src))
    return [{"name": name, "logo": logo} for name, logo in sorted(logos.items())]


def season_year(month):
    """Year of a calendar month inside the current season (July - June)."""
    today = datetime.datetime.now(TZ).date()
    start = today.year if today.month >= 7 else today.year - 1
    return start if month >= 7 else start + 1


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

    # Official fixture labels: "sobota, 17 paź, 18:00".
    match = re.search(
        r"(?i)(?:poniedziałek|wtorek|środa|czwartek|piątek|sobota|niedziela)?"
        r"\s*,?\s*(\d{1,2})\s+([a-ząćęłńóśźż]+)"
        r"\.?\s*,?\s*(\d{1,2}:\d{2})?",
        text,
    )
    if not match:
        return None, None
    day, month_name, clock = match.groups()
    month = months.get(month_name.casefold().rstrip("."))
    if not month:
        return None, None
    try:
        parsed = datetime.date(season_year(month), month, int(day))
        return parsed.strftime("%d.%m.%Y"), clock
    except ValueError:
        return None, None


def find_match_id(node):
    """Official match number from the 'Więcej' link, or None when it is not certain."""
    for scope in (node, node.parent):
        if scope is None:
            continue
        ids = set()
        for link in scope.find_all("a", href=True):
            found = re.search(r"/games/action/show/id/(\d+)", link["href"])
            if found:
                ids.add(found.group(1))
        if len(ids) == 1:
            return ids.pop()
        if len(ids) > 1:
            return None  # the scope holds several matches: do not guess
    return None


def parse_matches(soup, aliases):
    found = {}
    for img in soup.find_all("img"):
        name = team_in(norm(img.get("alt", "")) + " " + norm(img.get("title", "")), aliases)
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
            primary_text = re.split(r"(?i)wyniki pierwszego meczu", text, maxsplit=1)[0].strip()
            if not primary_text:
                continue

            names = team_names_in_node(node, aliases)
            # Parent containers may contain both the current fixture and the
            # historical head-to-head. Resolve the two teams only from the part
            # before that heading instead of discarding the whole card.
            if len(names) != 2:
                positions = []
                for alias, canonical in aliases:
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
                for alias, canonical in aliases:
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

            # The official page keeps a fixed 5-set points row (10 numbers).
            # During the first set the set tally may still be shown as "··· ···",
            # so parse the points row even when there is no numeric set tally.
            if score:
                home_sets, away_sets = int(score.group(1)), int(score.group(2))
                tail = middle[score.end():]
            else:
                home_sets = away_sets = 0
                tail = middle

            nums = [int(x) for x in re.findall(r"(?<!\d)\d{1,2}(?!\d)", tail)]
            point_pairs = [
                (nums[i], nums[i + 1])
                for i in range(0, min(len(nums), 10) - 1, 2)
            ]
            nonzero_pairs = [(a, b) for a, b in point_pairs if a != 0 or b != 0]
            set_scores = [f"{a}:{b}" for a, b in nonzero_pairs]

            current_points = None
            if max(home_sets, away_sets) >= 3:
                status = "finished"
            else:
                completed_sets = home_sets + away_sets
                # A live set appears as an extra non-zero points pair after the
                # completed sets. It is not a finished set yet.
                if len(nonzero_pairs) > completed_sets:
                    a, b = nonzero_pairs[-1]
                    current_points = f"{a}:{b}"
                    if set_scores:
                        set_scores.pop()
                status = "live" if current_points is not None or home_sets > 0 or away_sets > 0 else "scheduled"

            date, time = parse_date(text)
            # The date label is often a sibling of the team/score container, not inside it.
            if not date:
                for previous_text in node.find_all_previous(string=True):
                    candidate_date, candidate_time = parse_date(norm(str(previous_text)))
                    if candidate_date:
                        date, time = candidate_date, candidate_time
                        break

            # The official page can show "Trwa" for every card and keep the score
            # row at zero, so its label alone is not a reliable signal. If kickoff
            # passed within a plausible match window, expose the match as live.
            if status == "scheduled" and date and time:
                try:
                    kickoff = datetime.datetime.strptime(
                        f"{date} {time}", "%d.%m.%Y %H:%M"
                    ).replace(tzinfo=TZ)
                    elapsed = (datetime.datetime.now(TZ) - kickoff).total_seconds()
                    if 0 <= elapsed <= 3 * 60 * 60:
                        status = "live"
                except ValueError:
                    pass

            key = (date or "", time or "", home, away, home_sets, away_sets, tuple(set_scores))
            found[key] = {
                "id": find_match_id(node),
                "date": date or "Termin do potwierdzenia",
                "time": time,
                "status": status,
                "home": home,
                "away": away,
                "home_sets": home_sets,
                "away_sets": away_sets,
                "set_scores": set_scores,
                "current_points": current_points,
            }
            break

    # A fixture is identified by its actual date, kickoff and unordered team pair.
    grouped = {}
    for match in found.values():
        pair = tuple(sorted((match["home"], match["away"])))
        key = (match["date"], match.get("time") or "", pair)
        # Prefer completed scorelines, then the candidate with the most set scores.
        quality = (
            1 if match["status"] == "finished" else 0,
            len(match.get("set_scores", [])),
            sum(1 for score in match.get("set_scores", []) if score != "0:0"),
        )
        previous = grouped.get(key)
        if previous is None or quality > previous[0]:
            grouped[key] = (quality, match)
    return [entry[1] for entry in grouped.values()]


def parse_table(soup, aliases):
    """Standings. The page lists rows for many rounds, so keep each team's LATEST row."""
    latest = {}
    for tr in soup.select("tr"):
        cells = [norm(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"], recursive=False)]
        if not cells:
            continue
        team = next(
            (canonical for alias, canonical in aliases
             if any(alias.casefold() in c.casefold() for c in cells)),
            None,
        )
        if not team:
            continue
        nums = []
        for cell in cells:
            value = cell.replace(" ", "")
            if re.fullmatch(r"\d+", value):
                nums.append(int(value))
        # Official table order: rank, league points, played, wins, losses,
        # sets won/lost and points won/lost, followed by scoreline counts.
        if len(nums) < 9:
            continue
        row = {
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
        }
        current = latest.get(team)
        if current is None or row["played"] > current["played"]:
            latest[team] = row
    return sorted(latest.values(), key=lambda row: row["rank"])


def run_league(key, cfg):
    base = cfg["base"]
    out = Path(cfg["out"])
    previous = load_previous(out)

    games = BeautifulSoup(get(base + "/games/nocookies/1.html", base), "html.parser")

    table_soup = None
    table_error = None
    try:
        table_soup = BeautifulSoup(get(base + "/table/nocookies/1.html", base), "html.parser")
    except Exception as exc:  # network / redirect problems
        table_error = exc

    aliases = build_aliases(cfg, games, table_soup)

    matches = parse_matches(games, aliases)
    if not matches:
        raise RuntimeError("No matches parsed; refusing to overwrite the feed.")
    if len(matches) < 4:
        print(f"WARNING [{key}]: only {len(matches)} matches parsed (end of season or a layout change?).")

    standings = []
    if table_soup is not None:
        standings = parse_table(table_soup, aliases)
        if len(standings) < 8:
            table_error = table_error or RuntimeError(f"only {len(standings)} standings rows parsed")
            standings = []
    if not standings:
        # Keep the last good table instead of publishing an empty one.
        standings = previous.get("table", [])
        print(f"WARNING [{key}]: could not refresh standings, keeping previous table: {table_error}")

    payload = {
        "league": key,
        "teams": extract_team_logos(base, aliases, games, table_soup),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "matches": matches,
        "table": standings,
        "source": base,
        "competition": cfg["competition"],
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[{key}] Updated {len(matches)} matches and {len(standings)} standings rows -> {out}")


def main():
    parser = argparse.ArgumentParser(description="Refresh TAURON Liga data for Volley Hub.")
    parser.add_argument("--league", choices=[*LEAGUES, "all"], default="all")
    args = parser.parse_args()

    keys = list(LEAGUES) if args.league == "all" else [args.league]
    updated = 0
    for key in keys:
        try:
            run_league(key, LEAGUES[key])
            updated += 1
        except Exception as exc:  # one broken league must not block the others
            print(f"WARNING [{key}]: not updated: {exc}", file=sys.stderr)
    if updated == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
