import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup

from diagnostics.probe_leagues import badge_logos, load_scraper


class DiagnosticTests(unittest.TestCase):
    def test_pzps_league_points_are_not_rally_points_or_wins(self):
        scraper = load_scraper("update_2liga.py")
        html = """<table><tr><th>Lp.</th><th>Zespół</th><th>Mecze</th><th>Pkt</th>
        <th>Zw.</th><th>Sety +</th><th>Sety -</th><th>pkt +</th><th>pkt -</th></tr>
        <tr><td>1</td><td>Fort Tarnowo Podgórne</td><td>4</td><td>10</td>
        <td>3</td><td>11</td><td>3</td><td>339</td><td>287</td></tr></table>"""
        fixture = {"home": "Fort Tarnowo Podgórne", "away": "B", "group": "Grupa 1"}
        response = SimpleNamespace(text=html, raise_for_status=lambda: None)
        with patch.object(scraper.requests, "get", return_value=response):
            rows = scraper.parse_pzps_results([fixture])["Grupa 1"]
        self.assertEqual(rows, [{
            "rank": 1, "team": "Fort Tarnowo Podgórne", "played": 4, "wins": 3,
            "losses": 1, "sets_for": 11, "sets_against": 3, "points_for": 339,
            "points_against": 287, "points": 10,
        }])

    def test_jpg_and_png_team_badges_are_distinct_from_league_branding(self):
        soup = BeautifulSoup('''
          <img alt="Logo Liga" src="https://assets.volleystation.com/website/branding/website/216/logo.png">
          <img alt="Team A Logo" src="https://assets.volleystation.com/website/teams/1/badge.jpg">
          <img alt="Team B Logo" src="https://assets.volleystation.com/website/teams/2/badge.png">
          <img alt="Team C Logo" src="https://example.com/teams/3/badge.png">
        ''', "html.parser")
        logos = badge_logos(soup, "https://pomorskie.volleystation.com/")
        self.assertEqual(set(logos), {"Team A", "Team B"})
        self.assertTrue(logos["Team A"].endswith("badge.jpg"))

    def test_copies_write_into_diagnostic_artifacts(self):
        for filename in ("update_2liga.py", "update_pomorska3liga.py"):
            with self.subTest(filename=filename):
                scraper = load_scraper(filename)
                self.assertIn("diagnostics/artifacts/standalone/", str(scraper.OUT))


if __name__ == "__main__":
    unittest.main()
