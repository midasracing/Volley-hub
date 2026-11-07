#!/usr/bin/env python3
"""Run the production VolleyStation importer for Pomorska III liga."""

import sys
from pathlib import Path


def main(argv=None):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from local_scraper.runner import main as run

    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
