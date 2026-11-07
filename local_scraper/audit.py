"""Compare captured browser DOM with emitted records using an independent reader."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .feed import build_feed, validate_output
from .schema import MATCH_FIELDS, name_key
from .second import build_second
from .storage import atomic_json, now

MONTHS = dict(
    zip(
        (
            "stycznia",
            "lutego",
            "marca",
            "kwietnia",
            "maja",
            "czerwca",
            "lipca",
            "sierpnia",
            "września",
            "października",
            "listopada",
            "grudnia",
        ),
        range(1, 13),
    )
)


def read_cards(soup, url):
    rows = {}
    for card in soup.select('a.table-row[href*="/matches/"]'):
        home = card.select_one(".rival.home .name")
        away = card.select_one(".rival.away .name")
        if not home or not away:
            continue
        href = urljoin(url, card["href"])
        identifier = re.search(r"/matches/(\d+)/", href)[1]
        heading = next(
            (
                h.get_text(" ", strip=True)
                for h in card.find_all_previous(re.compile(r"^h[1-6]$"))
                if re.search(r"\d+\s+\w+\s+20\d{2}", h.get_text(" ", strip=True))
            ),
            None,
        )
        found = re.search(r"(\d+)\s+(\w+)\s+(20\d{2})", heading or "")
        if not found:
            raise ValueError("Nie znaleziono daty karty " + identifier)
        date = f"{int(found[1]):02d}.{MONTHS[found[2].casefold()]:02d}.{found[3]}"
        status = card.select_one(".status").get_text(" ", strip=True)
        result = {
            "id": identifier,
            "date": date,
            "home": home.get_text(" ", strip=True),
            "away": away.get_text(" ", strip=True),
            "source_url": href,
        }
        for side in ("home", "away"):
            image = card.select_one(".rival." + side + " img")
            logo = urljoin(url, image.get("src", "")) if image else None
            result[side + "_logo"] = logo
        result["round"] = int(
            re.search(r"\d+", card.select_one(".round").get_text())[0]
        )
        result["match_number"] = re.search(
            r"\d+", card.select_one(".match-number").get_text()
        )[0]
        stage = card.select_one(".stage")
        television = (
            card.select_one(".live-text")
            if stage and "live" in stage.get("class", [])
            else None
        )
        result["broadcast"] = (
            ["TV"] if television and television.get_text(strip=True) == "TV" else []
        )
        if re.fullmatch(r"[0-3]:[0-3]", status):
            result.update(
                status="finished"
                if max(int(status[0]), int(status[-1])) == 3
                else "live"
                if int(status[0]) + int(status[-1])
                or (
                    television
                    and television.get_text(strip=True).casefold() == "na żywo"
                )
                else "scheduled",
                home_sets=int(status[0]),
                away_sets=int(status[-1]),
            )
        else:
            result.update(status="scheduled", time=status)
        rows[identifier] = result
    return rows


def read_table(soup):
    result = {}
    for tr in soup.select("table tr"):
        cells = [
            c.get_text(" ", strip=True)
            for c in tr.find_all(["td", "th"], recursive=False)
        ]
        if len(cells) < 18 or not cells[0].isdigit():
            continue
        values = {
            "rank": int(cells[0]),
            "team": cells[1],
            "points": int(cells[2]),
            "played": int(cells[3]),
            "sets_for": int(cells[6]),
            "sets_against": int(cells[7]),
            "points_for": int(cells[8]),
            "points_against": int(cells[9]),
            "wins": sum(map(int, cells[12:15])),
            "losses": sum(map(int, cells[15:18])),
        }
        result[name_key(cells[1])] = values
    return result


class Captures:
    def __init__(self, root, engine):
        self.pages = {}
        self.soups = {}
        self.manifest = []
        folders = [*sorted(root.glob("details-*")), root / engine]
        for folder in folders:
            path = folder / "capture.json"
            if not path.exists():
                continue
            for item in json.loads(path.read_text()):
                if urlsplit(item["url"]).hostname not in {
                    "2ligamezczyzn.volleystation.com",
                    "pomorskie.volleystation.com",
                }:
                    continue
                if item.get("status") not in (200, 304) or item.get("challenge"):
                    raise ValueError("Niepoprawny dokument w audycie")
                p = folder / (item["name"] + ".html")
                html = p.read_text()
                if hashlib.sha256(html.encode()).hexdigest() != item["sha256"]:
                    raise ValueError("Niezgodny skrót źródła")
                self.pages[item["url"]] = html
                self.manifest.append(
                    {
                        **item,
                        "engine": item.get("engine", folder.name),
                        "capture_set": folder.name,
                        "captured_at": datetime.fromtimestamp(
                            p.stat().st_mtime, timezone.utc
                        ).isoformat(),
                    }
                )

    def fetch(self, url):
        if url not in self.pages:
            raise RuntimeError("Brak przechwyconej strony: " + url)
        if url not in self.soups:
            self.soups[url] = BeautifulSoup(self.pages[url], "html.parser")
        return self.soups[url]


def compare_group(group, store):
    expected = {}
    for url in [group["source"], group["results_source"]]:
        expected.update(read_cards(store.fetch(url), url))
    actual = {m["id"]: m for m in group["matches"]}
    teams_url = (
        "https://2ligamezczyzn.volleystation.com/pl/teams/"
        if group["league"] == "second"
        else group["source"].rsplit("/schedule/", 1)[0] + "/teams/"
    )
    identities = {}
    for anchor in store.fetch(teams_url).select("a.team-box[href]"):
        label = anchor.select_one(".text-title")
        identifier = re.search(r"/teams/(\d+)", anchor["href"])
        if label and identifier:
            identities[name_key(label.get_text(" ", strip=True))] = identifier[1]
    for row in expected.values():
        for side in ("home", "away"):
            row[side + "_team_id"] = identities.get(name_key(row[side]))
    differences = []
    live_changes = []
    for identifier, row in expected.items():
        if row["broadcast"]:
            # Independent DOM check, deliberately not the importer's helper.
            links = []
            for iframe in store.fetch(row["source_url"]).select(
                ".video-container iframe[src]"
            ):
                video = re.fullmatch(
                    r"https://www\.youtube\.com/embed/([\w-]{11})(?:\?[^\s]*)?",
                    iframe["src"],
                    flags=re.ASCII,
                )
                if video:
                    links.append("https://www.youtube.com/watch?v=" + video[1])
            row["broadcast_urls"] = list(dict.fromkeys(links))
        if row["status"] != "live" or row["source_url"] not in store.pages:
            continue
        detail = store.fetch(row["source_url"])
        h = detail.select_one(".team-points-row.home .match-points")
        a = detail.select_one(".team-points-row.away .match-points")
        if h and a:
            new = (int(h.get_text(strip=True)), int(a.get_text(strip=True)))
            if new != (row["home_sets"], row["away_sets"]):
                live_changes.append(
                    {
                        "id": identifier,
                        "list_score": [row["home_sets"], row["away_sets"]],
                        "detail_score": list(new),
                    }
                )
            row.update(
                home_sets=new[0],
                away_sets=new[1],
                status="finished" if max(new) == 3 else "live",
            )
    for identifier in sorted(set(expected) | set(actual)):
        if identifier not in expected or identifier not in actual:
            differences.append({"id": identifier, "field": "presence"})
            continue
        for key, value in expected[identifier].items():
            if actual[identifier].get(key) != value:
                differences.append(
                    {
                        "id": identifier,
                        "field": key,
                        "source": value,
                        "emitted": actual[identifier].get(key),
                    }
                )
    observed_table = read_table(store.fetch(group["standings_source"]))
    for row in group["table"]:
        expected_row = observed_table.get(name_key(row["team"]), {})
        for key, value in expected_row.items():
            if row.get(key) != value:
                differences.append(
                    {
                        "team": row["team"],
                        "field": key,
                        "source": value,
                        "emitted": row.get(key),
                    }
                )
    for match in group["matches"]:
        time_url = match.get("time_source", "") or ""
        if "/matches/" in time_url:
            expected_times = []
            for span in store.fetch(time_url).select("span"):
                stamp = re.fullmatch(
                    r"(\d+)\s+(\w+)\s+(20\d{2}),\s*(\d{1,2}:\d{2})",
                    span.get_text(" ", strip=True),
                )
                if (
                    stamp
                    and f"{int(stamp[1]):02d}.{MONTHS[stamp[2].casefold()]:02d}.{stamp[3]}"
                    == match["date"]
                ):
                    expected_times.append(stamp[4].zfill(5))
            if match["time"] not in expected_times:
                differences.append(
                    {
                        "id": match["id"],
                        "field": "detail_time",
                        "source": expected_times,
                        "emitted": match["time"],
                    }
                )
        if match["status"] not in ("finished", "live"):
            continue
        detail_url = match.get("set_scores_source")
        if detail_url and "/matches/" in detail_url:
            soup = store.fetch(detail_url)
            home = [
                int(n.get_text(strip=True))
                for n in soup.select(".team-points-row.home .set-points")
                if n.get_text(strip=True).isdigit()
            ]
            away = [
                int(n.get_text(strip=True))
                for n in soup.select(".team-points-row.away .set-points")
                if n.get_text(strip=True).isdigit()
            ]
            values = [f"{h}:{a}" for h, a in zip(home, away)]
            if match["status"] == "live":
                count = match["home_sets"] + match["away_sets"]
                active = values[count] if len(values) > count else None
                if match.get("current_points") != active:
                    differences.append(
                        {
                            "id": match["id"],
                            "field": "current_points",
                            "source": active,
                            "emitted": match.get("current_points"),
                        }
                    )
                values = values[:count]
            if values != match["set_scores"]:
                differences.append(
                    {
                        "id": match["id"],
                        "field": "set_scores",
                        "source": values,
                        "emitted": match["set_scores"],
                    }
                )
        points = [
            {"home": int(v.split(":")[0]), "away": int(v.split(":")[1])}
            for v in match["set_scores"]
        ]
        if (
            match.get("set_points") != points
            or match.get("home_points") != sum(p["home"] for p in points)
            or match.get("away_points") != sum(p["away"] for p in points)
        ):
            differences.append({"id": match["id"], "field": "normalized_set_points"})
    return {
        "name": group.get("name", "Pomorska III liga"),
        "matches": len(actual),
        "source_matches": len(expected),
        "finished": sum(m["status"] == "finished" for m in actual.values()),
        "with_time": sum(bool(m.get("time")) for m in actual.values()),
        "teams": len(group["teams"]),
        "table_rows": len(group["table"]),
        "missing_fields": sum(bool(MATCH_FIELDS - set(m)) for m in actual.values()),
        "venues": sum(bool(m.get("venue")) for m in actual.values()),
        "term_numbers": sum(m.get("term_number") is not None for m in actual.values()),
        "broadcast_markers": sum(bool(m.get("broadcast")) for m in actual.values()),
        "with_broadcast_urls": sum(
            bool(m.get("broadcast_urls")) for m in actual.values()
        ),
        "differences": differences,
        "live_changes_between_captures": live_changes,
    }


def run(root, output):
    output.mkdir(parents=True, exist_ok=True)
    report = {"checked_at": now(), "engines": {}}
    for engine in ["seleniumbase", "camoufox"]:
        store = Captures(root, engine)
        second, _ = build_second(store.fetch)
        third, _ = build_feed(store.fetch, refresh_details=True)
        validate_output(second)
        validate_output(third)
        for data in (second, third):
            for group in data.get("groups") or [data]:
                urls = {
                    group["source"],
                    group["results_source"],
                    group["standings_source"],
                }
                urls.update(
                    m.get(k)
                    for m in group["matches"]
                    for k in ("source_url", "set_scores_source", "time_source")
                )
                stamps = [r["captured_at"] for r in store.manifest if r["url"] in urls]
                group["source_observed_from"] = min(stamps)
                group["source_observed_to"] = max(stamps)
                group["updated_at"] = max(stamps)
                for match in group["matches"]:
                    checks = [
                        r["captured_at"]
                        for r in store.manifest
                        if r["url"] == match.get("set_scores_source")
                    ]
                    if checks:
                        match["details_checked_at"] = max(checks)
            if data.get("groups"):
                data["updated_at"] = max(g["updated_at"] for g in data["groups"])
        groups = [compare_group(g, store) for g in second["groups"]] + [
            compare_group(third, store)
        ]
        report["engines"][engine] = {
            "groups": groups,
            "captures": store.manifest,
            "differences": sum(len(g["differences"]) for g in groups),
        }
        atomic_json(output / (engine + "-2liga.json"), second)
        atomic_json(output / (engine + "-pomorska3liga.json"), third)

    def semantic(path):
        data = json.loads(path.read_text())
        groups = data.get("groups") or [data]
        return [
            {
                k: m.get(k)
                for k in (
                    "id",
                    "date",
                    "time",
                    "home",
                    "away",
                    "status",
                    "home_sets",
                    "away_sets",
                    "set_scores",
                    "home_team_id",
                    "away_team_id",
                    "home_logo",
                    "away_logo",
                    "broadcast_urls",
                )
            }
            for g in groups
            for m in g["matches"]
        ]

    report["engines_agree"] = {
        league: semantic(output / ("seleniumbase-" + league + ".json"))
        == semantic(output / ("camoufox-" + league + ".json"))
        for league in ["2liga", "pomorska3liga"]
    }
    report["passed"] = all(
        v["differences"] == 0 for v in report["engines"].values()
    ) and all(report["engines_agree"].values())
    atomic_json(output / "report.json", report)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "engines_agree": report["engines_agree"],
                "groups": report["engines"]["seleniumbase"]["groups"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--captures", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = run(args.captures, args.output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
