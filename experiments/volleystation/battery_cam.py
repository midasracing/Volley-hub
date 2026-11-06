"""Bounded Camoufox session experiments; each scenario has its own HTTP control."""
import argparse
import copy
import hashlib
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from camoufox.sync_api import Camoufox
from camoufox.utils import launch_options

from battery_common import measure, pace, quality, read_page, save
from run import HERE, PAGES
import scraper_incremental as scraper

CASES = ('cam-live', 'cam-linux', 'cam-cache', 'cam-fresh', 'cam-restart', 'cam-recorded', 'cam-handoff')


class Session:
    def __init__(self, case, root):
        self.case, self.root = case, root
        self.options = self.manager = self.context = self.page = None
        self.identity_digests = []

    def start(self, cycle):
        profile = self.root / (str(cycle) if self.case == 'cam-fresh' else 'persistent')
        if self.options is None or self.case == 'cam-fresh':
            options = {'headless': False, 'user_data_dir': str(profile)}
            if self.case in ('cam-linux', 'cam-cache', 'cam-recorded'):
                options['os'] = 'linux'
            if self.case == 'cam-cache':
                options['enable_cache'] = True
            if self.case == 'cam-recorded':
                from camoufox.fingerprints import get_random_preset
                preset = get_random_preset(os='linux')
                if not preset:
                    raise RuntimeError('No Linux device preset available; refusing a silent synthetic fallback')
                options['fingerprint_preset'] = preset
            self.options = launch_options(**options)
        identity = {k: v for k, v in self.options.get('env', {}).items() if k.startswith('CAMOU_CONFIG')}
        self.identity_digests.append(hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest())
        self.manager = Camoufox(from_options=copy.deepcopy(self.options), persistent_context=True)
        self.context = self.manager.__enter__()
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    def close(self):
        if self.manager and self.context:
            self.manager.__exit__(None, None, None)
        self.manager = self.context = self.page = None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--cycles', type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    output = HERE/'outputs'/'battery'/args.case
    output.mkdir(parents=True, exist_ok=True)
    source = HERE.parents[1]/'data'/'pomorska3liga.json'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    last_good = source
    root = Path(tempfile.mkdtemp(prefix='volleystation-battery-'))
    session = Session(args.case, root)
    rows, cycles, last = [], [], None
    blocked = False
    phase, cycle = 'import', 1
    summary = {'case': args.case, 'started_at': datetime.now(timezone.utc).isoformat(),
               'run_id': os.getenv('GITHUB_RUN_ID'), 'job': os.getenv('GITHUB_JOB'),
               'versions': {'camoufox': version('camoufox')}, 'planned_cycles': args.cycles,
               'interval_seconds': 8, 'pause_between_cycles_seconds': 20,
               'browser_navigation_budget': 14, 'cycles': cycles}

    def fetch(url):
        nonlocal last, blocked
        if blocked or len(rows) >= 14:
            raise RuntimeError('Refusal or scenario navigation budget exhausted')
        last = pace(last, 8)
        tick = time.monotonic()
        try:
            result = read_page(session.page, url, wait_seconds=45)
            kind = next((name for name, target in PAGES if target == url), None)
            row = measure(kind, url, result)
            row['clearance_cookie_present'] = any(c['name'] == 'cf_clearance' for c in session.context.cookies(url))
        except Exception as error:
            row = {'url': url, 'ok': False, 'error': f'{type(error).__name__}: {error}'}
            result = None
        row.update(cycle=cycle, phase=phase, elapsed_seconds=round(time.monotonic()-tick, 3))
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k not in ('data_sha256',)}, ensure_ascii=False), flush=True)
        if not row['ok']:
            blocked = True
            raise RuntimeError('Scenario stopped after first unsuccessful navigation')
        return BeautifulSoup(result['html'], 'html.parser')

    try:
        response = requests.get(scraper.SCHEDULE_URL, timeout=(10, 30))
        summary['plain_http_control'] = measure('schedule', scraper.SCHEDULE_URL,
            {'status': response.status_code, 'headers': dict(response.headers), 'html': response.text}, browser=False)
        for cycle in range(1, args.cycles+1):
            if cycle > 1:
                time.sleep(20)
            if session.page is None:
                session.start(cycle)
                summary['browser_version'] = session.context.browser.version
            destination = output/f'cycle-{cycle}.json'
            destination.write_bytes(last_good.read_bytes())
            scraper.OUT, scraper.fetch = destination, fetch
            start_count = len(rows)
            try:
                scraper.main()
                metrics = quality(json.loads(destination.read_text()))
                metrics['quality_passed'] = metrics['quality_passed'] and not blocked
                metrics.update(cycle=cycle, navigations=len(rows)-start_count)
            except Exception as error:
                metrics = {'cycle': cycle, 'quality_passed': False, 'navigations': len(rows)-start_count,
                           'error': f'{type(error).__name__}: {error}'}
            cycles.append(metrics)
            if not metrics['quality_passed']:
                break
            last_good = destination
            if args.case == 'cam-handoff':
                if len(rows) >= 14:
                    summary['handoff_skipped_budget'] = True
                    break
                from curl_cffi import Session as CurlSession
                cookies = session.context.cookies(scraper.SCHEDULE_URL)
                user_agent = session.page.evaluate('navigator.userAgent')
                client = CurlSession(impersonate='firefox', headers={'User-Agent': user_agent})
                try:
                    for cookie in cookies:
                        client.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'], path=cookie['path'])
                    last = pace(last, 8)
                    response = client.get(scraper.SCHEDULE_URL, timeout=35)
                    row = measure('schedule', scraper.SCHEDULE_URL,
                        {'status': response.status_code, 'headers': dict(response.headers), 'html': response.text}, browser=False)
                    row.update(cycle=cycle, phase='cookie_handoff_to_http')
                    rows.append(row)
                    summary['handoff_passed'] = row['ok']
                finally:
                    client.close()
                break
            if args.case in ('cam-fresh', 'cam-restart'):
                session.close()
        if blocked and args.case == 'cam-restart' and session.page and len(rows) < 14:
            phase = 'recovery_after_60_seconds'
            time.sleep(60)
            blocked = False
            try:
                fetch(scraper.SCHEDULE_URL)
                summary['recovery_passed'] = True
            except Exception:
                summary['recovery_passed'] = False
    except Exception as error:
        summary['setup_or_runtime_error'] = f'{type(error).__name__}: {error}'
    finally:
        try:
            session.close()
        except Exception as error:
            summary['close_error'] = str(error)
        shutil.rmtree(root, ignore_errors=True)
        summary.update(completed_cycles=len(cycles), passed_cycles=sum(bool(c['quality_passed']) for c in cycles),
                       navigations=len(rows), identity_config_digests=session.identity_digests,
                       production_unchanged=hashlib.sha256(source.read_bytes()).hexdigest() == source_hash)
        save(output, rows, summary)


if __name__ == '__main__':
    main()
