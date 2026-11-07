"""Offline failures and real parser fixtures for the free local importer."""

import copy
import html
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup
from filelock import FileLock

from local_scraper import feed, runner
from local_scraper.engines import AccessError, Session
from local_scraper.storage import atomic_json, now, read_json
from scripts import update_pomorska3liga as source

SEED = (
    Path(__file__).resolve().parents[1]
    / "experiments/volleystation/seed-validated-20261106.json"
)


def seed():
    data = json.loads(SEED.read_text())
    data["updated_at"] = now()
    return data


def match_url(match):
    return f"https://pomorskie.volleystation.com/pl/matches/{match['round']}-{match['match_number']}/"


def pages(data):
    """Recreate the actual server-rendered markup from a verified source snapshot."""
    docs = {}
    months = {v: k for k, v in source.MONTHS.items()}
    for status, url in [
        ("scheduled", source.SCHEDULE_URL),
        ("finished", source.RESULTS_URL),
    ]:
        anchors = ["<title>Oficjalne rozgrywki</title>"]
        for match in data["matches"]:
            if match["status"] != status:
                continue
            day = datetime.strptime(match["date"], "%d.%m.%Y")
            score = (
                f"{match['home_sets']}:{match['away_sets']}"
                if status == "finished"
                else match["time"]
            )
            anchors.append(
                f'<h2>{day.day} {months[day.month]} {day.year}</h2><a href="{match_url(match)}">'
                f"Runda: {match['round']} Nr {match['match_number']} {html.escape(match['home'])} {score} "
                f"{html.escape(match['away'])}</a>"
            )
        docs[url] = "".join(anchors)
    rows = ["<title>Tabela</title><table>"]
    logos = {t["name"]: t["logo"] for t in data["teams"]}
    for row in data["table"]:
        result_counts = []
        for result in [(3, 0), (3, 1), (3, 2), (2, 3), (1, 3), (0, 3)]:
            result_counts.append(
                sum(
                    m["status"] == "finished"
                    and (
                        (
                            m["home"] == row["team"]
                            and (m["home_sets"], m["away_sets"]) == result
                        )
                        or (
                            m["away"] == row["team"]
                            and (m["away_sets"], m["home_sets"]) == result
                        )
                    )
                    for m in data["matches"]
                )
            )
        cells = [
            row["rank"],
            f'<img src="{logos[row["team"]]}">{html.escape(row["team"])}',
            row["points"],
            row["played"],
            "-",
            "-",
            row["sets_for"],
            row["sets_against"],
            row["points_for"],
            row["points_against"],
            "-",
            "-",
            *result_counts,
        ]
        rows.append(
            "<tr>" + "".join("<td>" + str(c) + "</td>" for c in cells) + "</tr>"
        )
    docs[source.STANDINGS_URL] = "".join(rows) + "</table>"
    for match in data["matches"]:
        if match["status"] != "finished":
            continue
        pairs = [score.split(":") for score in match["set_scores"]]
        docs[match_url(match)] = (
            f"<title>Mecz</title><p>Godzina meczu: {match['time']}</p>"
            + "".join(
                f'<div class="team-points-row {side}">'
                + "".join(f'<span class="set-points">{p[index]}</span>' for p in pairs)
                + "</div>"
                for side, index in [("home", 0), ("away", 1)]
            )
        )
    docs[source.BASE + "/teams/"] = "".join(
        f'<a class="team-box" href="/pl/teams/{index}/"><div class="text-title">{html.escape(t["name"])}</div>'
        f'<img alt="{html.escape(t["name"])} Logo" src="{t["logo"]}"></a>'
        for index, t in enumerate(data["teams"], 1)
    )
    return docs


