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

if __name__ == "__main__":
    unittest.main()
