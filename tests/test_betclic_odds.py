"""Offline checks against the pinned upstream protobuf parser and mocked HTTP."""

import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
from betclic_api.models import Market, Match, Selection, Team
from betclic_api.proto import encode_field_string, encode_field_varint

from scripts.betclic_odds import (
    BetclicSnapshotClient, MAX_FRAME_BYTES, SnapshotError, collect_matches,
    main, make_snapshot, winner_market, write_snapshot,
)


def field_bytes(number, value):
    return encode_field_string(number, value)


def _encode_varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def frame(data, flags=0):
    return bytes([flags]) + struct.pack(">I", len(data)) + data


def match_bytes(match_id=101, with_market=False):
    match = encode_field_varint(1, match_id) + encode_field_string(2, "A - B")
    match += encode_field_string(3, "2026-11-05T19:30:00Z")
    competition = encode_field_varint(1, 41288) + encode_field_string(2, "Pologne Tauron Liga H.")
    match += field_bytes(8, competition)
    if with_market:
        market = encode_field_string(2, "Vainqueur du match")
        for name, odds in (("A", 1.5), ("B", 2.5)):
            selection = encode_field_string(10, name)
            selection += _encode_varint((12 << 3) | 1) + struct.pack("<d", odds)
            market += field_bytes(16, selection)
        match += field_bytes(11, field_bytes(3, market))
    return match


def response(chunks):
    result = Mock()
    result.headers = {}
    result.iter_content.return_value = iter(chunks)
    return result


def listed_match(**fields):
    return Match(teams=[Team("A"), Team("B")], **fields)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.client = BetclicSnapshotClient()
        self.addCleanup(self.client._session.close)

    def test_fragmented_listing_stops_before_next_live_update(self):
        body = frame(field_bytes(1, field_bytes(3, match_bytes())))

        def chunks():
            for index in range(0, len(body), 3):
                yield body[index:index + 3]
            raise AssertionError("Client kept waiting for the next live update")

        http = response(chunks())
        with patch.object(self.client._session, "post", return_value=http):
            result = self.client.get_matches("volleyball")
        self.assertEqual([match.id for match in result["matches"]], [101])
        http.close.assert_called_once()
        http.iter_content.assert_called_once_with(chunk_size=1024)

    def test_detail_is_parsed_by_the_real_upstream_parser(self):
        body = frame(field_bytes(1, field_bytes(1, match_bytes(with_market=True))))
        http = response([body])
        with patch.object(self.client._session, "post", return_value=http):
            detail = self.client.get_match(101)
        self.assertEqual(winner_market(detail)["selections"],
                         [{"name": "A", "odds": 1.5}, {"name": "B", "odds": 2.5}])
        http.close.assert_called_once()

    def test_successful_empty_snapshot_requires_success_trailer(self):
        http = response([frame(b"") + frame(b"grpc-status: 0\r\n", 0x80)])
        with patch.object(self.client._session, "post", return_value=http):
            self.assertEqual(self.client.get_matches("volleyball")["matches"], [])

    def test_empty_initial_listing_does_not_wait_for_live_updates(self):
        initial = frame(field_bytes(1, encode_field_varint(4, 0) + encode_field_varint(5, 30)))

        def chunks():
            yield initial
            raise AssertionError("Empty last page kept the notification stream open")

        http = response(chunks())
        with patch.object(self.client._session, "post", return_value=http):
            self.assertEqual(self.client.get_matches("volleyball", offset=22)["matches"], [])
        http.close.assert_called_once()

    def test_failures_are_not_reported_as_an_empty_success_and_close_response(self):
        cases = [
            [],
            [frame(b"")[:3]],
            [frame(b"grpc-status: 7\r\n", 0x80)],
            [frame(b"grpc-status: 0\r\n", 0x80)],
            [frame(b"compressed", 1)],
            [b"\0" + struct.pack(">I", MAX_FRAME_BYTES + 1)],
        ]
        for chunks in cases:
            with self.subTest(chunks=chunks):
                http = response(chunks)
                with patch.object(self.client._session, "post", return_value=http):
                    with self.assertRaises(SnapshotError):
                        self.client.get_matches("volleyball")
                http.close.assert_called_once()

    def test_read_timeout_propagates_and_closes_response(self):
        def timeout():
            yield b"\0\0"
            raise requests.ReadTimeout("No complete frame")

        http = response(timeout())
        with patch.object(self.client._session, "post", return_value=http):
            with self.assertRaises(requests.ReadTimeout):
                self.client.get_matches("volleyball")
        http.close.assert_called_once()

    def test_http_error_closes_response(self):
        http = response([])
        http.raise_for_status.side_effect = requests.HTTPError("403")
        with patch.object(self.client._session, "post", return_value=http):
            with self.assertRaises(requests.HTTPError):
                self.client.get_matches("volleyball")
        http.close.assert_called_once()


