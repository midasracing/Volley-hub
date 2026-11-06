#!/usr/bin/env python3
"""Small, serial comparison against real pages, with the same copied parsers."""
import argparse
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import scraper_copy as scraper
from transport_support import challenge

HERE = Path(__file__).resolve().parent
PAGES = [
    ('schedule', scraper.SCHEDULE_URL),
    ('results', scraper.RESULTS_URL),
    ('standings', scraper.STANDINGS_URL),
    ('teams', 'https://2ligamezczyzn.volleystation.com/pl/teams/'),
]


def validate(kind, html, url):
    soup = BeautifulSoup(html, 'html.parser')
    if kind in ('schedule', 'results'):
        data = scraper.parse_matches(soup, url)
        data = sorted(data, key=lambda match: match['id'])
        for match in data:
            match.pop('match_url', None)
        valid = len(data) > 0 and (kind != 'results' or all(m['status'] == 'finished' for m in data))
    elif kind == 'standings':
        data = scraper.parse_table(soup)
        valid = len(data) >= 8
    elif kind == 'detail':
        data = scraper.parse_match_detail(soup)
        valid = len(data['set_scores']) >= 3
    else:
        # Extract team identities without following links or fetching logos.
        data = sorted(set(a['href'] for a in soup.select('a[href*="/teams/"]')
                          if a['href'].rstrip('/').split('/')[-1] != 'teams'))
        valid = len(data) >= 8
    count = len(data) if not isinstance(data, dict) else len(data.get('set_scores', []))
    return {'parsed_count': count, 'valid': valid,
            'data_sha256': hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}


class Engine:
    def __init__(self, name, profile):
        self.name, self.profile = name, profile
        self.http = requests.Session()
        self.process = self.playwright = self.context = None

    def start(self):
        if self.name in ('stealth', 'rebrowser'):
            env = {**os.environ, 'LAB_PROFILE': str(self.profile)}
            self.process = subprocess.Popen(['node', str(HERE / 'browser.cjs'), self.name],
                                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, text=True, env=env)
        elif self.name == 'patchright':
            from patchright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            options = {
                'executable_path': os.getenv('LAB_BROWSER', '/usr/bin/chromium'),
                'headless': os.getenv('LAB_HEADFUL') != 'true',
                'no_viewport': True,
                'chromium_sandbox': os.getenv('LAB_NO_SANDBOX') != 'true',
                'timeout': 35000,
            }
            if os.getenv('LAB_PROXY'):
                options['proxy'] = {'server': os.environ['LAB_PROXY']}
            self.context = self.playwright.chromium.launch_persistent_context(str(self.profile), **options)
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    def get(self, url):
        if self.name == 'http':
            r = self.http.get(url, timeout=(10, 30))
            return {'status': r.status_code, 'headers': dict(r.headers), 'html': r.text, 'final_url': r.url}
        if self.name == 'patchright':
            # Capture the final main-document response, including challenge reloads.
            last_response = []
            def capture(response):
                if response.request.is_navigation_request() and response.frame == self.page.main_frame:
                    last_response[:] = [response]
            self.page.on('response', capture)
            try:
                self.page.goto(url, wait_until='domcontentloaded', timeout=35000)
                try:
                    self.page.wait_for_function('''() => !/just a moment|verify you are human|attention required|cierpliwości|cierpliwosci|chwileczkę/i.test(document.title)
                      && !document.querySelector('#challenge-running, #challenge-stage, #challenge-form')''', timeout=15000)
                except Exception:
                    pass
                response = last_response[-1] if last_response else None
                return {'status': response.status if response else None,
                        'headers': response.all_headers() if response else {},
                        'html': self.page.content(), 'final_url': self.page.url,
                        'browser': self.context.browser.version}
            finally:
                self.page.remove_listener('response', capture)
        self.process.stdin.write(json.dumps({'url': url}) + '\n')
        self.process.stdin.flush()
        ready, _, _ = select.select([self.process.stdout], [], [], 65)
        if not ready:
            raise TimeoutError('Browser worker exceeded 65s')
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(self.process.stderr.read()[-1500:])
        result = json.loads(line)
        if result.get('error'):
            raise RuntimeError(result['error'])
        return result

    def close(self):
        self.http.close()
        if self.context:
            self.context.close()
            self.context = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        if self.process:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()
            finally:
                self.process.stdout.close()
                self.process.stderr.close()
                self.process = None


