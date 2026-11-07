"""All five II liga groups from VolleyStation, with exact PZPS supplementation."""

import re
from urllib.parse import urljoin

from scripts.update_2liga import PZPS_RESULTS_URL, PZPS_URL, VOLLEYSTATION_TEAMS_URL

from .feed import InvalidFeed, build_feed, validate_feed
from .schema import name_key, team_metadata
from .storage import now

COUNTS = {1: 10, 2: 11, 3: 12, 4: 10, 5: 11}


def pzps_supplement(fixtures, results):
    rows = {}

    def parse_row(row):
        cells = [
            c.get_text(" ", strip=True) for c in row.find_all("td", recursive=False)
        ]
        if len(cells) < 5:
            return None
        index = next(
            (i for i, c in enumerate(cells) if re.match(r"^20\d{2}-\d{2}-\d{2}", c)),
            None,
        )
        if (
            index is None
            or index + 3 >= len(cells)
            or cells[index + 2] not in ("-", "–", "—")
        ):
            return None
        y, m, d = cells[index][:10].split("-")
        home, away = cells[index + 1], cells[index + 3]
        return (f"{d}.{m}.{y}", name_key(home), name_key(away)), cells, index

    for row in fixtures.select("tr"):
        parsed = parse_row(row)
        if not parsed:
            continue
        key, cells, index = parsed
        clock = re.search(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", cells[index])
        if clock:
            rows.setdefault(key, {}).update(
                time=clock[0].zfill(5), time_source=PZPS_URL
            )
    for row in results.select("tr"):
        parsed = parse_row(row)
        if not parsed:
            continue
        key, cells, index = parsed
        pairs = re.findall(
            r"(?<!\d)(\d+)\s*:\s*(\d+)(?!\d)", " ".join(cells[index + 4 :])
        )
        if not pairs:
            continue
        a, b = map(int, pairs[0])
        if max(a, b) != 3:
            continue
        rows.setdefault(key, {}).update(
            home_sets=a,
            away_sets=b,
            set_scores=[f"{h}:{v}" for h, v in pairs[1:]],
            set_scores_source=PZPS_RESULTS_URL,
            details_checked_at=now(),
        )
    return rows


def group_configs(soup):
    configs = {}
    for anchor in soup.select('a[href*="phase-"]'):
        label = " ".join(anchor.get_text(" ", strip=True).split())
        match = re.fullmatch(r"2 liga mężczyzn grupa ([1-5])", label, re.I)
        if not match:
            continue
        number = int(match[1])
        base = urljoin(VOLLEYSTATION_TEAMS_URL, anchor["href"]).rsplit("/teams/", 1)[0]
        configs[number] = {
            "base": base,
            "league": "second",
            "competition": "II Liga Mężczyzn",
            "expected_teams": COUNTS[number],
            "min_matches": COUNTS[number] * (COUNTS[number] - 1),
            "phase": label,
            "group": f"Grupa {number}",
        }
    if set(configs) != set(COUNTS):
        raise InvalidFeed("Nie znaleziono pięciu faz grupowych II ligi")
    return configs


def validate_second(data, previous=None):
    if data.get("league") != "second" or data.get("source") != VOLLEYSTATION_TEAMS_URL:
        raise InvalidFeed("Nieprawidłowe źródło II ligi")
    groups = data.get("groups", [])
    if len(groups) != 5 or {g["name"] for g in groups} != {
        f"Grupa {n}" for n in COUNTS
    }:
        raise InvalidFeed("Niekompletne grupy II ligi")
    metrics = {"matches": 0, "finished": 0, "teams": 0}
    for group in groups:
        number = int(group["name"].split()[-1])
        n = COUNTS[number]
        old = next(
            (
                g
                for g in (previous or {}).get("groups", [])
                if g["name"] == group["name"] and g.get("source") == group["source"]
            ),
            None,
        )
        values = validate_feed(
            group,
            old,
            expected_teams=n,
            min_matches=n * (n - 1),
            expected_source=group["source"],
            expected_league="second",
        )
        if len(group["matches"]) != n * (n - 1):
            raise InvalidFeed("Niepełny sezon zasadniczy " + group["name"])
        for k in metrics:
            metrics[k] += values[k]
    return metrics


def build_second(
    fetch, previous=None, refresh_details=False, detail_cache=None, on_detail=None
):
    teams_page = fetch(VOLLEYSTATION_TEAMS_URL)
    configs = group_configs(teams_page)
    teams = team_metadata(teams_page, VOLLEYSTATION_TEAMS_URL)
    supplement = pzps_supplement(fetch(PZPS_URL), fetch(PZPS_RESULTS_URL))
    groups = []
    extra = {"detail_requests": 0, "reused_details": 0, "refetched_cached_details": 0}
    for number, cfg in sorted(configs.items()):
        old = next(
            (
                g
                for g in (previous or {}).get("groups", [])
                if g["name"] == cfg["group"]
                and g.get("source") == cfg["base"] + "/schedule/"
            ),
            {},
        )
        data, metrics = build_feed(
            fetch,
            old,
            refresh_details,
            detail_cache,
            on_detail,
            config=cfg,
            supplemental=supplement,
            known_teams=teams,
        )
        data["name"] = cfg["group"]
        for match in data["matches"]:
            match["group"] = cfg["group"]
        groups.append(data)
        for k in extra:
            extra[k] += metrics[k]
    data = {
        "league": "second",
        "competition": "II Liga Mężczyzn",
        "source": VOLLEYSTATION_TEAMS_URL,
        "results_source": VOLLEYSTATION_TEAMS_URL,
        "supplemental_source": PZPS_URL,
        "updated_at": now(),
        "groups": groups,
    }
    metrics = validate_second(data, previous)
    metrics.update(extra)
    return data, metrics
