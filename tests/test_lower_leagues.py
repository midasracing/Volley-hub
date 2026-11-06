"""Offline regression checks for II Liga standings and lower-league audits."""
import unittest
from unittest.mock import patch

from scripts.update_2liga import parse_pzps_results
from scripts.audit_lower_leagues import audit_group

TABLE = """
<table>
<tr>
 <th>Lp.</th><th>Zespół</th><th>Mecze</th><th>Pkt</th><th>Zw.</th>
 <th>Por.</th><th>Sety +</th><th>Sety -</th>
 <th>Pkt +</th><th>Pkt -</th>
</tr>
<tr>
 <td>1</td><td>Fort Tarnowo Podgórne</td><td>4</td><td>10</td><td>3</td>
 <td>1</td><td>11</td><td>3</td><td>287</td><td>253</td>
</tr>
</table>
"""


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class LowerLeagueRegressionTests(unittest.TestCase):
    def test_pzps_table_uses_named_columns_instead_of_numeric_heuristics(self):
        matches = [
            {"date": "03.10.2026", "time": "17:00",
             "home": "Fort Tarnowo Podgórne", "away": "KRISHOME Września",
             "group": "Grupa 1", "status": "scheduled"},
        ]
        with patch("scripts.update_2liga.requests.get", return_value=FakeResponse(TABLE)):
            standings = parse_pzps_results(matches)
        self.assertEqual(standings["Grupa 1"], [{
            "rank": 1, "team": "Fort Tarnowo Podgórne",
            "played": 4, "wins": 3, "losses": 1, "points": 10,
            "sets_for": 11, "sets_against": 3,
            "points_for": 287, "points_against": 253,
        }])

    def test_audit_reports_missing_finished_set_points_without_inventing_them(self):
        group = {"name": "Pomorska III Liga",
                 "teams": [{"name": "A", "logo": "badge-a"},
                           {"name": "B", "logo": "badge-b"}],
                 "table": [{"team": "A", "played": 1, "wins": 1,
                            "losses": 0, "points": 2,
                            "sets_for": 3, "sets_against": 2},
                           {"team": "B", "played": 1, "wins": 0,
                            "losses": 1, "points": 1,
                            "sets_for": 2, "sets_against": 3}],
                 "matches": [{"date": "04.10.2026", "time": None,
                              "home": "A", "away": "B",
                              "status": "finished", "home_sets": 3,
                              "away_sets": 2, "set_scores": []}]}
        summary = audit_group(group)
        self.assertEqual(summary["finished"], 1)
        self.assertEqual(summary["finished_with_full_set_scores"], 0)
        self.assertEqual(len(summary["finished_without_full_set_scores"]), 1)
        self.assertEqual(summary["table_discrepancies"], 0)


if __name__ == "__main__":
    unittest.main()
