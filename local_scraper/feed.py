"""Build and independently validate a complete Pomorska III liga snapshot."""

import copy
import re
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import urlparse

from scripts import update_pomorska3liga as source

from .storage import now


class InvalidFeed(ValueError):
    pass


def fixture_key(match):
    return match["round"], match["match_number"]


def detail_identity(match):
    return tuple(
        match.get(k) for k in ("id", "date", "home", "away", "home_sets", "away_sets")
    )


def completed_sets(match):
    """Legal best-of-five set sequence; deuce has no arbitrary points ceiling."""
    home, away = match.get("home_sets"), match.get("away_sets")
    if (
        type(home) is not int
        or type(away) is not int
        or sorted((home, away)) not in [[0, 3], [1, 3], [2, 3]]
    ):
        raise InvalidFeed("Nieprawidłowy wynik meczu " + str(match.get("id")))
    scores = match.get("set_scores") or []
    if len(scores) != home + away:
        raise InvalidFeed("Niekompletne sety " + str(match.get("id")))
    pairs = []
    wins = [0, 0]
    for index, score in enumerate(scores):
        if not isinstance(score, str) or not re.fullmatch(r"\d+:\d+", score):
            raise InvalidFeed("Nieprawidłowy zapis seta")
        a, b = map(int, score.split(":"))
        hi, lo = max(a, b), min(a, b)
        target = 15 if index == 4 else 25
        if not (hi >= target and hi - lo >= 2 and (hi == target or hi - lo == 2)):
            raise InvalidFeed("Nielegalny wynik seta " + score)
        wins[int(b > a)] += 1
        pairs.append((a, b))
        if max(wins) == 3 and index != len(scores) - 1:
            raise InvalidFeed("Set rozegrany po zakończeniu meczu")
    if wins != [home, away]:
        raise InvalidFeed("Punkty setów nie zgadzają się z wynikiem meczu")
    return pairs


def standings_discrepancies(matches, table):
    counts = defaultdict(Counter)
    for match in matches:
        if match["status"] != "finished":
            continue
        pairs = completed_sets(match)
        hs, vs = match["home_sets"], match["away_sets"]
        for name, a, b, pf, pa in [
            (match["home"], hs, vs, sum(p[0] for p in pairs), sum(p[1] for p in pairs)),
            (match["away"], vs, hs, sum(p[1] for p in pairs), sum(p[0] for p in pairs)),
        ]:
            counts[name].update(
                played=1,
                wins=int(a > b),
                losses=int(a < b),
                sets_for=a,
                sets_against=b,
                points_for=pf,
                points_against=pa,
                points=(2 if a > b else 1) if min(a, b) == 2 else (3 if a > b else 0),
            )
    keys = (
        "played",
        "wins",
        "losses",
        "sets_for",
        "sets_against",
        "points_for",
        "points_against",
        "points",
    )
    return {
        row["team"]: [
            k
            for k in keys
            if type(row.get(k)) is not int or row[k] != counts[row["team"]][k]
        ]
        for row in table
        if any(
            type(row.get(k)) is not int or row[k] != counts[row["team"]][k]
            for k in keys
        )
    }


def validate_feed(data, previous=None):
    if (
        data.get("league") != "pomorska3liga"
        or data.get("source") != source.SCHEDULE_URL
    ):
        raise InvalidFeed("Inna liga lub faza rozgrywek")
    matches, teams, table = (
        data.get("matches", []),
        data.get("teams", []),
        data.get("table", []),
    )
    if len(matches) < 60 or len(teams) != 9 or len(table) != 9:
        raise InvalidFeed("Niekompletna liczba meczów, drużyn lub wierszy tabeli")
    names = {t["name"] for t in teams}
    if len(names) != 9 or {row["team"] for row in table} != names:
        raise InvalidFeed("Tabela nie odpowiada drużynom")
    if sorted(row["rank"] for row in table) != list(range(1, 10)):
        raise InvalidFeed("Nieprawidłowe miejsca w tabeli")
    if any(urlparse(t.get("logo", "")).scheme not in ("http", "https") for t in teams):
        raise InvalidFeed("Brak logotypu drużyny")
    ids = set()
    keys = set()
    for match in matches:
        if match["id"] in ids or fixture_key(match) in keys:
            raise InvalidFeed("Powtórzony mecz")
        ids.add(match["id"])
        keys.add(fixture_key(match))
        datetime.strptime(match["date"], "%d.%m.%Y")
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", match.get("time") or ""):
            raise InvalidFeed("Brak prawidłowej godziny meczu")
        if (
            match["home"] not in names
            or match["away"] not in names
            or match["home"] == match["away"]
        ):
            raise InvalidFeed("Nieprawidłowe drużyny meczu")
        if match["status"] == "finished":
            completed_sets(match)
        elif match["status"] != "scheduled":
            raise InvalidFeed("Nieobsługiwany status meczu")
    if previous:
        if previous.get("source") != source.SCHEDULE_URL:
            raise InvalidFeed("Cache pochodzi z innej fazy rozgrywek")
        old_keys = {fixture_key(m) for m in previous.get("matches", [])}
        if not old_keys.issubset(keys):
            raise InvalidFeed("Zniknęły mecze z poprzedniego feedu")
        old_results = {
            fixture_key(m)
            for m in previous.get("matches", [])
            if m.get("status") == "finished"
        }
        if not old_results.issubset(
            {fixture_key(m) for m in matches if m["status"] == "finished"}
        ):
            raise InvalidFeed("Zniknęły zakończone wyniki; wymagana kontrola źródła")
    discrepancies = standings_discrepancies(matches, table)
    if discrepancies:
        raise InvalidFeed("Tabela nie zgadza się z meczami: " + str(discrepancies))
    return {
        "matches": len(matches),
        "finished": sum(m["status"] == "finished" for m in matches),
        "teams": len(teams),
    }


