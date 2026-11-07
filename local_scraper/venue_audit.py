"""Offline audit of published match venues; never infer a venue from a team."""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

from .schema import name_key
from .storage import atomic_json, now

# Explicit aliases apply only to the Pomorska III liga source. In particular,
# "Trefl Gdańsk" in this category must never alias the club's II liga team.
POMORSKA_ALIASES = {
    name_key(a): b
    for a, b in {
        "KATS Alpat Gdynia": "KATS ALPAT CYMMAT GDYNIA",
        "UKS Olimpijczyk Pruszcz Gd.": "UKS Olimpijczyk Pruszcz Gdański",
        "Trefl Gdańsk": "Energa Trefl Gdańsk III",
        "LSZ Gniewkowo": "LZS GNIEWKO Gniewkowo",
    }.items()
}


def fixture_identity(match):
    return (match["date"], name_key(match["home"]), name_key(match["away"]))


def pzps_record(soup):
    """Read only the public match identity and the explicitly labelled venue."""
    main = soup.select_one('[role="main"]')
    if main is None:
        raise ValueError("Brak szczegółów meczu PZPS")
    headings = [h.get_text(" ", strip=True) for h in main.select("h5")]
    if not any(h.casefold() == "ii liga mężczyzn" for h in headings):
        raise ValueError("Inne rozgrywki PZPS")
    dates = [
        re.fullmatch(r"Rozgrywany dnia:\s*(\d{4})-(\d{2})-(\d{2})", h) for h in headings
    ]
    dates = [d for d in dates if d]
    teams = main.select(".row > .col-xs-5.text-center h4")
    if len(dates) != 1 or len(teams) != 2:
        raise ValueError("Niepełna tożsamość meczu PZPS")
    date = dates[0]
    label = next(
        (h for h in main.select("h5") if h.get_text(strip=True) == "Mecz rozgrywany w"),
        None,
    )
    if label is None:
        raise ValueError("Brak pola miejsca meczu")
    row = label.find_parent(class_="row")
    fields = row.select("h5")
    if len(fields) != 2:
        raise ValueError("Zmieniony układ miejsca meczu")
    lines = [" ".join(line.split()) for line in fields[1].stripped_strings]
    # PZPS sometimes publishes only a city or only an address. Keep the exact
    # text and do not promote a city into the name of a sports hall.
    raw = "\n".join(lines)
    alternatives = bool(re.search(r"dodatkow|druga hala|alternatyw", raw, re.I))
    street = bool(re.search(r"\d|\bul\.|\bal\.", lines[0] if lines else "", re.I))
    venue = (
        {
            "name": lines[1]
            if len(lines) > 1 and not re.match(r"^;", lines[1])
            else None,
            "address": lines[0] if lines and street else None,
            "city": lines[0] if len(lines) == 1 and not street else None,
            "source_text": raw,
            "alternatives_published": alternatives,
        }
        if lines
        else None
    )
    clock = next(
        (
            h
            for h in main.select("h5")
            if h.get_text(strip=True).casefold() == "godzina meczu:"
        ),
        None,
    )
    time = (
        clock.find_parent(class_="row").select("h5")[-1].get_text(strip=True)
        if clock
        else None
    )
    ids = sorted(
        set(
            re.findall(
                r"widgets\.volleystation\.com/(?:court|scoreboard|play-by-play|team-stats)/(\d+)",
                str(main),
            )
        )
    )
    group = next(
        (
            re.fullmatch(r"Grupa ([1-5])", h)
            for h in headings
            if re.fullmatch(r"Grupa ([1-5])", h)
        ),
        None,
    )
    number = next(
        (
            re.fullmatch(r"Mecz numer (\d+)", h)
            for h in headings
            if re.fullmatch(r"Mecz numer (\d+)", h)
        ),
        None,
    )
    return {
        "date": f"{date[3]}.{date[2]}.{date[1]}",
        "home": teams[0].get_text(" ", strip=True),
        "away": teams[1].get_text(" ", strip=True),
        "group": "Grupa " + group[1] if group else None,
        "match_number": number[1] if number else None,
        "time": time
        if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time or "")
        else None,
        "volleystation_ids": ids,
        "venue": venue,
    }


def arbitergo_records(soup):
    records = []
    for detail in soup.select(".delegation-list-detail"):
        category = detail.select_one(".delegation-competition__name")
        if not category or category.get_text(strip=True) != "III Liga Mężczyzn":
            continue
        stamp = detail.select_one(".delegation-date-number")
        date = re.match(
            r"(\d{2})-(\d{2})-(\d{4})\s+(\d{2}:\d{2})",
            stamp.get_text(" ", strip=True) if stamp else "",
        )
        games = detail.select(".delegation-matches-list li")
        address = detail.select_one(".delegation-competition__address")
        if not date or len(games) != 1 or not address:
            continue
        text = " ".join(games[0].stripped_strings).removeprefix("sports_volleyball ")
        teams = re.split(r"\s+-\s+", text)
        if len(teams) != 2:
            continue
        hall = address.select_one(".delegation-competition__hall")
        direct = " ".join(
            str(t).strip()
            for t in address.find_all(string=True, recursive=False)
            if str(t).strip()
        )
        city, sep, street = direct.partition(",")
        number = stamp.select_one(".delegation-date-number__number")
        records.append(
            {
                "date": f"{date[1]}.{date[2]}.{date[3]}",
                "time": date[4],
                "home": teams[0],
                "away": teams[1],
                "source_record_id": number.get_text(strip=True) if number else None,
                "venue": {
                    "name": hall.get_text(" ", strip=True) if hall else None,
                    "city": city.strip() if sep else None,
                    "address": street.strip() if sep else direct or None,
                    "source_text": " ".join(
                        [direct, hall.get_text(" ", strip=True) if hall else ""]
                    ).strip(),
                    "alternatives_published": False,
                },
            }
        )
    return records


