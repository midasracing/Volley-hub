"""PLS standings parser and snapshot-integrity regression tests (offline)."""
import json
from pathlib import Path
import unittest

from bs4 import BeautifulSoup

from scripts.refresh_tauron import parse_table, rank_standings, validate_standings


def standings_row(rank, team, points, played, wins, losses,
                  sets_for, sets_against, points_for, points_against):
    numbers = (rank, points, played, wins, losses, sets_for, sets_against,
               points_for, points_against)
    return (
        f"<tr><td>{numbers[0]}</td><td><a href='/teams/id/1'>{team}</a></td>"
        + "".join(f"<td>{number}</td>" for number in numbers[1:]) + "</tr>"
    )


class PlsTableTests(unittest.TestCase):
    def test_historical_rank_is_not_a_current_position(self):
        # PLS publishes historic round snapshots on a single HTML page.
        # A team's latest totals can retain its rank in an older snapshot.
        page = (
            "<table>"
            + standings_row(1, "Bogdanka", 9, 3, 3, 0, 9, 1, 225, 160)
            + standings_row(1, "Bogdanka", 12, 4, 4, 0, 12, 1, 327, 282)
            + standings_row(2, "Resovia", 7, 3, 2, 1, 8, 4, 276, 240)
            + standings_row(3, "Warta", 9, 4, 3, 1, 9, 5, 346, 304)
            + standings_row(2, "Warta", 12, 5, 4, 1, 12, 6, 439, 389)
            + "</table>"
        )
        aliases = [(name, name) for name in ("Bogdanka", "Resovia", "Warta")]
        rows = parse_table(BeautifulSoup(page, "html.parser"), aliases)
        self.assertEqual([(row["rank"], row["team"]) for row in rows],
                         [(1, "Bogdanka"), (2, "Warta"), (3, "Resovia")])
        self.assertEqual(rows[1]["points"], 12)

    def test_source_changes_points_without_new_game(self):
        page = (
            "<table>"
            + standings_row(1, "Lublin", 7, 3, 2, 1, 8, 5, 277, 265)
            + standings_row(1, "Lublin", 8, 3, 2, 1, 8, 5, 277, 265)
            + "</table>"
        )
        result = parse_table(BeautifulSoup(page, "html.parser"), [("Lublin", "Lublin")])
        self.assertEqual(result[0]["points"], 8)

    def test_pls_tiebreak_order_uses_wins_then_sets_then_small_points(self):
        base = {
            "rank": 9, "played": 5, "points": 10, "wins": 3, "losses": 2,
            "sets_for": 10, "sets_against": 7,
            "points_for": 200, "points_against": 200,
        }
        rows = [
            dict(base, team="Small ratio", points_for=220),
            dict(base, team="More wins", wins=4, losses=1),
            dict(base, team="Set ratio", sets_for=11),
            dict(base, team="Weakest"),
        ]
        ranked = rank_standings(rows)
        self.assertEqual([r["team"] for r in ranked],
                         ["More wins", "Set ratio", "Small ratio", "Weakest"])
        self.assertEqual([r["rank"] for r in ranked], [1, 2, 3, 4])

    def test_unrelated_table_or_partial_source_cannot_invent_a_club(self):
        page = "<table>" + standings_row(1, "Unrelated team", 7, 3, 2, 1, 8, 4, 250, 230) + "</table>"
        parsed = parse_table(BeautifulSoup(page, "html.parser"), [("Our team", "Our team")])
        self.assertEqual(parsed, [])

    def test_actual_saved_results_agree_with_current_official_totals(self):
        # Offline integration check of all finished matches in both leagues.
        for filename, count in (("tauron", 14), ("tauron1liga", 16)):
            with self.subTest(league=filename):
                feed = json.loads((Path("data") / (filename + ".json")).read_text(encoding="utf-8"))
                table = rank_standings(feed["table"], feed["matches"])
                self.assertTrue(validate_standings(table, feed["matches"], count))
                self.assertEqual(len({row["rank"] for row in table}), count)

    def test_inconsistent_totals_or_duplicate_ranks_fail_closed(self):
        feed = json.loads(Path("data/tauron.json").read_text(encoding="utf-8"))
        table = rank_standings(feed["table"], feed["matches"])
        table[0]["points"] += 1
        with self.assertRaises(RuntimeError):
            validate_standings(table, feed["matches"], 14)
        table = rank_standings(feed["table"], feed["matches"])
        table[1]["rank"] = 1
        with self.assertRaises(RuntimeError):
            validate_standings(table, feed["matches"], 14)


if __name__ == "__main__":
    unittest.main()