def build_feed(
    fetch, previous=None, refresh_details=False, detail_cache=None, on_detail=None
):
    previous = previous or {}
    if previous and previous.get("source") != source.SCHEDULE_URL:
        raise InvalidFeed("Cache pochodzi z innej fazy rozgrywek")
    schedule = source.parse_matches(fetch(source.SCHEDULE_URL), source.SCHEDULE_URL)
    results = source.parse_matches(fetch(source.RESULTS_URL), source.RESULTS_URL)
    standings_soup = fetch(source.STANDINGS_URL)
    table = source.parse_table(standings_soup)
    if len(table) != 9:
        raise InvalidFeed("Niekompletna tabela źródłowa")
    by_key = {fixture_key(m): m for m in schedule}
    if len(by_key) != len(schedule) or len({fixture_key(m) for m in results}) != len(
        results
    ):
        raise InvalidFeed("Duplikaty w źródle")
    for result in results:
        if result["status"] != "finished":
            raise InvalidFeed("Nieprawidłowa strona wyników")
        fixture = by_key.get(fixture_key(result), {})
        result = {**fixture, **result}
        if not result.get("time") and fixture.get("time"):
            result["time"] = fixture["time"]
        by_key[fixture_key(result)] = result
    matches = list(by_key.values())
    cached = {
        detail_identity(m): m
        for m in previous.get("matches", [])
        if m.get("status") == "finished"
    }
    cached.update(
        {
            detail_identity(m): m
            for m in (detail_cache or [])
            if m.get("status") == "finished"
        }
    )
    reused = []
    detail_requests = 0

    def detail(match):
        nonlocal detail_requests
        detail_requests += 1
        values = source.parse_match_detail(fetch(match["match_url"]))
        match["set_scores"] = values["set_scores"]
        if not match.get("time"):
            match["time"] = values["time"]
        completed_sets(match)
        if on_detail:
            on_detail(copy.deepcopy(match))

    for match in matches:
        if match["status"] != "finished":
            continue
        old = cached.get(detail_identity(match))
        if old and not refresh_details:
            try:
                completed_sets(old)
                match["set_scores"] = copy.deepcopy(old["set_scores"])
                if not match.get("time"):
                    match["time"] = old.get("time")
                if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", match.get("time") or ""):
                    reused.append(match)
                    continue
            except (InvalidFeed, TypeError, ValueError):
                pass
        detail(match)
    # The overall set score may stay unchanged after a correction of set points.
    # Fresh standings reveal that drift: refetch affected cached matches once.
    discrepancies = standings_discrepancies(matches, table)
    repaired = 0
    for match in reused:
        if match["home"] in discrepancies or match["away"] in discrepancies:
            detail(match)
            repaired += 1
    known = {
        t["name"]: t["logo"]
        for t in previous.get("teams", [])
        if t.get("name") and t.get("logo")
    }
    logos = source.parse_team_logos(
        standings_soup, source.STANDINGS_URL, known_logos=known, fetch_page=fetch
    )
    for match in matches:
        match.pop("match_url", None)
    matches.sort(
        key=lambda m: (
            datetime.strptime(m["date"], "%d.%m.%Y"),
            m["time"] or "99:99",
            m["round"],
            m["match_number"],
        )
    )
    names = sorted({m[k] for m in matches for k in ("home", "away")}, key=str.casefold)
    data = {
        "league": "pomorska3liga",
        "competition": "Pomorska III Liga Męska",
        "source": source.SCHEDULE_URL,
        "results_source": source.RESULTS_URL,
        "standings_source": source.STANDINGS_URL,
        "updated_at": now(),
        "teams": [{"name": name, "logo": logos.get(name, "")} for name in names],
        "matches": matches,
        "table": table,
    }
    metrics = validate_feed(data, previous)
    metrics.update(
        reused_details=len(reused),
        refetched_cached_details=repaired,
        detail_requests=detail_requests,
    )
    return data, metrics
