"""Serial failover and atomic publication; never publish a worker's partial output."""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .feed import validate_feed
from .storage import atomic_json, now, read_json, safe_error

ROOT = Path(__file__).resolve().parents[1]


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp bez strefy czasowej")
    return parsed.astimezone(timezone.utc)


def append_event(path, event):
    # Parent and worker write serially; retain at most four 1 MB event files.
    import logging
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(
        path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    try:
        handler.emit(
            logging.LogRecord(
                "local-scraper",
                logging.INFO,
                "",
                0,
                json.dumps({"at": now(), **event}, ensure_ascii=False),
                (),
                None,
            )
        )
    finally:
        handler.close()


def run_worker(engine, previous, candidate, report, events, args):
    import psutil

    command = [
        sys.executable,
        "-m",
        "local_scraper.worker",
        "--engine",
        engine,
        "--previous",
        str(previous),
        "--candidate",
        str(candidate),
        "--report",
        str(report),
        "--events",
        str(events),
        "--document-budget",
        str(args.document_budget),
    ]
    if args.browser:
        command += ["--browser", args.browser]
    if args.headless:
        command += ["--headless"]
    if args.refresh_details:
        command += ["--refresh-details"]
    if args.camoufox_ca:
        command += ["--camoufox-ca", str(args.camoufox_ca)]
    started = time.monotonic()
    children = {}
    timed_out = False
    with tempfile.TemporaryFile() as diagnostic:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=diagnostic,
            stderr=diagnostic,
            start_new_session=os.name != "nt",
        )
        parent = psutil.Process(process.pid)
        try:
            while process.poll() is None:
                try:
                    for child in parent.children(recursive=True):
                        children[(child.pid, child.create_time())] = child
                except psutil.Error:
                    pass
                remaining = args.timeout - (time.monotonic() - started)
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    process.wait(timeout=min(1, remaining))
                except subprocess.TimeoutExpired:
                    pass
        finally:
            # Also runs on Ctrl+C: close the browser tree before releasing the feed lock.
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            for child in reversed(list(children.values())):
                try:
                    child.terminate()
                except psutil.Error:
                    pass
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            _, alive = psutil.wait_procs(list(children.values()), timeout=2)
            for child in alive:
                try:
                    child.kill()
                except psutil.Error:
                    pass
            psutil.wait_procs(alive, timeout=2)
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if timed_out:
            return {
                "engine": engine,
                "ok": False,
                "error": f"Przekroczono limit {args.timeout} s",
            }
        try:
            result = read_json(report)
        except (ValueError, OSError):
            result = None
        if not isinstance(result, dict):
            diagnostic.seek(0, 2)
            size = diagnostic.tell()
            diagnostic.seek(max(0, size - 2000))
            detail = safe_error(diagnostic.read().decode("utf-8", errors="replace"))
            return {
                "engine": engine,
                "ok": False,
                "error": f"Proces zakończył się kodem {process.returncode}: {detail}",
            }
        if process.returncode != 0:
            result["ok"] = False
        return result


def freshness(output, max_age):
    try:
        data = read_json(output)
        if data is None:
            return {"feed_status": "missing", "age_seconds": None}
        validate_feed(data)
        age = (
            datetime.now(timezone.utc) - timestamp(data["updated_at"])
        ).total_seconds()
        if age < -300:
            raise ValueError("Data aktualizacji jest w przyszłości")
        return {
            "feed_status": "fresh" if age <= max_age else "stale",
            "age_seconds": max(0, round(age)),
            "feed_updated_at": data["updated_at"],
        }
    except (ValueError, TypeError, KeyError, OSError) as error:
        return {
            "feed_status": "invalid",
            "age_seconds": None,
            "feed_error": safe_error(error),
        }