class FeedTests(unittest.TestCase):
    def build(self, current, previous):
        docs = pages(current)
        self.calls = []

        def fetch(url):
            self.calls.append(url)
            return BeautifulSoup(docs[url], "html.parser")

        return feed.build_feed(fetch, previous)

    def test_identity_migration_then_warm_export_requires_three_documents(self):
        previous = seed()
        data, metrics = self.build(previous, previous)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(metrics["reused_details"], 17)
        self.assertEqual(metrics["finished"], 17)
        self.assertEqual(data["table"], previous["table"])
        _, metrics = self.build(previous, data)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(metrics["reused_details"], 17)

    def test_cold_import_recovers_every_finished_detail(self):
        current = seed()
        data, metrics = self.build(current, {})
        self.assertEqual(metrics["detail_requests"], 17)
        self.assertEqual(len(self.calls), 21)
        self.assertEqual(feed.validate_feed(data)["matches"], 72)

    def test_incomplete_saved_details_are_fetched(self):
        current = seed()
        previous = copy.deepcopy(current)
        match = next(m for m in previous["matches"] if m["status"] == "finished")
        match["set_scores"].pop()
        _, metrics = self.build(current, previous)
        self.assertEqual(metrics["detail_requests"], 1)
        self.assertIn(match_url(match), self.calls)

    def test_valid_details_survive_an_interrupted_cold_import(self):
        current = seed()
        docs = pages(current)
        remembered = []
        calls = []

        def interrupted(url):
            calls.append(url)
            if len(calls) > 6:
                raise RuntimeError("test interruption")
            return BeautifulSoup(docs[url], "html.parser")

        with self.assertRaisesRegex(RuntimeError, "interruption"):
            feed.build_feed(interrupted, on_detail=remembered.append)
        self.assertEqual(len(remembered), 2)
        data, metrics = feed.build_feed(
            lambda url: BeautifulSoup(docs[url], "html.parser"), detail_cache=remembered
        )
        self.assertEqual(metrics["reused_details"], 2)
        self.assertEqual(metrics["detail_requests"], 15)
        self.assertEqual(feed.validate_feed(data)["finished"], 17)

    def test_corrected_set_points_invalidate_cache_from_fresh_table(self):
        previous = seed()
        current = copy.deepcopy(previous)
        match = next(m for m in current["matches"] if m["status"] == "finished")
        a, b = map(int, match["set_scores"][0].split(":"))
        self.assertGreater(a, b)
        match["set_scores"][0] = f"{a}:{b - 1}"
        for row in current["table"]:
            if row["team"] == match["home"]:
                row["points_against"] -= 1
            if row["team"] == match["away"]:
                row["points_for"] -= 1
        data, metrics = self.build(current, previous)
        actual = next(m for m in data["matches"] if m["id"] == match["id"])
        self.assertEqual(actual["set_scores"], match["set_scores"])
        self.assertGreater(metrics["refetched_cached_details"], 0)

    def test_missing_fixture_is_rejected_even_when_more_than_sixty_remain(self):
        previous = seed()
        current = copy.deepcopy(previous)
        current["matches"].remove(
            next(m for m in current["matches"] if m["status"] == "scheduled")
        )
        with self.assertRaisesRegex(feed.InvalidFeed, "Zniknęły mecze"):
            self.build(current, previous)

    def test_inconsistent_table_is_not_published(self):
        current = seed()
        current["table"][0]["points"] += 1
        with self.assertRaisesRegex(feed.InvalidFeed, "Tabela nie zgadza"):
            self.build(current, {})

    def test_long_deuce_and_long_tiebreak_are_legal(self):
        soup = BeautifulSoup(
            "<p>Godzina meczu: 18:00</p>"
            + '<div class="team-points-row home"><i class="set-points">41</i></div>'
            + '<div class="team-points-row away"><i class="set-points">39</i></div>',
            "html.parser",
        )
        self.assertEqual(source.parse_match_detail(soup)["set_scores"], ["41:39"])
        match = {
            "id": "long",
            "home_sets": 3,
            "away_sets": 2,
            "set_scores": ["41:39", "23:25", "25:20", "24:26", "42:40"],
        }
        self.assertEqual(len(feed.completed_sets(match)), 5)

    def test_illegal_deuce_and_premature_fifteenth_point_are_rejected(self):
        for scores in [["26:20", "25:20", "25:20"], ["15:13", "25:20", "25:20"]]:
            with self.subTest(scores=scores), self.assertRaises(feed.InvalidFeed):
                feed.completed_sets(
                    {"home_sets": 3, "away_sets": 0, "set_scores": scores}
                )

    def test_same_overall_score_with_wrong_set_winners_is_rejected(self):
        with self.assertRaises(feed.InvalidFeed):
            feed.completed_sets(
                {
                    "home_sets": 3,
                    "away_sets": 0,
                    "set_scores": ["25:20", "20:25", "25:20"],
                }
            )


