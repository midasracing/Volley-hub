"""Offline regression tests for verified Italian and Japanese league layouts."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.update_international import (
    build_feed, japan_months, japanese_time, parse_italian_heading,
    parse_italy, parse_japan_day, parse_japan_month_days, write_feed,
)

ITALY = """
<table id="GareGiornata">
  <tr class="GiornataA"><td colspan="7">4ª Giornata Andata - Mercoledí 4 Novembre 2026 Ore 20:30</td></tr>
  <tr><th>#</th><th>Casa</th></tr>
  <tr><td>23</td><td>Pallavolo Padova</td>
      <td class="DettaglioRisCal" onclick="return document.location.href=('Tabellino.asp?IdGara=40307')">0-0</td>
      <td>Tinet Prata di Pordenone</td><td>ref</td><td>arena</td><td>16/11/2026 Ore 20:30</td></tr>
  <tr><td>24</td><td>Acqua Sant'Anna Cuneo</td>
      <td onclick="return document.location.href=('Tabellino.asp?IdGara=40308')">2-3</td>
      <td>Vero Volley Monza</td><td>ref</td><td>arena</td><td></td></tr>
</table>
"""
JAPAN = """
<dt><div><b>第3節 GAME2</b></div></dt>
<dd><ul class="reset">
  <li><img src="/files/2026-27/team/voreas/emblem.png"/><b>ヴォレアス</b>
      <div class="game"><span></span><span></span><span></span><span></span><span></span><span></span></div></li>
  <li class="away"><img src="/files/2026-27/team/fkagoshima/emblem.png"/><b>F鹿児島</b>
      <div class="game"><span></span><span></span><span></span><span></span><span></span><span></span></div></li>
</ul><div class="time">GAME START <em>13:35</em></div>
<div class="field"><a href="/match/detail/37995/">試合詳細</a></div></dd>
<dt><div><b>第1節 GAME1</b></div></dt>
<dd><ul class="reset">
  <li><b>サントリー</b><div class="game"><span>25</span><span>17</span><span>26</span><span>25</span><span></span><span>3</span></div></li>
  <li class="away"><b>ヴォレアス</b><div class="game"><span>23</span><span>25</span><span>24</span><span>23</span><span></span><span>1</span></div></li>
</ul><div class="time"></div><a href="/match/detail/37976/">試合詳細</a></dd>
"""


class InternationalParserTests(unittest.TestCase):
    def test_italian_heading(self):
        found = parse_italian_heading("11ª Giornata Ritorno - Domenica 10 Gennaio 2027 Ore 18:00")
        self.assertEqual(found[0].strftime("%d.%m.%Y"), "10.01.2027")
        self.assertEqual(found[2:], (11, "ritorno"))

    def test_italian_schedule_distinguishes_unplayed_and_final(self):
        matches = parse_italy(ITALY)
        self.assertEqual(len(matches), 2)
        a, b = matches
        self.assertEqual(a["id"], "it-40307")
        self.assertEqual(a["date"], "16.11.2026")
        self.assertEqual(a["time"], "20:30")
        self.assertEqual(a["status"], "scheduled")
        self.assertIsNone(a["home_sets"])
        self.assertEqual(b["id"], "it-40308")
        self.assertEqual(b["status"], "finished")
        self.assertEqual((b["home_sets"], b["away_sets"]), (2, 3))

    def test_japanese_month_options_and_days(self):
        document = """
          <select id="select-year"><option selected value="2026">2026-27</option></select>
          <select id="select-ym"><option value="2026:10">10月</option>
          <option value="2026:11">11月</option><option value="2027:1">1月</option></select>
          <div id="div_day_6" class="div_day"></div>
          <div id="div_day_7" class="div_day active"></div>
        """
        self.assertEqual(japan_months(document), (2026, [(2026, 10), (2026, 11), (2027, 1)]))
        self.assertEqual(parse_japan_month_days(document), [6, 7])

    def test_japanese_ajax_fixture_and_finished_points(self):
        first, second = parse_japan_day(JAPAN, 2026, 11, 7)
        self.assertEqual(first["id"], "jp-37995")
        self.assertEqual(first["date"], "07.11.2026")
        self.assertEqual(first["time"], "05:35")  # 13:35 in Tokyo
        self.assertEqual(first["status"], "scheduled")
        self.assertEqual(first["team_logos"][0], "https://www.svleague.jp/files/2026-27/team/voreas/emblem.png")
        self.assertEqual(second["status"], "finished")
        self.assertEqual(second["home_sets"], 3)
        self.assertEqual(second["away_sets"], 1)
        self.assertEqual(second["set_scores"], ["25:23", "17:25", "26:24", "25:23"])

    def test_japanese_time_conversion_preserves_local_date(self):
        from datetime import datetime
        self.assertEqual(japanese_time(datetime(2026, 11, 6), "18:35"), ("06.11.2026", "10:35"))
        self.assertEqual(japanese_time(datetime(2026, 10, 24), ""), ("24.10.2026", ""))

    def test_bad_ajax_fragment_fails_not_overwrites(self):
        with self.assertRaises(RuntimeError):
            parse_japan_day("<dt>one</dt>", 2026, 11, 7)

    def test_atomic_snapshot_and_no_timestamp_only_changes(self):
        match = parse_italy(ITALY)[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "italy.json"
            first = build_feed("italy", "SuperLega", "https://source.test", [match.copy()])
            self.assertTrue(write_feed(path, first))
            stored = json.loads(path.read_text(encoding="utf-8"))
            newer = build_feed("italy", "SuperLega", "https://source.test", [match.copy()])
            self.assertFalse(write_feed(path, newer))
            self.assertEqual(stored, json.loads(path.read_text(encoding="utf-8")))

    def test_japanese_time_is_reused_after_official_results_omit_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "japan.json"
            old = build_feed("japan", "SV.League", "https://source.test", [parse_japan_day(JAPAN, 2026, 11, 7)[0]])
            write_feed(path, old)
            match = parse_japan_day(JAPAN, 2026, 11, 7)[0]
            match["time"] = ""
            match["status"] = "finished"
            match["home_sets"] = 3
            match["away_sets"] = 0
            new = build_feed("japan", "SV.League", "https://source.test", [match])
            write_feed(path, new)
            stored = json.loads(path.read_text())
            self.assertEqual(stored["matches"][0]["time"], "05:35")


if __name__ == "__main__":
    unittest.main()