def main():
    # Preserve the managed environment's outbound proxy for browser requests too.
    if 'LAB_PROXY' not in os.environ and os.getenv('HTTPS_PROXY'):
        os.environ['LAB_PROXY'] = os.environ['HTTPS_PROXY']
    parser = argparse.ArgumentParser()
    parser.add_argument('--engines', nargs='+', choices=['http', 'stealth', 'rebrowser', 'patchright'],
                        default=['http', 'stealth', 'rebrowser', 'patchright'])
    parser.add_argument('--rounds', type=int, choices=range(1, 4), default=2)
    parser.add_argument('--interval', type=float, default=3)
    parser.add_argument('--restart-between-rounds', action='store_true',
                        help='Restart browser processes while retaining their private profiles')
    parser.add_argument('--output', type=Path, default=HERE / 'results.jsonl')
    args = parser.parse_args()
    if args.interval < 2:
        parser.error('Use an interval of at least 2 seconds')
    started = datetime.now(timezone.utc).isoformat()
    from importlib.metadata import version
    versions = {'python': sys.version.split()[0], 'node': subprocess.check_output(['node', '--version'], text=True).strip(),
                'patchright': version('patchright'), 'requests': version('requests'),
                'chromium': subprocess.check_output([os.getenv('LAB_BROWSER', '/usr/bin/chromium'), '--version'], text=True).strip()}
    for package in ('puppeteer', 'puppeteer-extra', 'puppeteer-extra-plugin-stealth', 'rebrowser-puppeteer'):
        package_path = HERE / 'node_modules' / package / 'package.json'
        if package_path.exists():
            versions[package] = json.loads(package_path.read_text())['version']
    metadata = {'started_at': started, 'engines': args.engines, 'rounds': args.rounds,
                'restart_between_rounds': args.restart_between_rounds,
                'interval_seconds': args.interval, 'headful': os.getenv('LAB_HEADFUL') == 'true',
                'proxy_used': bool(os.getenv('LAB_PROXY')), 'versions': versions,
                'limitation': 'One environment/outbound network; no claim of Cloudflare bypass without an observed challenge.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.meta.json').write_text(json.dumps(metadata, indent=2) + '\n')
    profiles = Path(tempfile.mkdtemp(prefix='volleystation-lab-'))
    engines = {name: Engine(name, profiles / name) for name in args.engines}
    initialized, disabled = set(), set()
    records, detail_url = [], None
    try:
        with args.output.open('w', buffering=1) as output:
            for round_index in range(args.rounds):
                # Rotate order to reduce the advantage of being tested first.
                names = args.engines[round_index % len(args.engines):] + args.engines[:round_index % len(args.engines)]
                for name in names:
                    if name in disabled:
                        continue
                    engine = engines[name]
                    pages = PAGES + ([('detail', detail_url)] if detail_url else [])
                    for kind, url in pages:
                        time.sleep(args.interval)
                        row = {'engine': name, 'round': round_index + 1, 'page': kind, 'url': url,
                               'at': datetime.now(timezone.utc).isoformat()}
                        tick = time.monotonic()
                        try:
                            if name not in initialized:
                                engine.start()
                                initialized.add(name)
                            result = engine.get(url)
                            headers = {k.lower(): v for k, v in result['headers'].items()}
                            html = result['html']
                            row.update(status=result['status'], final_url=result['final_url'],
                                       browser=result.get('browser'), cf_ray=headers.get('cf-ray'),
                                       challenge=challenge(html, headers), bytes=len(html.encode()))
                            title = BeautifulSoup(html, 'html.parser').title
                            row['title'] = title.get_text(strip=True) if title else ''
                            row.update(validate(kind, html, url))
                            # A browser can expose the network's 304 and still provide
                            # the complete cached document. A bare HTTP 304 has no body.
                            row['browser_cache_revalidated'] = name != 'http' and result['status'] == 304
                            row['ok'] = bool((result['status'] == 200 or row['browser_cache_revalidated'])
                                             and not row['challenge'] and row['valid'])
                            if kind == 'results' and row['ok'] and detail_url is None:
                                matches = scraper.parse_matches(BeautifulSoup(html, 'html.parser'), url)
                                detail_url = next((m['match_url'] for m in matches if m['status'] == 'finished'), None)
                                if detail_url and not any(kind == 'detail' for kind, _ in pages):
                                    pages.append(('detail', detail_url))
                            if row['challenge'] or result['status'] in (401, 403, 429):
                                # One observed refusal per engine is enough for this experiment.
                                disabled.add(name)
                        except Exception as exc:
                            row.update(ok=False, error=f'{type(exc).__name__}: {exc}')
                            disabled.add(name)
                        row['elapsed_seconds'] = round(time.monotonic() - tick, 3)
                        output.write(json.dumps(row, ensure_ascii=False) + '\n')
                        records.append(row)
                        print(f"{name} round={round_index+1} {kind}: ok={row['ok']} status={row.get('status')} "
                              f"parsed={row.get('parsed_count')} seconds={row['elapsed_seconds']} "
                              f"{row.get('error', '')}", flush=True)
                        if name in disabled:
                            break
                    if args.restart_between_rounds and name in initialized and round_index + 1 < args.rounds:
                        engine.close()
                        initialized.remove(name)
    finally:
        for engine in engines.values():
            try:
                engine.close()
            except Exception:
                pass
        shutil.rmtree(profiles, ignore_errors=True)
    print(f'Results saved to {args.output}', flush=True)


if __name__ == '__main__':
    main()
