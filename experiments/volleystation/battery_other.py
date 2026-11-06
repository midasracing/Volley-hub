"""Additional transports tested without inheriting a Puppeteer/Playwright Chrome driver."""
import argparse
import asyncio
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from battery_common import measure, pace, read_page, save
from run import HERE, PAGES
from transport_support import challenge


async def nodriver_probe(case, rows, summary):
    import nodriver as uc
    directory = tempfile.mkdtemp(prefix='volleystation-nodriver-')
    browser = None
    try:
        browser = await uc.start(browser_executable_path=os.getenv('LAB_BROWSER', '/usr/bin/google-chrome'),
                                 headless=case.endswith('headless'), sandbox=False, user_data_dir=directory)
        tab = await browser.get('about:blank')
        responses = []
        async def capture(event):
            if (event.type_ == uc.cdp.network.ResourceType.DOCUMENT
                    and event.response.url.startswith('https://pomorskie.volleystation.com/')):
                responses.append(event.response)
        tab.add_handler(uc.cdp.network.ResponseReceived, capture)
        await tab.send(uc.cdp.network.enable())
        for kind, url in PAGES[:3]:
            await asyncio.sleep(8)
            responses.clear()
            tick = time.monotonic()
            try:
                await tab.get(url)
                await asyncio.sleep(2)
                html = await tab.get_content()
                initial = challenge(html, {})
                until = time.monotonic()+45
                while challenge(html, {}) and 'attention required' not in html.lower() and time.monotonic() < until:
                    await asyncio.sleep(2)
                    html = await tab.get_content()
                response = responses[-1] if responses else None
                result = {'status': int(response.status) if response else None,
                          'headers': dict(response.headers) if response else {}, 'html': html,
                          'challenge_seen_initially': initial}
                row = measure(kind, url, result)
                if response is None:
                    row['error'] = 'No main document network response captured'
            except Exception as error:
                row = {'page': kind, 'url': url, 'ok': False, 'error': f'{type(error).__name__}: {error}'}
            row['elapsed_seconds'] = round(time.monotonic()-tick, 3)
            rows.append(row)
            print(json_line(row), flush=True)
            if not row['ok']:
                break
    finally:
        if browser:
            browser.stop()
            await asyncio.sleep(0.2)
        shutil.rmtree(directory, ignore_errors=True)


def json_line(row):
    import json
    return json.dumps(row, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=['nodriver-headless', 'nodriver-headful', 'stock-firefox', 'curl-profiles'], required=True)
    args = parser.parse_args()
    rows = []
    summary = {'case': args.case, 'started_at': datetime.now(timezone.utc).isoformat(),
               'run_id': os.getenv('GITHUB_RUN_ID'), 'navigation_budget': 3, 'wait_for_challenge_seconds': 45}
    try:
        response = requests.get(PAGES[0][1], timeout=(10, 30))
        summary['plain_http_control'] = measure('schedule', PAGES[0][1],
            {'status': response.status_code, 'headers': dict(response.headers), 'html': response.text}, browser=False)
        if args.case.startswith('nodriver'):
            asyncio.run(nodriver_probe(args.case, rows, summary))
        elif args.case == 'stock-firefox':
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.firefox.launch(headless=False)
                try:
                    summary['browser_version'] = browser.version
                    page = browser.new_page()
                    for kind, url in PAGES[:3]:
                        time.sleep(8)
                        tick = time.monotonic()
                        result = read_page(page, url, wait_seconds=45)
                        row = measure(kind, url, result)
                        row['elapsed_seconds'] = round(time.monotonic()-tick, 3)
                        rows.append(row)
                        print(json_line(row), flush=True)
                        if not row['ok']:
                            break
                finally:
                    browser.close()
        else:
            from curl_cffi import Session
            for profile in ('chrome', 'firefox', 'safari'):
                time.sleep(8)
                tick = time.monotonic()
                with Session(impersonate=profile) as client:
                    response = client.get(PAGES[0][1], timeout=35)
                    row = measure('schedule', PAGES[0][1],
                        {'status': response.status_code, 'headers': dict(response.headers), 'html': response.text}, browser=False)
                row.update(profile=profile, elapsed_seconds=round(time.monotonic()-tick, 3))
                rows.append(row)
                print(json_line(row), flush=True)
    except Exception as error:
        summary['setup_or_runtime_error'] = f'{type(error).__name__}: {error}'
    summary.update(navigations=len(rows), passed_navigations=sum(bool(r['ok']) for r in rows))
    save(HERE/'outputs'/'battery'/args.case, rows, summary)


if __name__ == '__main__':
    main()
