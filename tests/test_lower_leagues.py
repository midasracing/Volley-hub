"""Offline regression checks for II Liga standings and lower-league audits."""

import unittest
from unittest.mock import patch

from scripts.audit_lower_leagues import audit_group
from scripts.update_2liga import main as update_second
from scripts.update_pomorska3liga import main as update_third


class LowerLeagueRegressionTests(unittest.TestCase):
    def test_third_league_command_delegates_to_the_default_local_importer(self):
        with patch("local_scraper.runner.main", return_value=0) as run:
            self.assertEqual(update_third(["--status"]), 0)
        run.assert_called_once_with(["--status"])

    def test_legacy_command_delegates_to_the_local_volleystation_importer(self):
        with (
            patch("sys.argv", ["update_2liga.py", "--status"]),
            patch("local_scraper.runner.main", return_value=0) as run,
        ):
            self.assertEqual(update_second(), 0)
        run.assert_called_once_with(["--league", "second", "--status"])

    def test_audit_reports_missing_finished_set_points_without_inventing_them(self):
        group = {
            "name": "Pomorska III Liga",
            "teams": [
                {"name": "A", "logo": "badge-a"},
                {"name": "B", "logo": "badge-b"},
            ],
            "table": [
                {
                    "team": "A",
                    "played": 1,
                    "wins": 1,
                    "losses": 0,
                    "points": 2,
                    "sets_for": 3,
                    "sets_against": 2,
                },
                {
                    "team": "B",
                    "played": 1,
                    "wins": 0,
                    "losses": 1,
                    "points": 1,
                    "sets_for": 2,
                    "sets_against": 3,
                },
            ],
            "matches": [
                {
                    "date": "04.10.2026",
                    "time": None,
                    "home": "A",
                    "away": "B",
                    "status": "finished",
                    "home_sets": 3,
                    "away_sets": 2,
                    "set_scores": [],
                }
            ],
        }
        summary = audit_group(group)
        self.assertEqual(summary["finished"], 1)
        self.assertEqual(summary["finished_with_full_set_scores"], 0)
        self.assertEqual(len(summary["finished_without_full_set_scores"]), 1)
        self.assertEqual(summary["table_discrepancies"], 0)


if __name__ == "__main__":
    unittest.main()
