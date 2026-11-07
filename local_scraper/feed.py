"""Build and independently validate a complete Pomorska III liga snapshot."""

import copy
import re
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import urlparse

from scripts import update_pomorska3liga as source

from .schema import card_metadata, name_key, normalize, team_metadata
from .storage import now


class InvalidFeed(ValueError):
    pass


def fixture_key(match):
    return str(match["round"]), str(match["match_number"])


def detail_identity(match):
    return (
        *fixture_key(match),
        *(match.get(k) for k in ("date", "home", "away", "home_sets", "away_sets")),
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


def live_sets(match):
    home, away = match.get("home_sets"), match.get("away_sets")
    if (
        type(home) is not int
        or type(away) is not int
        or not 0 <= home < 3
        or not 0 <= away < 3
    ):
        raise InvalidFeed("Nieprawidłowy wynik trwającego meczu")
    pairs = []
    wins = [0, 0]
    for index, value in enumerate(match.get("set_scores", [])):
        a, b = map(int, value.split(":"))
        hi, lo = max(a, b), min(a, b)
        target = 15 if index == 4 else 25
        if not (hi >= target and hi - lo >= 2 and (hi == target or hi - lo == 2)):
            raise InvalidFeed("Niepełny set nie może być zapisany jako zakończony")
        pairs.append((a, b))
        wins[int(b > a)] += 1
    if wins != [home, away]:
        raise InvalidFeed("Sety nie odpowiadają wynikowi LIVE")
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


def validate_feed(
    data,
    previous=None,
    *,
    expected_teams=9,
    min_matches=60,
    expected_source=source.SCHEDULE_URL,
    expected_league="pomorska3liga",
):
    if data.get("league") != expected_league or data.get("source") != expected_source:
        raise InvalidFeed("Inna liga lub faza rozgrywek")
    matches, teams, table = (
        data.get("matches", []),
        data.get("teams", []),
        data.get("table", []),
    )
    if (
        len(matches) < min_matches
        or len(teams) != expected_teams
        or len(table) != expected_teams
    ):
        raise InvalidFeed("Niekompletna liczba meczów, drużyn lub wierszy tabeli")
    names = {t["name"] for t in teams}
    if len(names) != expected_teams or {row["team"] for row in table} != names:
        raise InvalidFeed("Tabela nie odpowiada drużynom")
    if sorted(row["rank"] for row in table) != list(range(1, expected_teams + 1)):
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
        elif match["status"] == "live":
            live_sets(match)
        elif match["status"] != "scheduled":
            raise InvalidFeed("Nieobsługiwany status meczu")
    if previous:
        if previous.get("source") != expected_source:
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
    fetch,
    previous=None,
    refresh_details=False,
    detail_cache=None,
    on_detail=None,
    config=None,
    supplemental=None,
    known_teams=None,
):
    cfg = {
        "base": source.BASE,
        "competition": "Pomorska III Liga Męska",
        "league": "pomorska3liga",
        "expected_teams": 9,
        "min_matches": 60,
        "phase": "Pomorska III Liga Męska",
        **(config or {}),
    }
    schedule_url = cfg["base"] + "/schedule/"
    results_url = cfg["base"] + "/results/"
    standings_url = cfg["base"] + "/standings/"
    previous = previous or {}
    if previous and previous.get("source") != schedule_url:
        raise InvalidFeed("Cache pochodzi z innej fazy rozgrywek")
    schedule_soup = fetch(schedule_url)
    results_soup = fetch(results_url)
    schedule = source.parse_matches(schedule_soup, schedule_url)
    results = source.parse_matches(results_soup, results_url)
    observed_teams = {
        **(known_teams or {}),
        **team_metadata(schedule_soup, schedule_url),
        **team_metadata(results_soup, results_url),
    }
    if known_teams is None:
        previous_teams = {
            name_key(t["name"]): t
            for t in previous.get("teams", [])
            if t.get("id") and t.get("id_source")
        }
        if len(previous_teams) == cfg["expected_teams"]:
            official_teams = previous_teams
        else:
            official_teams = team_metadata(
                fetch(cfg["base"] + "/teams/"), cfg["base"] + "/teams/"
            )
    else:
        official_teams = known_teams
    for key, known in official_teams.items():
        observed_teams.setdefault(key, dict(known))
        observed_teams[key].update(
            id=known.get("id"),
            id_source=known.get("id_source"),
            badge_id=known.get("badge_id"),
        )
    observed_cards = {
        **card_metadata(schedule_soup, schedule_url),
        **card_metadata(results_soup, results_url),
    }
    standings_soup = fetch(standings_url)
    table = source.parse_table(standings_soup, expected_teams=cfg["expected_teams"])
    if len(table) != cfg["expected_teams"]:
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
    for match in matches:
        extra = (supplemental or {}).get(
            (match["date"], name_key(match["home"]), name_key(match["away"])), {}
        )
        if not match.get("time") and extra.get("time"):
            match["time"] = extra["time"]
            match["time_source"] = extra.get("time_source")
        if match["status"] == "finished" and (
            extra.get("home_sets"),
            extra.get("away_sets"),
        ) == (match["home_sets"], match["away_sets"]):
            try:
                completed_sets(extra)
                match["set_scores"] = list(extra["set_scores"])
                match["set_scores_source"] = extra.get("set_scores_source")
                match["details_checked_at"] = extra.get("details_checked_at")
            except (InvalidFeed, ValueError, TypeError):
                pass
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
        match["current_points"] = values.get("current_points")
        if (
            match["status"] in ("live", "scheduled")
            and "home_sets" in values
            and "away_sets" in values
        ):
            match["home_sets"] = values["home_sets"]
            match["away_sets"] = values["away_sets"]
            if max(values["home_sets"], values["away_sets"]) == 3:
                match["status"] = "finished"
            elif values["home_sets"] + values["away_sets"] or values.get(
                "current_points"
            ) not in (None, "0:0"):
                match["status"] = "live"
        if not match.get("time"):
            match["time"] = values["time"]
            match["time_source"] = match["match_url"]
        if match["status"] == "live":
            live_sets(match)
        elif match["status"] == "finished":
            completed_sets(match)
        match["details_checked_at"] = now()
        match["set_scores_source"] = match["match_url"]
        if on_detail and match["status"] == "finished":
            on_detail(copy.deepcopy(match))

    for match in matches:
        if match["status"] == "live" or (
            match["status"] == "scheduled" and not match.get("time")
        ):
            detail(match)
            continue
        if match["status"] != "finished":
            continue
        if match.get("set_scores") and match.get("time") and not refresh_details:
            completed_sets(match)
            reused.append(match)
            continue
        old = cached.get(detail_identity(match))
        if old and not refresh_details:
            try:
                completed_sets(old)
                match["set_scores"] = copy.deepcopy(old["set_scores"])
                match["details_checked_at"] = old.get("details_checked_at")
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
    known.update({t["name"]: t["logo"] for t in observed_teams.values()})
    logos = source.parse_team_logos(
        standings_soup, standings_url, known_logos=known, fetch_page=fetch
    )
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
        "league": cfg["league"],
        "competition": cfg["competition"],
        "phase": cfg["phase"],
        "source": schedule_url,
        "results_source": results_url,
        "standings_source": standings_url,
        "updated_at": now(),
        "teams": [{"name": name, "logo": logos.get(name, "")} for name in names],
        "matches": matches,
        "table": table,
    }
    normalize(data, observed_teams, observed_cards)
    metrics = validate_feed(
        data,
        previous,
        expected_teams=cfg["expected_teams"],
        min_matches=cfg["min_matches"],
        expected_source=schedule_url,
        expected_league=cfg["league"],
    )
    metrics.update(
        reused_details=len(reused),
        refetched_cached_details=repaired,
        detail_requests=detail_requests,
    )
    return data, metrics


def validate_output(data, previous=None):
    if data.get("league") == "second":
        from .second import validate_second

        return validate_second(data, previous)
    return validate_feed(data, previous)
