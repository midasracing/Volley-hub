"""Read a bounded snapshot of volleyball match-winner odds; never place bets."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time

import requests
from betclic_api import BetclicClient
from betclic_api.client import _BASE_URL
from betclic_api.parser import parse_match_detail_response
from betclic_api.proto import decode_protobuf, grpc_frame


WINNER_MARKET = "vainqueur du match"  # French locale, exact match: no set/score markets.
COUNTRIES = {"pl": "pologne", "it": "italie", "jp": "japon"}
MAX_FRAME_BYTES = 2_000_000
MAX_STREAM_BYTES = 4_000_000


class SnapshotError(RuntimeError):
    """The endpoint did not supply a usable, complete snapshot."""


class BetclicSnapshotClient(BetclicClient):
    """Keep upstream protobuf parsing, close notification streams after the snapshot.

    Private upstream imports are intentional and covered by the pinned requirement.
    Network/protocol errors propagate instead of becoming an empty successful feed.
    """

    def __init__(self):
        super().__init__(locale="fr", timeout=(5, 8))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._session.close()

    def _post(self, service, method, payload):
        started = time.monotonic()
        response = self._session.post(
            f"{_BASE_URL}/{service}/{method}",
            data=grpc_frame(payload), timeout=self.timeout, stream=True,
        )
        try:
            response.raise_for_status()
            status = response.headers.get("grpc-status", "0")
            if status != "0":
                raise SnapshotError(f"gRPC status {status}")
            buffer = bytearray()
            frames = []
            received = 0
            for chunk in response.iter_content(chunk_size=1024):
                if time.monotonic() - started > 20:
                    raise SnapshotError("Snapshot deadline exceeded")
                received += len(chunk)
                if received > MAX_STREAM_BYTES:
                    raise SnapshotError("Snapshot exceeds the byte limit")
                buffer.extend(chunk)
                while len(buffer) >= 5:
                    flags = buffer[0]
                    size = int.from_bytes(buffer[1:5], "big")
                    if size > MAX_FRAME_BYTES:
                        raise SnapshotError("gRPC frame exceeds the byte limit")
                    if len(buffer) < 5 + size:
                        break
                    data = bytes(buffer[5:5 + size])
                    del buffer[:5 + size]
                    if flags == 0x80:
                        trailers = {}
                        for line in data.decode("ascii").splitlines():
                            key, separator, value = line.partition(":")
                            if separator:
                                trailers[key.strip().lower()] = value.strip()
                        if trailers.get("grpc-status") != "0":
                            raise SnapshotError(f"gRPC status {trailers.get('grpc-status', 'missing')}")
                        if not frames:
                            raise SnapshotError("No snapshot before gRPC trailers")
                        return frames  # An explicitly empty, successfully completed snapshot.
                    if flags != 0:
                        raise SnapshotError(f"Unsupported gRPC frame flags: {flags}")
                    frames.append({"flags": flags, "data": data})
                    if len(frames) > 64:
                        raise SnapshotError("Too many frames without a snapshot")
                    if method == "GetMatchesBySportWithNotifications":
                        # Field 1 is the initial listing response, including a valid
                        # empty last page. Field 2 carries later notifications.
                        # Waiting for a match on an empty page keeps the stream open.
                        ready = any(isinstance(wrapper, bytes)
                                    for wrapper in decode_protobuf(data).get(1, []))
                    elif method == "GetMatchWithNotification":
                        ready = parse_match_detail_response(frames).id is not None
                    else:
                        raise SnapshotError(f"Unsupported snapshot method: {method}")
                    if ready:
                        return frames
            raise SnapshotError("Stream ended before a complete snapshot")
        finally:
            response.close()


def winner_market(match):
    """Return only an active two-way full-match winner market, or None."""
    for market in match.markets:
        if " ".join(market.name.casefold().split()) != WINNER_MARKET:
            continue
        if market.suspended or len(market.selections) != 2:
            continue
        selections = market.selections
        if len({selection.name.strip().casefold() for selection in selections}) != 2:
            continue
        if any(not selection.name.strip() or not math.isfinite(selection.odds)
               or selection.odds <= 1 for selection in selections):
            continue
        return {
            "name": market.name,
            "selections": [{"name": selection.name, "odds": selection.odds}
                           for selection in selections],
        }
    return None


def country_for(match):
    """Match the country prefix of a domestic competition in the fixed FR locale."""
    prefix = (match.competition or "").strip().casefold().split(maxsplit=1)
    return next((code for code, name in COUNTRIES.items() if prefix and prefix[0] == name), None)


def collect_matches(client, countries, max_pages, max_matches):
    """Page by actual received count; signal caps or an ignored offset explicitly."""
    matches = []
    seen = set()
    offset = 0
    for _ in range(max_pages):
        page = client.get_matches("volleyball", offset=offset)["matches"]
        if not page:
            return matches, False
        new_ids = set()
        for match in page:
            if match.id is None:
                raise SnapshotError("Match without an ID in the listing")
            if match.id in seen:
                continue
            seen.add(match.id)
            new_ids.add(match.id)
            if country_for(match) not in countries or len(match.teams) != 2:
                continue
            if len(matches) == max_matches:
                return matches, True
            matches.append(match)
        if not new_ids:
            return matches, True
        offset += len(page)
    return matches, True


def make_snapshot(client, countries=("pl", "it", "jp"), max_pages=5, max_matches=40):
    matches, truncated = collect_matches(client, set(countries), max_pages, max_matches)
    records = []
    for listed in matches:
        detail = client.get_match(listed.id)
        if detail.id != listed.id:
            raise SnapshotError("Detail response does not match the listed match ID")
        competition_id = detail.competition_id or listed.competition_id
        records.append({
            "id": str(detail.id),
            "country": country_for(listed),
            "name": detail.name or listed.name,
            "starts_at": detail.date or listed.date,
            "competition": {
                "id": str(competition_id) if competition_id is not None else None,
                "name": detail.competition or listed.competition,
            },
            "teams": [team.name for team in (detail.teams or listed.teams)],
            "winner_market": winner_market(detail),
        })
    return {
        "source": "betclic",
        "sport": "volleyball",
        "countries": list(countries),
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "truncated": truncated,
        "matches": records,
    }


def write_snapshot(path, document):
    """Replace an export atomically, only after every request succeeded."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as output:
            temporary = Path(output.name)
            output.write(document)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def positive_int(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("Wartość musi być większa od zera")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kursy Betclic na zwycięzcę meczu siatkówki (JSON)")
    parser.add_argument("--country", choices=tuple(COUNTRIES), action="append",
                        help="pl: Polska, it: Włochy, jp: Japonia; domyślnie wszystkie trzy")
    parser.add_argument("--max-pages", type=positive_int, default=5)
    parser.add_argument("--max-matches", type=positive_int, default=40)
    parser.add_argument("--output", type=Path, help="Plik JSON; domyślnie stdout")
    args = parser.parse_args(argv)
    try:
        with BetclicSnapshotClient() as client:
            countries = tuple(dict.fromkeys(args.country or COUNTRIES))
            snapshot = make_snapshot(client, countries, args.max_pages, args.max_matches)
        document = json.dumps(snapshot, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        if args.output:
            write_snapshot(args.output, document)
        else:
            sys.stdout.write(document)
        if snapshot["truncated"]:
            print("Uwaga: osiągnięto limit pobierania lub API powtórzyło stronę; lista jest niepełna.",
                  file=sys.stderr)
        return 0
    except (requests.RequestException, SnapshotError, OSError, ValueError) as error:
        print(f"Nie udało się pobrać kursów: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
