import unittest
import importlib.util
from pathlib import Path
from bs4 import BeautifulSoup

path = Path(__file__).resolve().parents[1] / "scripts" / "refresh_tauron.py"
spec = importlib.util.spec_from_file_location("refresh_tauron", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class PLSParserTests(unittest.TestCase):
    def test_official_names_and_set_points(self):
        soup = BeautifulSoup("""
        <article><span>5 listopada 2026, 18:00</span>
        <a href="/teams/id/24.html"><img src="/a.png" alt="Energa Indykpol AZS Olsztyn">Energa Indykpol AZS Olsztyn</a>
        3 1 25 18 25 19 18 25 25 22 0 0
        <a href="/teams/id/78.html"><img src="/b.png" alt="Energa Trefl Gdańsk">Energa Trefl Gdańsk</a>
        <a href="/games/action/show/id/123.html">Więcej</a></article>
        """, "html.parser")
        aliases = mod.build_aliases(mod.LEAGUES["men"], soup)
        matches = mod.parse_matches(soup, aliases)
        self.assertTrue(matches)
        match = matches[0]
        self.assertEqual(match["home"], "Energa Indykpol AZS Olsztyn")
        self.assertEqual(match["away"], "Energa Trefl Gdańsk")
        self.assertEqual(match["set_scores"], ["25:18", "25:19", "18:25", "25:22"])
        self.assertEqual(match["home_points"], 93)
        self.assertEqual(match["away_points"], 84)
        self.assertEqual(match["status"], "finished")
        logos = mod.extract_team_logos("https://www.tauronliga.pl", aliases, {}, soup)
        self.assertIn("24", [t.get("id") for t in logos])

    def test_game_details(self):
        soup = BeautifulSoup("""
        <h2>Transmisje</h2><div><img alt="TV Polsat Sport 1" src="/tv.png"></div>
        <h2>SZCZEGÓŁY</h2>
        <table><tr><td>Faza:</td><td>Zasadnicza</td></tr>
        <tr><td>Termin:</td><td>3</td></tr>
        <tr><td>Numer meczu:</td><td>017</td></tr></table>
        <h2>Informacje o hali</h2>
        <table><tr><td>Nazwa:</td><td>Hala Urania</td></tr>
        <tr><td>Adres:</td><td>Piłsudskiego 44</td></tr>
        <tr><td>Miasto:</td><td>Olsztyn</td></tr></table>
        <h2>POWIĄZANE WIADOMOŚCI</h2>
        """, "html.parser")
        data = mod.detail_metadata(soup)
        self.assertEqual(data["term_number"], 3)
        self.assertEqual(data["venue"]["name"], "Hala Urania")
        self.assertEqual(data["broadcast"], ["TV Polsat Sport 1"])

    def test_detail_set_points_match_validated_result(self):
        soup = BeautifulSoup("""
        <div class="game-result-box">
        <div class="game-result"><span class="game-score">3</span> :
        <span class="game-score">1</span></div>
        <div>04.11.2026, 20:30</div>
        <p>Małe punkty: 25 27 25 20 26 24 26 24 0 0</p>
        <p>Złoty set:</p></div>
        """, "html.parser")
        match = {"home_sets": 3, "away_sets": 1, "status": "finished"}
        points, active = mod.read_match_detail(soup, match)
        self.assertEqual(points, ["25:27", "25:20", "26:24", "26:24"])
        self.assertIsNone(active)
        bad = {**match, "home_sets": 0, "away_sets": 3}
        points, _ = mod.read_match_detail(soup, bad)
        self.assertIsNone(points)

if __name__ == "__main__":
    unittest.main()
