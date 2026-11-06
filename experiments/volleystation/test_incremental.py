import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

import scraper_incremental as scraper


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.old = {'id': 'same-id', 'date': '01.11.2026', 'home': 'A', 'away': 'B',
                    'status': 'finished', 'home_sets': 3, 'away_sets': 0,
                    'time': '18:00', 'set_scores': ['25:20', '25:22', '25:19']}
        self.current = {**self.old, 'time': None, 'set_scores': []}

    def reuse(self):
        return scraper.reuse_previous_details([self.current], {'matches': [self.old]},
                                              lambda score: score.startswith('25:'))

    def test_complete_unchanged_result_reuses_points_and_time(self):
        self.assertEqual(self.reuse(), 1)
        self.assertEqual(self.current['set_scores'], self.old['set_scores'])
        self.assertEqual(self.current['time'], '18:00')

    def test_changed_official_result_requires_refetch(self):
        self.current['away_sets'] = 1
        self.assertEqual(self.reuse(), 0)
        self.assertEqual(self.current['set_scores'], [])

    def test_inconsistent_set_winners_are_not_reused(self):
        self.old['set_scores'][-1] = '19:25'
        self.assertEqual(self.reuse(), 0)

    def test_incomplete_set_scores_are_not_reused(self):
        self.old['set_scores'].pop()
        self.assertEqual(self.reuse(), 0)

    def test_other_team_identity_is_not_reused(self):
        self.current['away'] = 'C'
        self.assertEqual(self.reuse(), 0)

    def test_known_logo_and_navigation_link_need_no_profile_requests(self):
        soup = BeautifulSoup('<a href="/pl/teams/">Drużyny</a><a href="/pl/teams/123/">A</a>', 'html.parser')
        with patch.object(scraper, 'fetch') as fetch:
            logos = scraper.parse_team_logos(soup, scraper.STANDINGS_URL, {'A': 'https://example.org/logo.png'})
        fetch.assert_not_called()
        self.assertEqual(logos['A'], 'https://example.org/logo.png')


if __name__ == '__main__':
    unittest.main()
