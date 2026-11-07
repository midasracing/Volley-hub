#!/usr/bin/env python3
"""Compatibility entry point for the local, VolleyStation-only II liga importer."""

import sys
from pathlib import Path


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from local_scraper.runner import main as run

    return run(["--league", "second", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