def cycle(args, execute=run_worker, sleep=time.sleep):
    state = read_json(args.state_dir / "status.json", {})
    retry_at = state.get("next_attempt_at")
    if retry_at and timestamp(retry_at) > datetime.now(timezone.utc):
        print(
            f"Przerwa po błędzie do {retry_at}. Feed pozostaje bez zmian.",
            file=sys.stderr,
        )
        return False
    previous_path = args.output if args.output.exists() else args.seed
    previous = read_json(previous_path, {}) if previous_path else {}
    if not isinstance(previous, dict):
        raise ValueError("Cache nie jest obiektem JSON")
    state.update(last_attempt_at=now(), status="running", output=str(args.output))
    atomic_json(args.state_dir / "status.json", state)
    engines = ("seleniumbase", "camoufox") if args.engine == "auto" else (args.engine,)
    attempts = []
    events = args.state_dir / "events.jsonl"
    retry_after = 0
    try:
        with tempfile.TemporaryDirectory(
            prefix="attempt-", dir=args.state_dir
        ) as temporary:
            folder = Path(temporary)
            previous_file = folder / "previous.json"
            atomic_json(previous_file, previous)
            for index, engine in enumerate(engines):
                if index:
                    sleep(args.fallback_delay)
                candidate = folder / (engine + ".json")
                report = folder / (engine + "-report.json")
                append_event(events, {"event": "attempt_started", "engine": engine})
                publishing = False
                try:
                    attempt = execute(
                        engine, previous_file, candidate, report, events, args
                    )
                    if attempt.get("ok"):
                        data = read_json(candidate)
                        metrics = validate_feed(data, previous)
                        age = (
                            datetime.now(timezone.utc) - timestamp(data["updated_at"])
                        ).total_seconds()
                        if not -300 <= age <= args.timeout + 60:
                            raise ValueError("Kandydat ma nieaktualny znacznik czasu")
                        publishing = True
                        atomic_json(args.output, data)
                        if args.public_output:
                            atomic_json(args.public_output, data)
                        state.update(
                            status="ok",
                            last_success_at=data["updated_at"],
                            last_success_engine=engine,
                            consecutive_failures=0,
                            next_attempt_at=None,
                            attempts=attempts + [attempt],
                            metrics=metrics,
                        )
                        atomic_json(args.state_dir / "status.json", state)
                        append_event(
                            events, {"event": "published", "engine": engine, **metrics}
                        )
                        print(
                            f"OK: {engine}; {metrics['matches']} meczów, {metrics['finished']} wyników; {args.output}",
                            flush=True,
                        )
                        return True
                except Exception as error:
                    attempt = {
                        "engine": engine,
                        "ok": False,
                        "error": type(error).__name__ + ": " + safe_error(error),
                    }
                attempts.append(attempt)
                retry_after = max(retry_after, attempt.get("retry_after", 0))
                append_event(events, {"event": "attempt_failed", **attempt})
                if retry_after or publishing:
                    break  # A disk failure cannot be fixed by another browser.
    except BaseException:
        state.update(status="interrupted", attempts=attempts)
        atomic_json(args.state_dir / "status.json", state)
        raise
    failures = state.get("consecutive_failures", 0) + 1
    delay = max(retry_after, min(3600, 300 * 2 ** min(failures - 1, 4)))
    state.update(
        status="error",
        consecutive_failures=failures,
        attempts=attempts,
        next_attempt_at=(
            datetime.now(timezone.utc) + timedelta(seconds=delay)
        ).isoformat(),
    )
    atomic_json(args.state_dir / "status.json", state)
    print(
        "ALERT: aktualizacja lub publikacja nie została ukończona. "
        + "; ".join(a.get("error", "nieznany błąd") for a in attempts),
        file=sys.stderr,
        flush=True,
    )
    return False


