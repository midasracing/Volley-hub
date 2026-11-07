"""Source-derived regression cases found by the II/III liga parity audit."""

import unittest

from bs4 import BeautifulSoup

from local_scraper.feed import live_sets
from local_scraper.runner import arguments
from local_scraper.schema import (
    MATCH_FIELDS,
    broadcast_urls,
    card_metadata,
    normalize,
    team_metadata,
)
from scripts import update_pomorska3liga as source


class ParityTests(unittest.TestCase):
    def test_live_label_does_not_drop_a_zero_zero_match(self):
        soup = BeautifulSoup(
            '<h2>7 listopada 2026</h2><a href="/matches/2560302/">'
            "Na żywo Runda: 1 Nr 45 Gospodarz 0:0 Gość</a>",
            "html.parser",
        )
        matches = source.parse_matches(soup, source.SCHEDULE_URL)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["status"], "live")
        self.assertEqual((matches[0]["home_sets"], matches[0]["away_sets"]), (0, 0))

    def test_tv_label_alone_does_not_start_a_match(self):
        soup = BeautifulSoup(
            '<h2>7 listopada 2026</h2><a href="/matches/2560302/">'
            "TV Runda: 1 Nr 45 Gospodarz 0:0 Gość</a>",
            "html.parser",
        )
        self.assertEqual(
            source.parse_matches(soup, source.SCHEDULE_URL)[0]["status"], "scheduled"
        )

    def test_broadcast_uses_match_player_and_discards_embed_tracking(self):
        soup = BeautifulSoup(
            '<a href="https://www.youtube.com/watch?v=38BPqJpf0HU">Klub</a>'
            '<iframe src="https://www.youtube.com/embed/38BPqJpf0HU"></iframe>'
            '<div class="video-container">'
            '<iframe src="https://www.youtube.com/embed/nDOImTNf7_o?si=tracking"></iframe>'
            '<iframe src="//www.youtube-nocookie.com/embed/nDOImTNf7_o"></iframe>'
            '<iframe src="https://www.youtube.com.evil.test/embed/38BPqJpf0HU"></iframe>'
            '<iframe src="javascript:alert(1)"></iframe>'
            '<iframe src="/embed/38BPqJpf0HU"></iframe>'
            '<iframe src="https://www.youtube.com/embed/too-short"></iframe>'
            "</div>",
            "html.parser",
        )
        self.assertEqual(
            broadcast_urls(soup), ["https://www.youtube.com/watch?v=nDOImTNf7_o"]
        )

    def test_nonfinal_score_is_live_not_finished(self):
        soup = BeautifulSoup(
            '<h2>7 listopada 2026</h2><a href="/matches/123/">Runda: 5 Nr 24 Gospodarz 1:1 Gość</a>',
            "html.parser",
        )
        match = source.parse_matches(soup, source.SCHEDULE_URL)[0]
        self.assertEqual(match["status"], "live")

    def test_active_tied_points_are_kept_separate_from_completed_sets(self):
        soup = BeautifulSoup(
            "<p>Godzina meczu: 18:00</p>"
            + "".join(
                f'<div class="team-points-row {side}">'
                + "".join(f'<i class="set-points">{n}</i>' for n in values)
                + f'<b class="match-points">{score}</b></div>'
                for side, values, score in [
                    ("home", [25, 20, 25, 12], 2),
                    ("away", [17, 25, 20, 12], 1),
                ]
            ),
            "html.parser",
        )
        detail = source.parse_match_detail(soup)
        self.assertEqual(detail["set_scores"], ["25:17", "20:25", "25:20"])
        self.assertEqual(detail["current_points"], "12:12")
        self.assertEqual(len(live_sets(detail)), 3)

    def test_hidden_tv_placeholder_is_not_a_broadcast(self):
        soup = BeautifulSoup(
            '<a href="/matches/123/"><div class="stage"><span class="live-text">TV</span></div></a>',
            "html.parser",
        )
        self.assertEqual(
            next(iter(card_metadata(soup, source.BASE).values()))["broadcast"], []
        )

    def test_visible_tv_marker_is_preserved(self):
        soup = BeautifulSoup(
            '<a href="/matches/123/"><div class="stage live"><span class="live-text">TV</span></div></a>',
            "html.parser",
        )
        self.assertEqual(
            next(iter(card_metadata(soup, source.BASE).values()))["broadcast"], ["TV"]
        )

    def test_team_profile_id_is_not_the_badge_asset_id(self):
        soup = BeautifulSoup(
            '<a href="/teams/2103916-STOCZ/"><img alt="GKS Stoczniowiec Logo" src="https://assets.volleystation.com/website/teams/2122546/badge.jpeg"></a>',
            "html.parser",
        )
        team = next(iter(team_metadata(soup, source.BASE).values()))
        self.assertEqual(team["id"], "2103916")
        self.assertEqual(team["badge_id"], "2122546")

    def test_normalized_fields_match_the_tauron_contract_without_inventing_venue(self):
        data = {
            "league": "second",
            "competition": "II Liga Mężczyzn",
            "phase": "Grupa 1",
            "teams": [
                {"name": "A", "logo": "https://example.org/a.png"},
                {"name": "B", "logo": "https://example.org/b.png"},
            ],
            "matches": [
                {
                    "id": "legacy",
                    "date": "07.11.2026",
                    "time": "18:00",
                    "round": 1,
                    "match_number": 1,
                    "home": "A",
                    "away": "B",
                    "home_sets": 3,
                    "away_sets": 0,
                    "set_scores": ["25:20", "25:21", "25:22"],
                    "status": "finished",
                    "source_url": "https://2ligamezczyzn.volleystation.com/pl/matches/123/",
                }
            ],
        }
        match = normalize(data)["matches"][0]
        self.assertFalse(MATCH_FIELDS - set(match))
        self.assertEqual(match["id"], "123")
        self.assertEqual(match["date_iso"], "2026-11-07")
        self.assertEqual(match["home_points"], 75)
        self.assertEqual(match["away_points"], 63)
        self.assertEqual(match["set_points"][0], {"home": 25, "away": 20})
        self.assertIsNone(match["venue"])
        self.assertIsNone(match["term_number"])

    def test_second_league_has_its_own_output(self):
        args = arguments(["--league", "second"])
        self.assertEqual(args.output.name, "2liga.json")


if __name__ == "__main__":
    unittest.main()
