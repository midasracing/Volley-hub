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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        # Read the actual names printed by PLS this season. A historical
        # sponsor-name map must never override the official display name.
        "team_ids": {},
        "aliases": {},
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


def extract_team_logos(base, aliases, previous, *soups):
    """Official team logos and IDs, with a safe last-known-good fallback.

    The PLS /teams/id/<id> link is the stable identity. Never infer a logo
    by fuzzy team-name matching; sponsorship names can change each season.
    """
    current = {}
    for soup in soups:
        if soup is None:
            continue
        for link in soup.find_all("a", href=True):
            found = re.search(r"/teams/id/(\d+)", link["href"])
            if not found:
                continue
            team_id = found.group(1)
            label = norm(link.get_text(" ", strip=True))
            if not label:
                img = link.find("img")
                label = norm((img.get("alt") or img.get("title") or "")) if img else ""
            team = team_in(label, aliases)
            if not team:
                continue
            row = current.setdefault(team, {"name": team, "id": team_id, "logo": ""})
            row["id"] = team_id
            image = link.find("img")
            if image is not None:
                url = norm(image.get("src", "") or image.get("data-src", "") or image.get("data-lazy-src", ""))
                if url and not url.startswith("data:"):
                    row["logo"] = urljoin(base, url)

        # Other official layouts show club images outside the team link.
        for img in soup.find_all("img"):
            label = norm(img.get("alt", "")) + " " + norm(img.get("title", ""))
            team = team_in(label, aliases)
            if not team:
                continue
            url = norm(img.get("src", "") or img.get("data-src", "") or img.get("data-lazy-src", ""))
            if not url or url.startswith("data:"):
                continue
            row = current.setdefault(team, {"name": team, "logo": ""})
            if not row.get("logo"):
                row["logo"] = urljoin(base, url)

    old_by_id = {str(row["id"]): row for row in previous.get("teams", [])
                 if isinstance(row, dict) and row.get("id")}
    old_by_name = {row["name"].casefold(): row for row in previous.get("teams", [])
                   if isinstance(row, dict) and row.get("name")}
    for team, row in current.items():
        if row.get("logo"):
            continue
        old = old_by_id.get(str(row.get("id"))) or old_by_name.get(team.casefold(), {})
        row["logo"] = old.get("logo", "")
    return sorted(current.values(), key=lambda row: row["name"])


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


def detect_competition(text, default_competition):
    """Identify cup/supercup fixtures from the official match-card label."""
    label = norm(text)
    patterns = [
        (r"(?i)AL[-‑– ]?KO\s+Superpuchar\s+Polski(?:\s+Mężczyzn)?(?:\s+\d{4})?", "AL-KO Superpuchar Polski"),
        (r"(?i)TAURON\s+Puchar\s+Polski", "TAURON Puchar Polski"),
        (r"(?i)Puchar\s+Polski", "Puchar Polski"),
        (r"(?i)Superpuchar\s+Polski", "Superpuchar Polski"),
    ]
    for pattern, name in patterns:
        if re.search(pattern, label):
            return name
    if "1. Liga" in default_competition:
        return "TAURON 1. Liga"
    return "TAURON Liga"