def arguments(argv=None):
    p = argparse.ArgumentParser(
        description="Lokalny darmowy scraper Pomorskiej III ligi: UC + CDP → Camoufox."
    )
    p.add_argument("--output", type=Path, default=ROOT / "data" / "pomorska3liga.json")
    p.add_argument(
        "--seed",
        type=Path,
        help="Poprzedni feed, używany tylko gdy --output jeszcze nie istnieje.",
    )
    p.add_argument(
        "--public-output",
        type=Path,
        help="Dodatkowa atomowa kopia dla lokalnej aplikacji, np. public/data/pomorska3liga.json.",
    )
    p.add_argument("--state-dir", type=Path)
    p.add_argument(
        "--engine", choices=("auto", "seleniumbase", "camoufox"), default="auto"
    )
    p.add_argument("--browser", help="Opcjonalna ścieżka do Chrome/Chromium.")
    p.add_argument(
        "--camoufox-ca",
        type=Path,
        help="Opcjonalny zaufany certyfikat CA proxy dla prywatnego profilu Camoufox.",
    )
    p.add_argument(
        "--headless",
        action="store_true",
        help="Tryb diagnostyczny; zalecana przeglądarka z interfejsem.",
    )
    p.add_argument(
        "--refresh-details",
        action="store_true",
        help="Pobierz ponownie szczegóły zakończonych meczów.",
    )
    p.add_argument(
        "--watch", action="store_true", help="Powtarzaj aktualizacje do Ctrl+C."
    )
    p.add_argument(
        "--every",
        type=int,
        default=900,
        help="Odstęp po zakończeniu cyklu w sekundach, minimum 300.",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Limit czasu na jeden silnik: 30–1800 s.",
    )
    p.add_argument(
        "--document-budget",
        type=int,
        default=40,
        help="Limit dokumentów na silnik: 3–120; domyślnie 40.",
    )
    p.add_argument(
        "--fallback-delay",
        type=int,
        default=30,
        help="Przerwa przed silnikiem zapasowym: 15–300 s.",
    )
    p.add_argument(
        "--status",
        action="store_true",
        help="Pokaż stan i wiek feedu bez uruchamiania przeglądarki.",
    )
    p.add_argument(
        "--max-age",
        type=int,
        default=1800,
        help="Próg świeżości feedu w sekundach dla --status.",
    )
    args = p.parse_args(argv)
    if (
        args.every < 300
        or not 30 <= args.timeout <= 1800
        or not 15 <= args.fallback_delay <= 300
        or args.max_age < 1
        or not 3 <= args.document_budget <= 120
    ):
        p.error("Nieprawidłowe odstępy, limit czasu lub próg świeżości.")
    args.output = args.output.resolve()
    if args.public_output:
        args.public_output = args.public_output.resolve()
    if args.seed:
        args.seed = args.seed.resolve()
    if args.camoufox_ca:
        args.camoufox_ca = args.camoufox_ca.resolve()
        if not args.camoufox_ca.is_file():
            p.error("Nie znaleziono pliku certyfikatu CA.")
    key = hashlib.sha256(str(args.output).encode()).hexdigest()[:12]
    args.state_dir = (args.state_dir or ROOT / ".local-scraper" / key).resolve()
    return args


def main(argv=None):
    args = arguments(argv)
    if args.status:
        state = read_json(args.state_dir / "status.json", {})
        result = {**state, **freshness(args.output, args.max_age)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return (
            0
            if result["feed_status"] == "fresh" and result.get("status") == "ok"
            else 1
        )
    from filelock import FileLock, Timeout

    args.state_dir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(args.output) + ".local-scraper.lock")
    try:
        with lock.acquire(timeout=0):
            while True:
                ok = cycle(args)
                if not args.watch:
                    return 0 if ok else 1
                time.sleep(args.every)
    except Timeout:
        print(
            "Ten feed aktualizuje już inny proces lokalnego scrapera.", file=sys.stderr
        )
        return 2
    except KeyboardInterrupt:
        print("Zatrzymano lokalny scraper.", file=sys.stderr)
        return 130
    except Exception as error:
        print("ALERT: " + safe_error(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