def match_record(record, matches, *, aliases=None):
    """Require ordered teams and exact date; reject ambiguous and conflicting IDs."""
    aliases = aliases or {}
    resolved = {
        **record,
        **{
            side: aliases.get(name_key(record[side]), record[side])
            for side in ("home", "away")
        },
    }
    candidates = [
        m for m in matches if fixture_identity(m) == fixture_identity(resolved)
    ]
    if len(candidates) != 1:
        return None, "ambiguous_fixture" if candidates else "no_fixture"
    match = candidates[0]
    if record.get("group") and record["group"] != match.get("group"):
        return None, "group_conflict"
    if record.get("match_number") and str(record["match_number"]) != str(
        match.get("match_number")
    ):
        return None, "match_number_conflict"
    ids = record.get("volleystation_ids") or []
    if ids and ids != [str(match["id"])]:
        return None, "id_conflict"
    return match, None


def captured(folder):
    for meta in json.loads((folder / "capture.json").read_text()):
        raw = (folder / (meta["name"] + ".html")).read_bytes()
        if meta["status"] != 200 or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            raise ValueError("Niepoprawny dokument lub skrót")
        yield meta, BeautifulSoup(raw, "html.parser")


def run(root, captures, output):
    second = json.loads((root / "data/2liga.json").read_text())
    third = json.loads((root / "data/pomorska3liga.json").read_text())
    second_matches = [m for g in second["groups"] for m in g["matches"]]
    report = {
        "checked_at": now(),
        "scope": "Read-only venue audit; candidate catalog only, production feeds unchanged",
        "second": [],
        "third": [],
        "errors": [],
    }

    def inspect(record, matches, meta, league, aliases=None):
        match, error = match_record(record, matches, aliases=aliases)
        item = {
            **record,
            "source_url": meta["url"],
            "captured_at": meta["captured_at"],
            "sha256": meta["sha256"],
        }
        if error:
            report["errors"].append({**item, "error": error})
            return
        item.update(
            match_id=match["id"],
            feed_source_url=match["source_url"],
            feed_time=match.get("time"),
            time_conflict=bool(
                record.get("time") and record["time"] != match.get("time")
            ),
        )
        item["aliases_used"] = {
            side: {"source": record[side], "feed": match[side]}
            for side in ("home", "away")
            if name_key(record[side]) != name_key(match[side])
        }
        report[league].append(item)

    for meta, soup in captured(captures / "pzps-all"):
        if meta["name"] == "fixtures":
            continue
        record = pzps_record(soup)
        # Separate reader checks all rendered words in the labelled row, so
        # splitting name/address cannot silently discard a second venue.
        text_rows = [
            r.get_text(" ", strip=True) for r in soup.select('[role="main"] .row')
        ]
        original = [
            " ".join(t.removeprefix("Mecz rozgrywany w").split())
            for t in text_rows
            if t.startswith("Mecz rozgrywany w")
        ]
        emitted = " ".join((record["venue"] or {}).get("source_text", "").split())
        if original != [emitted]:
            raise ValueError("Odczyt hali nie odpowiada tekstowi strony PZPS")
        inspect(record, second_matches, meta, "second")
    fresh_clocks = {}
    for meta, soup in captured(captures / "third-check"):
        if meta["name"] == "arbitergo":
            for record in arbitergo_records(soup):
                inspect(record, third["matches"], meta, "third", POMORSKA_ALIASES)
        else:
            header = soup.select_one(".details.date")
            text = header.get_text(" ", strip=True) if header else ""
            clock = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
            fresh_clocks[meta["name"]] = {
                "source_url": meta["url"],
                "captured_at": meta["captured_at"],
                "sha256": meta["sha256"],
                "header_text": text,
                "time": clock[0].zfill(5) if clock else None,
            }
    for record in report["third"]:
        record["fresh_volleystation"] = fresh_clocks.get(record["match_id"])
    for league, total in [
        ("second", len(second_matches)),
        ("third", len(third["matches"])),
    ]:
        records = report[league]
        if len({r["match_id"] for r in records}) != len(records):
            raise ValueError("Zduplikowane dopasowanie meczu")
        report[league + "_summary"] = {
            "feed_matches": total,
            "matched_source_records": len(records),
            "with_location": sum(bool(r["venue"]) for r in records),
            "with_hall_name": sum(
                bool((r["venue"] or {}).get("name")) for r in records
            ),
            "with_address": sum(
                bool((r["venue"] or {}).get("address")) for r in records
            ),
            "with_hall_and_address": sum(
                bool((r["venue"] or {}).get("name"))
                and bool((r["venue"] or {}).get("address"))
                for r in records
            ),
            "with_cross_source_match_id": sum(
                bool(r.get("volleystation_ids")) for r in records
            ),
            "city_only": sum(
                bool((r["venue"] or {}).get("city"))
                and not (r["venue"] or {}).get("name")
                and not (r["venue"] or {}).get("address")
                for r in records
            ),
            "with_alternatives": sum(
                bool((r["venue"] or {}).get("alternatives_published")) for r in records
            ),
            "clock_conflicts": sum(r["time_conflict"] for r in records),
            "by_group": dict(
                Counter(r.get("group", "Pomorska III liga") for r in records)
            ),
        }
    report["complete_second_capture"] = (
        len(report["second"]) == len(second_matches) and not report["errors"]
    )
    atomic_json(output, report)
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k.endswith("_summary") or k == "complete_second_capture"
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(Path(__file__).resolve().parents[1], args.captures, args.output)
    return 0 if report["complete_second_capture"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
