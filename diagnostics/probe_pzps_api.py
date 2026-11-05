#!/usr/bin/env python3
"""Check public read-only routes documented for SZPS against the PZPS installation."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import requests


BASE = "https://sedziowie.pzps.pl/system/webapi.php"
QUERIES = {"default": "", "version": "?version", "score": "?score",
           "clubs": "?clubs", "table": "?table", "type-9": "?type=9",
           "version-value": "?version=1", "clubs-value": "?clubs=1",
           "table-parameters": "?table&gender=2&age=4&class=2&phase=1&group=1"}


def describe(payload):
    if isinstance(payload, dict):
        return {"type": "object", "keys": sorted(payload)}
    result = {"type": type(payload).__name__}
    if isinstance(payload, list):
        result["items"] = len(payload)
        leagues = {}
        for league in payload:
            if not isinstance(league, list) or len(league) != 2:
                continue
            name, phases = league
            if not isinstance(name, str) or not isinstance(phases, list):
                continue
            leagues[name.strip()] = sum(len(matches) for _, groups in phases for _, matches in groups)
        result["league_result_counts"] = leagues
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "artifacts" / "pzps-api")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "queries": {},
              "reference_documentation": "https://system.szps.pl/sedzia/32/API_DOCUMENTATION.pdf"}
    with requests.Session() as session:
        for name, query in QUERIES.items():
            path = args.output / f"{name}.json"
            if args.offline:
                record = json.loads((args.output / f"{name}.http.json").read_text(encoding="utf-8"))
                payload = json.loads(path.read_text(encoding="utf-8"))
            else:
                response = session.get(BASE + query, timeout=(5, 20))
                response.raise_for_status()
                payload = response.json()
                record = {"url": response.url, "status": response.status_code,
                          "checked_at": datetime.now(timezone.utc).isoformat(),
                          "content_type": response.headers.get("Content-Type")}
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                (args.output / f"{name}.http.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
            report["queries"][name] = {**record, "sha256": hashlib.sha256(canonical).hexdigest(),
                                        "shape": describe(payload)}
            print(name, json.dumps(report["queries"][name], ensure_ascii=False), flush=True)
    baseline = report["queries"]["default"]["sha256"]
    report["same_as_default"] = [name for name, result in report["queries"].items()
                                 if name != "default" and result["sha256"] == baseline]
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
