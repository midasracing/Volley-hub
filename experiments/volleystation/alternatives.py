"""Bounded trials of a different browser engine and HTTP/TLS implementation."""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from bs4 import BeautifulSoup

from run import PAGES, validate
from transport_support import challenge


class Alternative:
    def __init__(self, name, headful):
        self.name, self.headful = name, headful
        self.client = self.manager = None

    def start(self):
        if self.name == 'curl_cffi':
            from curl_cffi import Session
            self.client = Session(impersonate='chrome')
        else:
            from camoufox.sync_api import Camoufox
            options = {'headless': not self.headful}
            if os.getenv('HTTPS_PROXY'):
                options['proxy'] = {'server': os.environ['HTTPS_PROXY']}
            self.manager = Camoufox(**options)
            self.client = self.manager.__enter__()
            self.page = self.client.new_page()

    def get(self, url):
        if self.name == 'curl_cffi':
            response = self.client.get(url, timeout=35)
            return {'status': response.status_code, 'headers': dict(response.headers),
                    'html': response.text, 'final_url': response.url}
        responses = []
        def capture(response):
            if response.request.is_navigation_request() and response.frame == self.page.main_frame:
                responses.append(response)
        self.page.on('response', capture)
        try:
            self.page.goto(url, wait_until='domcontentloaded', timeout=35000)
            initial_challenge = challenge(self.page.content(), {})
            try:
                self.page.wait_for_function('''() => !/just a moment|verify you are human|attention required|cierpliwości|cierpliwosci|chwileczkę/i.test(document.title)
                  && !document.querySelector('#challenge-running, #challenge-stage, #challenge-form')''', timeout=20000)
            except Exception:
                pass
            response = responses[-1] if responses else None
            return {'status': response.status if response else None,
                    'headers': response.all_headers() if response else {}, 'html': self.page.content(),
                    'final_url': self.page.url, 'challenge_seen_initially': initial_challenge,
                    'browser': self.client.version}
        finally:
            self.page.remove_listener('response', capture)

    def close(self):
        if self.manager and self.client:
            self.manager.__exit__(None, None, None)
        elif self.client:
            self.client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engines', nargs='+', choices=['curl_cffi', 'camoufox'], default=['curl_cffi', 'camoufox'])
    parser.add_argument('--headful', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    meta = {'started_at': datetime.now(timezone.utc).isoformat(), 'headful': args.headful,
            'interval_seconds': 3, 'rounds': 1, 'restart_between_rounds': False,
            'environment': 'github-actions' if os.getenv('GITHUB_ACTIONS') == 'true' else 'local-managed',
            'github_run_id': os.getenv('GITHUB_RUN_ID'), 'proxy_used': bool(os.getenv('HTTPS_PROXY')),
            'versions': {name: version(name) for name in ('camoufox', 'curl_cffi')}}
    args.output.with_suffix('.meta.json').write_text(json.dumps(meta, indent=2) + '\n')
    with args.output.open('w', buffering=1) as output:
        for name in args.engines:
            engine = Alternative(name, args.headful)
            initialized = False
            try:
                for kind, url in PAGES:
                    time.sleep(3)
                    row = {'engine': name, 'round': 1, 'page': kind, 'url': url,
                           'at': datetime.now(timezone.utc).isoformat()}
                    tick = time.monotonic()
                    try:
                        if not initialized:
                            engine.start()
                            initialized = True
                        result = engine.get(url)
                        headers = {k.lower(): v for k, v in result['headers'].items()}
                        html = result['html']
                        title = BeautifulSoup(html, 'html.parser').title
                        row.update(status=result['status'], title=title.get_text(strip=True) if title else '',
                                   challenge=challenge(html, headers), cf_ray=headers.get('cf-ray'),
                                   browser=result.get('browser'),
                                   challenge_seen_initially=result.get('challenge_seen_initially'))
                        row.update(validate(kind, html, url))
                        row['ok'] = bool((result['status'] == 200 or (name == 'camoufox' and result['status'] == 304))
                                         and row['valid'] and not row['challenge'])
                    except Exception as exc:
                        row.update(ok=False, error=f'{type(exc).__name__}: {exc}')
                    row['elapsed_seconds'] = round(time.monotonic() - tick, 3)
                    output.write(json.dumps(row, ensure_ascii=False) + '\n')
                    print(f"{name} headful={args.headful} {kind}: ok={row['ok']} status={row.get('status')} "
                          f"parsed={row.get('parsed_count')} seconds={row['elapsed_seconds']} {row.get('error', '')}", flush=True)
                    if not row['ok']:
                        break
            finally:
                engine.close()


if __name__ == '__main__':
    main()