class ExportTests(unittest.TestCase):
    def test_set_score_suspended_invalid_and_three_way_markets_are_excluded(self):
        for market in (
            Market("1er Set - Vainqueur du Set", selections=[Selection("A", 1.5), Selection("B", 2.5)]),
            Market("Score exact", selections=[Selection("3-0", 1.5), Selection("3-1", 2.5)]),
            Market("Vainqueur du match", True, [Selection("A", 1.5), Selection("B", 2.5)]),
            Market("Vainqueur du match", selections=[Selection("A", float("nan")), Selection("B", 2.5)]),
            Market("Vainqueur du match", selections=[Selection("A", 1), Selection("B", 2.5)]),
            Market("Vainqueur du match", selections=[Selection("A", 1.5), Selection("A", 2.5)]),
            Market("Vainqueur du match", selections=[Selection("A", 1.5), Selection("B", 2.5), Selection("X", 3)]),
        ):
            with self.subTest(market=market):
                self.assertIsNone(winner_market(Match(markets=[market])))

    def test_pagination_filters_countries_and_deduplicates_before_fetching_details(self):
        a = listed_match(id=101, competition="Pologne Tauron Liga H.")
        b = listed_match(id=102, competition="France Ligue A")
        c = listed_match(id=103, competition="Italie SuperLega")
        client = Mock()
        client.get_matches.side_effect = [
            {"matches": [a, b]}, {"matches": [a, c]}, {"matches": []},
        ]
        matches, truncated = collect_matches(client, {"pl", "it", "jp"}, 5, 40)
        self.assertEqual([match.id for match in matches], [101, 103])
        self.assertFalse(truncated)
        self.assertEqual([call.kwargs["offset"] for call in client.get_matches.call_args_list], [0, 2, 4])

    def test_ignored_offset_and_limits_mark_the_export_as_truncated(self):
        client = Mock()
        a = listed_match(id=101, competition="Japon SV.League H.")
        b = listed_match(id=102, competition="Pologne Tauron Liga H.")
        client.get_matches.return_value = {"matches": [a]}
        self.assertTrue(collect_matches(client, {"jp"}, 5, 40)[1])
        client.get_matches.return_value = {"matches": [a, b]}
        matches, truncated = collect_matches(client, {"pl", "jp"}, 5, 1)
        self.assertEqual(len(matches), 1)
        self.assertTrue(truncated)
        self.assertTrue(collect_matches(client, {"jp"}, 1, 40)[1])

    def test_export_preserves_source_names_and_reports_missing_winner_market(self):
        match = listed_match(id=101, name="Politechnika Lublin - Skra Belchatow",
                      competition_id=41288, competition="Pologne Tauron Liga H.")
        client = Mock()
        client.get_matches.side_effect = [{"matches": [match]}, {"matches": []}]
        client.get_match.return_value = match
        snapshot = make_snapshot(client)
        self.assertEqual(snapshot["matches"][0]["name"], match.name)
        self.assertEqual(snapshot["matches"][0]["id"], "101")
        self.assertIsNone(snapshot["matches"][0]["winner_market"])
        self.assertNotIn("score", snapshot["matches"][0])

    def test_wrong_detail_id_is_an_error(self):
        client = Mock()
        client.get_matches.side_effect = [
            {"matches": [listed_match(id=101, competition="Italie SuperLega")]}, {"matches": []},
        ]
        client.get_match.return_value = Match(id=999)
        with self.assertRaises(SnapshotError):
            make_snapshot(client)

    def test_only_requested_domestic_countries_are_exported(self):
        allowed = [listed_match(id=101, competition="Pologne Tauron Liga H."),
                   listed_match(id=102, competition="Italie SuperLega"),
                   listed_match(id=103, competition="Japon SV.League H.")]
        excluded = [listed_match(id=104, competition="France Ligue A"),
                    listed_match(id=105, competition="Ligue des Nations - Japon"),
                    listed_match(id=106, competition=None),
                    Match(id=107, name="Serie A1 F. 2026/27", competition="Italie Serie A1 F.")]
        client = Mock()
        client.get_matches.side_effect = [{"matches": allowed + excluded}, {"matches": []}]
        client.get_match.side_effect = allowed
        snapshot = make_snapshot(client)
        self.assertEqual([match["country"] for match in snapshot["matches"]], ["pl", "it", "jp"])
        self.assertEqual(client.get_match.call_count, 3)
        client.get_matches.side_effect = [{"matches": allowed}, {"matches": []}]
        client.get_match.side_effect = [allowed[2]]
        self.assertEqual(make_snapshot(client, countries=("jp",))["matches"][0]["country"], "jp")

    def test_failed_fetch_preserves_previous_export_and_exits_with_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "odds.json"
            path.write_text('{"previous": true}\n', encoding="utf-8")
            with patch("scripts.betclic_odds.BetclicSnapshotClient") as factory:
                factory.return_value.__enter__.return_value.get_matches.side_effect = requests.ReadTimeout("timeout")
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["--country", "pl", "--output", str(path)]), 1)
            self.assertEqual(json.loads(path.read_text()), {"previous": True})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_atomic_write_and_replace_failure_leave_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "odds.json"
            write_snapshot(path, '{"ok": true}\n')
            with patch("scripts.betclic_odds.os.replace", side_effect=OSError("failed")):
                with self.assertRaises(OSError):
                    write_snapshot(path, "new")
            self.assertEqual(json.loads(path.read_text()), {"ok": True})
            self.assertEqual(list(Path(directory).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