def parse_matches(soup, aliases, default_competition="TAURON Liga"):
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

            # Kickoff time alone is NOT evidence of a live match.
            # A delayed/postponed fixture can keep its original start time.

            key = (date or "", time or "", home, away, home_sets, away_sets, tuple(set_scores))
            found[key] = {
                "id": find_match_id(node),
                "competition": detect_competition(text, default_competition),
                "date": date or "Termin do potwierdzenia",
                "time": time,
                "status": status,
                "home": home,
                "away": away,
                "home_sets": home_sets,
                "away_sets": away_sets,
                "set_scores": set_scores,
                "set_points": [
                    {"home": int(pair.split(":")[0]), "away": int(pair.split(":")[1])}
                    for pair in set_scores
                ],
                "home_points": sum(int(pair.split(":")[0]) for pair in set_scores),
                "away_points": sum(int(pair.split(":")[1]) for pair in set_scores),
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


def detail_metadata(soup):
    """Extract optional PLS game details without guessing missing information.

    PLS labels the fixture ordinal as 'Termin', which is kept alongside
    the round field for transparency. Channel names come from TV image alt.
    """
    data = {}
    headings = soup.find_all(re.compile(r"^h[1-6]$", re.I))
    for heading in headings:
        label = norm(heading.get_text(" ", strip=True)).casefold()
        if label not in ("szczegóły", "informacje o hali", "transmisje"):
            continue
        elements = []
        for element in heading.next_elements:
            if element is heading:
                continue
            if getattr(element, "name", None) and re.fullmatch(r"h[1-6]", element.name, re.I):
                break
            if getattr(element, "name", None) in ("td", "th", "img", "tr"):
                elements.append(element)
        if label == "szczegóły":
            rows = []
            for el in elements:
                if el.name == "tr":
                    cells = [norm(c.get_text(" ", strip=True)) for c in el.find_all(["th", "td"], recursive=False)]
                    if len(cells) >= 2:
                        rows.append((cells[0].rstrip(":"), cells[1]))
            for key, val in rows:
                if key.casefold() == "termin" and val.isdigit():
                    data["term_number"] = int(val)
                elif key.casefold() == "faza":
                    data["phase"] = val
                elif key.casefold() == "numer meczu":
                    data["match_number"] = val
        elif label == "informacje o hali":
            venue = {}
            for el in elements:
                if el.name != "tr":
                    continue
                cells = [norm(c.get_text(" ", strip=True)) for c in el.find_all(["th", "td"], recursive=False)]
                if len(cells) < 2:
                    continue
                key, value = cells[0].rstrip(":").casefold(), cells[1]
                if key == "nazwa":
                    venue["name"] = value
                elif key == "adres":
                    venue["address"] = value
                elif key == "miasto":
                    venue["city"] = value
            if venue.get("name"):
                data["venue"] = venue
        elif label == "transmisje":
            names = []
            for el in elements:
                if el.name != "img":
                    continue
                value = norm(el.get("alt", "") or el.get("title", ""))
                if value and ("tv" in value.casefold() or "polsat" in value.casefold()) and value not in names:
                    names.append(value)
            if names:
                data["broadcast"] = names
    return data


def build_official_fixture_teams(matches, previous):
    old_by_id = {str(t["id"]): t for t in previous.get("teams", [])
                 if isinstance(t, dict) and t.get("id")}
    teams = {}
    for match in matches:
        for side in ("home", "away"):
            name = match[side]
            team_id = match.get(side + "_team_id")
            logo = match.get(side + "_logo", "")
            old = old_by_id.get(str(team_id), {})
            if not logo:
                logo = old.get("logo", "")
            item = teams.setdefault(name, {"name": name, "logo": "", "id": team_id})
            if logo:
                item["logo"] = logo
            if team_id:
                item["id"] = team_id
    return sorted(teams.values(), key=lambda x: x["name"])


def parse_full_season(soup, key, base, previous=None):
    """Read all official round-grouped fixture cards, including future games.

    The featured match carousel is not the season schedule: using its team
    images alone yields only about 25 matches. Every fixture has an official
    data-game-id under a data-round container in the complete list.
    """
    previous = previous or {}
    old_by_id = {
        str(x["id"]): x for x in previous.get("matches", [])
        if isinstance(x, dict) and x.get("id")
    }
    parsed = {}
    for card in soup.select("section[data-game-id]"):
        # A PLS round wrapper can contain later rounds in the parsed DOM.
        # The nearest preceding heading determines the actual fixture round.
        heading = card.find_previous(
            lambda tag: getattr(tag, "name", None) in ("h2", "h3", "h4", "h5", "h6")
            and re.search(r"^Kolejka\s*:\s*\d+", norm(tag.get_text(" ", strip=True)), re.I)
        )
        if heading is None:
            continue
        game_id = str(card.get("data-game-id", "")).strip()
        if not game_id:
            continue
        home_node = card.select_one(".game-team.left")
        away_node = card.select_one(".game-team.right")
        if not home_node or not away_node:
            continue
        home = norm(home_node.get_text(" ", strip=True))
        away = norm(away_node.get_text(" ", strip=True))
        if not home or not away:
            continue
        date_node = card.select_one(".game-date")
        date, time = parse_date(norm(date_node.get_text(" ", strip=True))) if date_node else (None, None)
        score_nodes = card.select(".game-result .game-score")
        score_values = [norm(el.get_text(" ", strip=True)) for el in score_nodes[:2]]
        valid_score = len(score_values) == 2 and all(re.fullmatch(r"[0-3]", v) for v in score_values)
        hs, ass = (int(score_values[0]), int(score_values[1])) if valid_score else (0, 0)
        class_names = " ".join(card.select_one(".game-box").get("class", [])) if card.select_one(".game-box") else ""
        status = "finished" if max(hs, ass) == 3 else "live" if "live" in class_names or hs + ass > 0 else "scheduled"

        phase_node = card.select_one(".game-stage")
        phase = norm(phase_node.get_text(" ", strip=True)) if phase_node else "Faza Zasadnicza"
        channel_img = card.select_one(".game-tv img")
        channel = norm(channel_img.get("title", "") or channel_img.get("alt", "")) if channel_img else ""
        team_ids = [x.strip() for x in (card.get("data-team") or "").split(",") if x.strip()]
        logos = []
        for side in ("left", "right"):
            image = card.select_one(".game-logo." + side + " img")
            image_url = image.get("src") or image.get("data-src") if image else ""
            logos.append(urljoin(base, image_url) if image_url and not image_url.startswith("data:") else "")

        round_value = re.search(r"Kolejka\s*:\s*(\d+)", heading.get_text(" ", strip=True), re.I).group(1)
        try:
            round_number = int(round_value)
        except (ValueError, TypeError):
            round_number = None
        previous_game = old_by_id.get(game_id, {})
        set_scores = previous_game.get("set_scores", []) if (
            previous_game.get("home") == home and previous_game.get("away") == away
            and previous_game.get("home_sets") == hs and previous_game.get("away_sets") == ass
        ) else []
        # Historic points are only reused when the result and teams match.
        # A live game's points may change; never freeze them from an old poll.
        if status != "finished":
            set_scores = []
        game = {
            "id": game_id,
            "league": key,
            "competition": "TAURON 1. Liga" if key == "first" else "TAURON Liga",
            "date": date or "Termin do potwierdzenia",
            "time": time,
            "date_iso": datetime.datetime.strptime(date, "%d.%m.%Y").date().isoformat() if date else None,
            "round": round_number,
            "round_source_label": "Kolejka",
            "phase": phase,
            "status": status,
            "home": home,
            "away": away,
            "home_sets": hs,
            "away_sets": ass,
            "set_scores": list(set_scores),
            "set_points": [{"home": int(x.split(":")[0]), "away": int(x.split(":")[1])} for x in set_scores],
            "home_points": sum(int(x.split(":")[0]) for x in set_scores),
            "away_points": sum(int(x.split(":")[1]) for x in set_scores),
            "current_points": None,
            "source_url": f"{base}/games/action/show/id/{game_id}/nocookies/1.html",
            "home_team_id": team_ids[0] if len(team_ids) >= 1 else None,
            "away_team_id": team_ids[1] if len(team_ids) >= 2 else None,
            "home_logo": logos[0],
            "away_logo": logos[1],
        }
        if channel:
            game["broadcast"] = [channel]
        for field in ("venue", "match_number"):
            if field in previous_game:
                game[field] = previous_game[field]
        parsed[game_id] = game
    return list(parsed.values())


def _standing_ratio(won, lost):
    """PLS tie-break ratio, treating an unbeaten record as the highest ratio."""
    return won / lost if lost else float("inf") if won else 0.0


def _standings_sort_key(row):
    # PLS: league points, wins, set ratio, small-point ratio.
    return (
        -row["points"], -row["wins"],
        -_standing_ratio(row["sets_for"], row["sets_against"]),
        -_standing_ratio(row["points_for"], row["points_against"]),
    )


def _mini_table(tied, matches):
    """Head-to-head mini-table, used only after every normal PLS tie-break."""
    names = {row["team"] for row in tied}
    mini = {name: {
        "team": name, "points": 0, "wins": 0,
        "sets_for": 0, "sets_against": 0,
        "points_for": 0, "points_against": 0,
    } for name in names}
    played = False
    for match in matches:
        if match.get("status") != "finished":
            continue
        home, away = match.get("home"), match.get("away")
        if home not in names or away not in names:
            continue
        hs, ass = int(match["home_sets"]), int(match["away_sets"])
        if max(hs, ass) != 3:
            continue
        played = True
        for name, won, lost, points_for, points_against in (
            (home, hs, ass, match.get("home_points", 0), match.get("away_points", 0)),
            (away, ass, hs, match.get("away_points", 0), match.get("home_points", 0)),
        ):
            r = mini[name]
            r["wins"] += int(won > lost)
            r["points"] += 3 if won == 3 and lost <= 1 else 2 if won == 3 else 1 if won == 2 else 0
            r["sets_for"] += won
            r["sets_against"] += lost
            r["points_for"] += points_for
            r["points_against"] += points_against
    return mini if played else None


def rank_standings(rows, matches=()):
    """Re-rank latest official statistics, never reuse a historical round rank.

    The PLS /table page includes snapshots from *multiple* earlier rounds. A
    club's newest row is authoritative for its statistics but its rank column
    refers to that snapshot, not necessarily the newest league-wide ranking.
    """
    ordered = sorted((dict(row) for row in rows),
                     key=lambda row: (_standings_sort_key(row), row["team"].casefold()))
    result = []
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and _standings_sort_key(ordered[j]) == _standings_sort_key(ordered[i]):
            j += 1
        tied = ordered[i:j]
        if len(tied) > 1:
            mini = _mini_table(tied, matches)
            if mini:
                tied.sort(key=lambda row: (_standings_sort_key(mini[row["team"]]),
                                            row["rank"], row["team"].casefold()))
            else:
                # Before the clubs meet, retain source tie ordering where
                # available. Do not confuse that historic rank with our output.
                tied.sort(key=lambda row: (row["rank"], row["team"].casefold()))
        result.extend(tied)
        i = j
    for pos, row in enumerate(result, 1):
        row["rank"] = pos
    return result


def parse_table(soup, aliases, matches=()):
    """Read each club's latest official totals and build a single current table."""
    latest = {}
    alias_names = {alias.casefold(): canonical for alias, canonical in aliases}
    for tr in soup.select("tr"):
        nodes = tr.find_all(["td", "th"], recursive=False)
        if len(nodes) < 10:
            continue
        cells = [norm(node.get_text(" ", strip=True)) for node in nodes]
        # Only the second table cell is a club name; searching all cells
        # accidentally includes historical and unrelated HTML tables.
        team = alias_names.get(cells[1].casefold())
        if not team or not re.fullmatch(r"\d+", cells[0]):
            continue
        values = []
        for cell in cells:
            stripped = cell.replace(" ", "")
            if re.fullmatch(r"\d+", stripped):
                values.append(int(stripped))
        # rank, league points, played, won, lost, sets for/against,
        # small points for/against (ratios and scoreline totals follow).
        if len(values) < 9:
            continue
        row = {
            "rank": values[0],
            "team": team,
            "points": values[1],
            "played": values[2],
            "wins": values[3],
            "losses": values[4],
            "sets_for": values[5],
            "sets_against": values[6],
            "points_for": values[7],
            "points_against": values[8],
        }
        current = latest.get(team)
        # Use the *last* occurrence when a team has equal games played.
        # The official site can update points/corrections without a new game.
        if current is None or row["played"] >= current["played"]:
            latest[team] = row
    return rank_standings(list(latest.values()), matches)


def validate_standings(table, matches, team_count):
    """Fail closed on incomplete, inconsistent or mixed-round standings."""
    if len(table) != team_count:
        raise RuntimeError(f"PLS table has {len(table)} of {team_count} clubs")
    names = {match[side] for match in matches for side in ("home", "away")}
    if {row["team"] for row in table} != names or len(names) != team_count:
        raise RuntimeError("Standings teams do not match the official fixture list")
    if [row["rank"] for row in table] != list(range(1, team_count + 1)):
        raise RuntimeError("Standings have repeated or missing ranks")
    totals = {name: {
        "points": 0, "played": 0, "wins": 0, "losses": 0,
        "sets_for": 0, "sets_against": 0,
        "points_for": 0, "points_against": 0,
    } for name in names}
    for match in matches:
        if match["status"] != "finished":
            continue
        hs, ass = match["home_sets"], match["away_sets"]
        if max(hs, ass) != 3:
            raise RuntimeError(f"Unfinished final score: {match['id']}")
        for name, won, lost, scored, conceded in (
            (match["home"], hs, ass, match["home_points"], match["away_points"]),
            (match["away"], ass, hs, match["away_points"], match["home_points"]),
        ):
            row = totals[name]
            row["played"] += 1
            row["wins"] += int(won > lost)
            row["losses"] += int(won < lost)
            row["points"] += 3 if won == 3 and lost <= 1 else 2 if won == 3 else 1 if won == 2 else 0
            row["sets_for"] += won
            row["sets_against"] += lost
            row["points_for"] += scored
            row["points_against"] += conceded
    for row in table:
        expected = totals[row["team"]]
        wrong = {field: (row[field], expected[field]) for field in expected
                 if row[field] != expected[field]}
        if wrong:
            raise RuntimeError(f"PLS table and finished results differ for {row['team']}: {wrong}")
    return True


def verify_detail_identity(soup, match):
    """Reject error pages/redirects instead of copying an unrelated arena."""
    title = norm(soup.title.get_text(" ", strip=True)) if soup.title else ""
    if not title:
        raise RuntimeError(f"No page title for official match {match['id']}")
    names = (match["home"].casefold(), match["away"].casefold())
    if not all(name in title.casefold() for name in names):
        raise RuntimeError(
            f"Wrong PLS match-detail page for {match['id']}: {title[:160]!r}"
        )


def read_match_detail(soup, match):
    """Return confirmed point scores only when the detail agrees with fixture.

    A detail page can contain multiple match widgets and previous head-to-head
    scorelines. Never use an unrelated match's point pairs.
    """
    played = match["home_sets"] + match["away_sets"]
    for box in soup.select(".game-result-box"):
        score_elements = box.select(".game-result .game-score")
        result = [norm(x.get_text(" ", strip=True)) for x in score_elements[:2]]
        if result != [str(match["home_sets"]), str(match["away_sets"])]:
            continue
        text = norm(box.get_text(" ", strip=True))
        found = re.search(r"Małe punkty\s*:\s*(.*?)(?:Złoty set\s*:|$)", text, re.I)
        if not found:
            continue
        values = [int(n) for n in re.findall(r"(?<!\d)\d{1,3}(?!\d)", found.group(1))]
        if len(values) < 10:
            continue
        pairs = [(values[i], values[i + 1]) for i in range(0, 10, 2)]
        if match["status"] == "finished":
            complete = pairs[:played]
            if len(complete) != played or any(a == b or not a or not b for a,b in complete):
                continue
            if sum(a > b for a,b in complete) != match["home_sets"]:
                continue
            if sum(b > a for a,b in complete) != match["away_sets"]:
                continue
            return [f"{a}:{b}" for a,b in complete], None
        # A non-finished fixture may have a partial current set.
        completed = pairs[:played]
        if any(a == b or not a or not b for a,b in completed):
            continue
        next_pair = pairs[played] if played < len(pairs) else (0, 0)
        active = f"{next_pair[0]}:{next_pair[1]}" if any(next_pair) else None
        return [f"{a}:{b}" for a,b in completed], active
    return None, None


def apply_point_scores(match, scores, active=None):
    match["set_scores"] = scores
    match["set_points"] = [
        {"home": int(x.split(":")[0]), "away": int(x.split(":")[1])}
        for x in scores
    ]
    match["home_points"] = sum(x["home"] for x in match["set_points"])
    match["away_points"] = sum(x["away"] for x in match["set_points"])
    match["current_points"] = active


def run_league(key, cfg, full_details=False):
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

    matches = parse_full_season(games, key, base, previous)
    # The carousel has detailed point-by-point summaries for recent games.
    # Enrich fixture cards by match ID without losing future fixtures.
    carousel = parse_matches(games, aliases, cfg["competition"])
    carousel_by_id = {str(m["id"]): m for m in carousel if m.get("id")}
    for match in matches:
        detail = carousel_by_id.get(match["id"])
        if detail and detail.get("home_sets") == match["home_sets"] and detail.get("away_sets") == match["away_sets"]:
            for field in ("set_scores", "set_points", "home_points", "away_points", "current_points"):
                match[field] = detail.get(field)
            if detail.get("status") == "live" and match["status"] != "finished":
                match["status"] = "live"
    # Complete regular-season round counts: 14*13 and 16*15 matches.
    team_count = 14 if key == "men" else 16
    expected = team_count * (team_count - 1)
    expected_rounds = 2 * (team_count - 1)
    games_per_round = team_count // 2
    actual_rounds = {}
    for match in matches:
        rnd = match.get("round")
        actual_rounds[rnd] = actual_rounds.get(rnd, 0) + 1
    if any(actual_rounds.get(r) != games_per_round for r in range(1, expected_rounds + 1)):
        raise RuntimeError(
            f"Invalid rounds for {key}: {actual_rounds}; expected "
            f"{games_per_round} games in each of {expected_rounds} rounds."
        )
    if len(matches) < expected:
        raise RuntimeError(
            f"Incomplete 2026/27 regular-season schedule: got {len(matches)} / {expected} "
            f"matches for {key}; refusing to overwrite the feed."
        )

    # Some match cards lag behind the dedicated match page. For today's fixtures
    # whose kickoff has passed, try the official per-match URL as a second source.
    # Merge only when it yields a more informative score/status for the same match.
    now = datetime.datetime.now(TZ)
    for match in list(matches):
        if not match.get("id") or not match.get("date") or not match.get("time"):
            continue
        try:
            kickoff = datetime.datetime.strptime(
                f"{match['date']} {match['time']}", "%d.%m.%Y %H:%M"
            ).replace(tzinfo=TZ)
        except ValueError:
            continue
        if kickoff.date() != now.date() or now < kickoff or match.get("status") == "finished":
            continue
        detail_url = f"{base}/games/action/show/id/{match['id']}/nocookies/1.html"
        try:
            detail_soup = BeautifulSoup(get(detail_url, base), "html.parser")
            detail_matches = parse_matches(detail_soup, aliases, cfg["competition"])
        except Exception as exc:
            print(f"INFO [{key}]: detail page unavailable for match {match['id']}: {exc}")
            continue
        pair = {match.get("home"), match.get("away")}
        candidates = [
            candidate for candidate in detail_matches
            if {candidate.get("home"), candidate.get("away")} == pair
            and candidate.get("date") == match.get("date")
        ]
        if not candidates:
            continue
        def score_quality(candidate):
            return (
                1 if candidate.get("status") == "finished" else 0,
                1 if candidate.get("current_points") else 0,
                len(candidate.get("set_scores", [])),
                int(candidate.get("home_sets", 0)) + int(candidate.get("away_sets", 0)),
            )
        better = max(candidates, key=score_quality)
        if score_quality(better) > score_quality(match):
            match.update(better)
            match["id"] = match.get("id") or better.get("id")

    # Complete missing historical point scores from each OFFICIAL match page.
    # Fetch only missing finished games; previous valid scores remain cached.
    missing_points = [
        m for m in matches if m["status"] == "finished"
        and len(m.get("set_scores", [])) != m["home_sets"] + m["away_sets"]
    ]
    if missing_points:
        print(f"INFO [{key}]: fetching points for {len(missing_points)} finished matches",
              flush=True)

    def fetch_missing_points(match):
        url = f"{base}/games/action/show/id/{match['id']}/nocookies/1.html"
        detail = BeautifulSoup(get(url, base), "html.parser")
        verify_detail_identity(detail, match)
        scores, active = read_match_detail(detail, match)
        return match["id"], scores, active, detail_metadata(detail)

    if missing_points:
        by_id = {m["id"]: m for m in matches}
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(fetch_missing_points, m): m for m in missing_points}
            for future in as_completed(futures):
                match = futures[future]
                try:
                    mid, scores, active, metadata = future.result()
                    if scores is not None:
                        apply_point_scores(by_id[mid], scores, active)
                    by_id[mid].update(metadata)
                    # The detailed page has been examined; persist that fact
                    # even when PLS has not yet announced arena or broadcast.
                    by_id[mid]["details_checked_at"] = datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat()
                except Exception as exc:
                    print(f"WARNING [{key}]: points for {match['id']} unavailable: {exc}",
                          file=sys.stderr)
    still_missing = []
    for m in matches:
        if m["status"] != "finished":
            continue
        scores = m.get("set_scores", [])
        expected_sets = m["home_sets"] + m["away_sets"]
        try:
            pairs = [tuple(int(x) for x in score.split(":")) for score in scores]
            valid = (
                len(pairs) == expected_sets
                and all(len(pair) == 2 and pair[0] != pair[1] for pair in pairs)
                and sum(a > b for a, b in pairs) == m["home_sets"]
                and sum(b > a for a, b in pairs) == m["away_sets"]
                and sum(a for a, _ in pairs) == m.get("home_points")
                and sum(b for _, b in pairs) == m.get("away_points")
            )
        except (ValueError, TypeError):
            valid = False
        if not valid:
            still_missing.append(m["id"])
    if still_missing:
        raise RuntimeError(
            f"Incomplete official set points for {len(still_missing)} finished "
            f"games in {key}, examples: {still_missing[:5]}; refusing to overwrite."
        )

    # Keep the old app fields, and add explicit league identity and ISO dates.
    for match in matches:
        match["league"] = key
        match["source_url"] = (
            f"{base}/games/action/show/id/{match['id']}/nocookies/1.html"
            if match.get("id") else base + "/games/nocookies/1.html"
        )
        try:
            match["date_iso"] = datetime.datetime.strptime(
                match["date"], "%d.%m.%Y"
            ).date().isoformat()
        except (ValueError, TypeError):
            match["date_iso"] = None

    # Preserve confirmed details by match ID, not by club name. Current fixture
    # TV labels take priority over old announcements (broadcasters may change).
    previous_by_id = {
        str(row["id"]): row for row in previous.get("matches", [])
        if isinstance(row, dict) and row.get("id")
    }
    for match in matches:
        old = previous_by_id.get(str(match["id"]), {})
        for field in ("venue", "match_number", "term_number", "details_checked_at"):
            if field in old and field not in match:
                match[field] = old[field]

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    today = now_utc.astimezone(TZ).date()

    def details_age_days(match):
        raw = match.get("details_checked_at")
        if not raw:
            return float("inf")
        try:
            checked = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if checked.tzinfo is None:
                return float("inf")
            return max(0, (now_utc - checked).total_seconds() / 86400)
        except (TypeError, ValueError):
            return float("inf")

    def details_priority(match):
        try:
            days = (datetime.date.fromisoformat(match["date_iso"]) - today).days
        except (TypeError, ValueError):
            days = 365
        # Prioritize today's matches and the coming 30 days (TV and venues
        # are likeliest to be announced shortly before kickoff).
        if -2 <= days <= 30:
            return (0, abs(days), match["id"])
        if days > 30:
            return (1, days, match["id"])
        return (2, -days, match["id"])

    def due_for_details(match):
        age = details_age_days(match)
        if age < 1 / 48:  # already fetched in this very refresh (points pass)
            return False
        if full_details:
            return True
        if age == float("inf"):
            return True
        try:
            days = (datetime.date.fromisoformat(match["date_iso"]) - today).days
        except (TypeError, ValueError):
            days = 365
        if -2 <= days <= 30:
            return age >= 3
        if days > 30:
            return age >= 28
        return age >= 90  # completed games rarely change their venue

    candidates = sorted(
        (m for m in matches if m.get("id") and due_for_details(m)),
        key=details_priority,
    )
    # Regular frequent updates are bounded. An explicit --full-details run
    # backfills all 422 matches, then later runs reuse the checked timestamp.
    detail_batch = candidates if full_details else candidates[:24]
    if detail_batch:
        print(
            f"INFO [{key}]: refreshing details for {len(detail_batch)} / "
            f"{len(candidates)} due matches (full={full_details})", flush=True
        )

    def fetch_metadata(match):
        detail = BeautifulSoup(get(match["source_url"], base), "html.parser")
        verify_detail_identity(detail, match)
        return match["id"], detail_metadata(detail)

    failed_details = []
    if detail_batch:
        by_id = {m["id"]: m for m in matches}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(fetch_metadata, m): m for m in detail_batch}
            for future in as_completed(futures):
                match = futures[future]
                try:
                    mid, metadata = future.result()
                    by_id[mid].update(metadata)
                    by_id[mid]["details_checked_at"] = now_utc.isoformat()
                except Exception as exc:
                    failed_details.append(match["id"])
                    print(f"WARNING [{key}]: metadata unavailable for "
                          f"{match['id']}: {exc}", file=sys.stderr)
    if full_details:
        unchecked = [m["id"] for m in matches if not m.get("details_checked_at")]
        if unchecked or failed_details:
            raise RuntimeError(
                f"Full details audit incomplete for {key}: "
                f"{len(unchecked)} unchecked and {len(failed_details)} failed "
                f"(examples: {(unchecked + failed_details)[:5]})"
            )

    checked = sum(bool(m.get("details_checked_at")) for m in matches)
    halls = sum(bool(m.get("venue", {}).get("name")) for m in matches)
    tv = sum(bool(m.get("broadcast")) for m in matches)
    print(f"INFO [{key}]: details checked={checked}/{len(matches)}, "
          f"venues={halls}, broadcasts={tv}", flush=True)

    if len(matches) < 4:
        print(f"WARNING [{key}]: only {len(matches)} matches parsed (end of season or a layout change?).")

    standings = []
    if table_soup is not None:
        try:
            standings = parse_table(table_soup, aliases, matches)
            validate_standings(standings, matches, team_count)
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            table_error = exc
            standings = []
    if not standings:
        # A stale previous table is safe only when its totals still match the
        # newly parsed games. Correct its historical ranks as well.
        standings = rank_standings(previous.get("table", []), matches)
        validate_standings(standings, matches, team_count)
        print(f"WARNING [{key}]: official table unavailable; using verified previous totals: {table_error}",
              file=sys.stderr)
    print(f"INFO [{key}]: standings verified: {len(standings)} clubs, "
          f"ranks 1–{len(standings)}, totals agree with completed matches", flush=True)

    payload = {
        "league": key,
        "teams": build_official_fixture_teams(matches, previous),
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
    parser.add_argument(
        "--full-details", action="store_true",
        help="Check official detailed pages for every match (one-time backfill/audit).",
    )
    args = parser.parse_args()

    keys = list(LEAGUES) if args.league == "all" else [args.league]
    updated = 0
    for key in keys:
        try:
            run_league(key, LEAGUES[key], full_details=args.full_details)
            updated += 1
        except Exception as exc:  # one broken league must not block the others
            print(f"WARNING [{key}]: not updated: {exc}", file=sys.stderr)
    if updated == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
