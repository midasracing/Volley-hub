"""Real source layouts and cases that must not attach a hall to the wrong match."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from local_scraper.capture_venues import capture
from local_scraper.venue_audit import (
    POMORSKA_ALIASES,
    arbitergo_records,
    match_record,
    pzps_record,
)


def pzps(venue, league="II liga mężczyzn"):
    return BeautifulSoup(
        '<div role="main"><h5>Mecz numer 4</h5>'
        "<h5>Rozgrywany dnia: 2026-10-03</h5>"
        f"<h5>{league}</h5><h5>Grupa 1</h5>"
        '<div class="row"><div class="col-xs-5 text-center"><h4>Fort Tarnowo Podgórne</h4></div>'
        '<div class="col-xs-5 text-center"><h4>KRISHOME Września</h4></div></div>'
        '<div class="row"><div><h5>Mecz rozgrywany w</h5></div>'
        f"<div><h5>{venue}</h5></div></div>"
        '<div class="row"><h5>godzina meczu:</h5><h5>14:00</h5></div>'
        '<iframe src="https://widgets.volleystation.com/court/2560066?side_force=home"></iframe></div>',
        "html.parser",
    )


def arbiter(
    category="III Liga Mężczyzn",
    home="GKS Stoczniowiec Gdańsk",
    away="KATS Alpat Gdynia",
):
    return BeautifulSoup(
        '<div class="delegation-list-detail">'
        '<div class="delegation-date-number">07-11-2026 12:00'
        '<span class="delegation-date-number__number">434/Hala 2026/2027</span></div>'
        f'<span class="delegation-competition__name">{category}</span>'
        '<div class="delegation-matches-list"><ul><li>'
        f"<span>sports_volleyball</span><span>{home} - {away}</span></li></ul></div>"
        '<div class="delegation-competition__address"><span>location_on</span>'
        'Gdańsk, Reja 25<span class="delegation-competition__hall">ZSE</span></div></div>',
        "html.parser",
    )


class VenueTests(unittest.TestCase):
    def test_capture_stops_on_rate_limit_and_preserves_completed_manifest(self):
        responses = [
            (200, "User-agent: *\nAllow: /"),
            (200, '<a href="/system/mecz/1/">1</a><a href="/system/mecz/2/">2</a>'),
            (429, "rate limited"),
        ]
        session = Mock()
        session.headers = {}
        session.get.side_effect = [
            SimpleNamespace(
                status_code=status,
                text=text,
                content=text.encode(),
                headers={"Retry-After": "300"},
            )
            for status, text in responses
        ]
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch(
                "local_scraper.capture_venues.requests.Session", return_value=session
            ),
            patch("local_scraper.capture_venues.time.sleep"),
        ):
            folder = Path(temporary)
            with self.assertRaises(RuntimeError):
                capture(folder, folder / "unused.json")
            self.assertEqual(session.get.call_count, 3)
            self.assertTrue((folder / "pzps-all/fixtures.html").exists())
            self.assertFalse((folder / "pzps-all/match-1.html").exists())
            self.assertTrue((folder / "pzps-all/error.json").exists())
            session.close.assert_called_once()

    def test_pzps_extracts_labelled_hall_and_address(self):
        record = pzps_record(pzps("ul. Szkolna 7, 62-080 Lusówko<br>Hala OSiR<br>"))
        self.assertEqual(record["venue"]["name"], "Hala OSiR")
        self.assertEqual(record["venue"]["address"], "ul. Szkolna 7, 62-080 Lusówko")
        self.assertEqual(record["volleystation_ids"], ["2560066"])

    def test_city_alone_is_never_promoted_to_hall_or_street(self):
        venue = pzps_record(pzps("Bydgoszcz"))["venue"]
        self.assertEqual(venue["city"], "Bydgoszcz")
        self.assertIsNone(venue["name"])
        self.assertIsNone(venue["address"])

    def test_address_alone_has_no_invented_hall_name(self):
        venue = pzps_record(pzps("ul. Brzozowa 30, 84-240 Reda"))["venue"]
        self.assertIsNone(venue["name"])
        self.assertEqual(venue["address"], "ul. Brzozowa 30, 84-240 Reda")

    def test_alternative_halls_remain_explicit_in_source_text(self):
        venue = pzps_record(
            pzps(
                "Wojska Polskiego 1, Września<br>HS ZSP<br>; Hala dodatkowa: HS SSP nr 3"
            )
        )["venue"]
        self.assertTrue(venue["alternatives_published"])
        self.assertIn("Hala dodatkowa", venue["source_text"])

    def test_empty_location_is_missing(self):
        self.assertIsNone(pzps_record(pzps("<br>"))["venue"])

    def test_other_competition_is_rejected(self):
        with self.assertRaises(ValueError):
            pzps_record(pzps("Hala", "II liga kobiet"))

    def test_matching_requires_direction_date_group_number_and_consistent_id(self):
        record = pzps_record(pzps("Bydgoszcz"))
        match = {**record, "id": "2560066"}
        self.assertIsNotNone(match_record(record, [match])[0])
        for change in [
            {"home": record["away"], "away": record["home"]},
            {"date": "04.10.2026"},
            {"group": "Grupa 2"},
            {"match_number": "5"},
            {"id": "2560067"},
        ]:
            self.assertIsNone(match_record(record, [{**match, **change}])[0])
        self.assertEqual(match_record(record, [match, match])[1], "ambiguous_fixture")

    def test_arbitergo_extracts_city_street_hall_without_icon_text(self):
        record = arbitergo_records(arbiter())[0]
        self.assertEqual(record["date"], "07.11.2026")
        self.assertEqual(record["time"], "12:00")
        self.assertEqual(record["venue"]["name"], "ZSE")
        self.assertEqual(record["venue"]["city"], "Gdańsk")
        self.assertEqual(record["venue"]["address"], "Reja 25")
        self.assertEqual(record["source_record_id"], "434/Hala 2026/2027")

    def test_arbitergo_cannot_use_the_same_club_in_another_league(self):
        self.assertEqual(arbitergo_records(arbiter("II Liga Mężczyzn")), [])

    def test_aliases_are_explicit_and_leave_the_clock_discrepancy_visible(self):
        record = arbitergo_records(arbiter())[0]
        match = {
            "id": "2579669",
            "date": "07.11.2026",
            "time": "18:00",
            "home": "GKS Stoczniowiec Gdańsk",
            "away": "KATS ALPAT CYMMAT GDYNIA",
        }
        self.assertIsNone(match_record(record, [match])[0])
        found, error = match_record(record, [match], aliases=POMORSKA_ALIASES)
        self.assertIsNone(error)
        self.assertEqual(found["id"], "2579669")
        self.assertNotEqual(record["time"], found["time"])
        self.assertIsNone(
            match_record(
                {**record, "away": "KATS Alpat Gdynia II"},
                [match],
                aliases=POMORSKA_ALIASES,
            )[0]
        )


if __name__ == "__main__":
    unittest.main()