class TransportTests(unittest.TestCase):
    def test_challenge_with_http_200_stops_the_session(self):
        browser = SimpleNamespace(
            get=lambda url: {
                "status": 200,
                "headers": {},
                "html": "<title>Cierpliwości…</title>",
            }
        )
        with patch.object(browser, "get", wraps=browser.get) as get:
            session = Session(browser, lambda e: None, interval=0)
            for _ in range(2):
                with self.assertRaises(AccessError):
                    session.fetch(source.SCHEDULE_URL)
            self.assertEqual(get.call_count, 1)

    def test_rate_limit_records_retry_after(self):
        browser = SimpleNamespace(
            get=lambda url: {
                "status": 429,
                "headers": {"Retry-After": "7200"},
                "html": "busy",
            }
        )
        session = Session(browser, lambda e: None, interval=0)
        with self.assertRaises(AccessError) as error:
            session.fetch(source.SCHEDULE_URL)
        self.assertEqual(error.exception.retry_after, 7200)
        self.assertEqual(session.retry_after, 7200)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = seed()
        self.args = runner.arguments(
            [
                "--output",
                str(self.root / "feed.json"),
                "--state-dir",
                str(self.root / "state"),
            ]
        )
        self.args.state_dir.mkdir()
        atomic_json(self.args.output, self.data)
        self.original = self.args.output.read_bytes()
        self.engines = []

    def execute(self, engine, previous, candidate, report, events, args):
        self.engines.append(engine)
        if engine == "seleniumbase":
            return {"engine": engine, "ok": False, "error": "test refusal"}
        data = copy.deepcopy(self.data)
        data["updated_at"] = now()
        atomic_json(candidate, data)
        return {"engine": engine, "ok": True}

    def test_complete_camoufox_candidate_is_used_after_primary_failure(self):
        self.assertTrue(
            runner.cycle(self.args, execute=self.execute, sleep=lambda _: None)
        )
        self.assertEqual(self.engines, ["seleniumbase", "camoufox"])
        self.assertEqual(
            read_json(self.args.state_dir / "status.json")["last_success_engine"],
            "camoufox",
        )
        feed.validate_feed(read_json(self.args.output))

    def test_invalid_success_candidates_preserve_exact_previous_bytes(self):
        def invalid(engine, previous, candidate, *args):
            atomic_json(candidate, {"matches": []})
            return {"engine": engine, "ok": True}

        self.assertFalse(runner.cycle(self.args, execute=invalid, sleep=lambda _: None))
        self.assertEqual(self.args.output.read_bytes(), self.original)
        state = read_json(self.args.state_dir / "status.json")
        self.assertEqual(state["status"], "error")
        self.assertEqual(len(state["attempts"]), 2)

    def test_primary_success_does_not_launch_fallback(self):
        def primary(engine, previous, candidate, *args):
            self.engines.append(engine)
            data = copy.deepcopy(self.data)
            data["updated_at"] = now()
            atomic_json(candidate, data)
            return {"engine": engine, "ok": True}

        self.assertTrue(runner.cycle(self.args, execute=primary))
        self.assertEqual(self.engines, ["seleniumbase"])

    def test_rate_limit_prevents_immediate_fallback_and_next_invocation(self):
        calls = []

        def limited(engine, *args):
            calls.append(engine)
            return {"engine": engine, "ok": False, "error": "429", "retry_after": 7200}

        self.assertFalse(runner.cycle(self.args, execute=limited))
        self.assertFalse(runner.cycle(self.args, execute=limited))
        self.assertEqual(calls, ["seleniumbase"])
        self.assertEqual(self.args.output.read_bytes(), self.original)

    def test_stale_feed_is_reported_without_changing_it(self):
        data = seed()
        data["updated_at"] = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()
        atomic_json(self.args.output, data)
        original = self.args.output.read_bytes()
        self.assertEqual(
            runner.freshness(self.args.output, 1800)["feed_status"], "stale"
        )
        self.assertEqual(self.args.output.read_bytes(), original)

    def test_validated_feed_reaches_the_local_web_app(self):
        self.args.public_output = self.root / "public" / "data" / "pomorska3liga.json"
        self.assertTrue(
            runner.cycle(self.args, execute=self.execute, sleep=lambda _: None)
        )
        self.assertEqual(
            self.args.output.read_bytes(), self.args.public_output.read_bytes()
        )

    def test_mirror_disk_error_does_not_launch_another_browser(self):
        occupied = self.root / "occupied"
        occupied.write_text("not a directory")
        self.args.public_output = occupied / "feed.json"

        def primary(engine, previous, candidate, *args):
            self.engines.append(engine)
            data = copy.deepcopy(self.data)
            data["updated_at"] = now()
            atomic_json(candidate, data)
            return {"engine": engine, "ok": True}

        self.assertFalse(runner.cycle(self.args, execute=primary))
        self.assertEqual(self.engines, ["seleniumbase"])
        feed.validate_feed(read_json(self.args.output))
        self.assertEqual(
            read_json(self.args.state_dir / "status.json")["status"], "error"
        )

    def test_concurrent_invocation_is_rejected_before_browser_start(self):
        with FileLock(str(self.args.output) + ".local-scraper.lock"):
            self.assertEqual(
                runner.main(
                    [
                        "--output",
                        str(self.args.output),
                        "--state-dir",
                        str(self.args.state_dir),
                    ]
                ),
                2,
            )

    def test_timeout_terminates_worker_and_descendant(self):
        import psutil

        real_popen = subprocess.Popen
        pid_file = self.root / "child-pid"
        code = (
            "import subprocess,sys,time,pathlib; "
            'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(600)"]); '
            f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid)); time.sleep(600)"
        )

        def start(*args, **kwargs):
            return real_popen([sys.executable, "-c", code], **kwargs)

        self.args.timeout = 0.8
        with patch("local_scraper.runner.subprocess.Popen", side_effect=start):
            result = runner.run_worker(
                "seleniumbase",
                self.args.output,
                self.root / "candidate.json",
                self.root / "report.json",
                self.root / "events.jsonl",
                self.args,
            )
        self.assertFalse(result["ok"])
        self.assertIn("limit", result["error"])
        pid = int(pid_file.read_text())
        try:
            self.assertEqual(psutil.Process(pid).status(), psutil.STATUS_ZOMBIE)
        except psutil.NoSuchProcess:
            pass


if __name__ == "__main__":
    unittest.main()
