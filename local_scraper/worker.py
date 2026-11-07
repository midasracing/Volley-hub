"""One disposable browser process; the parent alone can publish the feed."""

import argparse
from pathlib import Path

from .engines import CamoufoxBrowser, SeleniumBrowser, Session
from .feed import build_feed, detail_identity, source
from .storage import atomic_json, now, read_json, safe_error


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--engine", choices=("seleniumbase", "camoufox"), required=True)
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--events", type=Path, required=True)
    p.add_argument("--browser")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--refresh-details", action="store_true")
    p.add_argument("--camoufox-ca", type=Path)
    p.add_argument("--document-budget", type=int, default=40)
    args = p.parse_args()
    report = {"engine": args.engine, "started_at": now(), "ok": False}

    def record(event):
        from .runner import append_event

        append_event(args.events, {"engine": args.engine, **event})

    options = {"profile": args.candidate.parent / (args.engine + "-profile")}
    if args.engine == "camoufox":
        options["ca_certificate"] = args.camoufox_ca
    browser = (SeleniumBrowser if args.engine == "seleniumbase" else CamoufoxBrowser)(
        args.browser, args.headless, **options
    )
    session = Session(browser, record, budget=args.document_budget)
    try:
        previous = read_json(args.previous, {})
        cache_path = args.events.parent / "details-cache.json"
        try:
            cache = read_json(cache_path, {})
        except ValueError:
            record({"event": "detail_cache_unreadable"})
            cache = {}
        cached_matches = (
            cache.get("matches", [])
            if isinstance(cache, dict) and cache.get("source") == source.SCHEDULE_URL
            else []
        )
        saved = {detail_identity(m): m for m in cached_matches}

        def remember(match):
            match.pop("match_url", None)
            saved[detail_identity(match)] = match
            atomic_json(
                cache_path,
                {"source": source.SCHEDULE_URL, "matches": list(saved.values())[-200:]},
            )

        browser.start()
        data, metrics = build_feed(
            session.fetch,
            previous,
            args.refresh_details,
            detail_cache=cached_matches,
            on_detail=remember,
        )
        atomic_json(args.candidate, data)
        report.update(ok=True, metrics=metrics)
    except Exception as error:
        report.update(
            error=type(error).__name__ + ": " + safe_error(error),
            retry_after=max(getattr(error, "retry_after", 0), session.retry_after),
        )
    finally:
        try:
            browser.close()
        except Exception as error:
            report["close_error"] = safe_error(error)
        report.update(finished_at=now(), documents=session.requests)
        atomic_json(args.report, report)
        record({"event": "attempt_finished", **report})
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
