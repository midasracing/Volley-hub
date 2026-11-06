"""Targeted follow-ups: distinguish setup failures, bootstrap, and warm operation."""
import argparse
import asyncio
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from battery_cam import Session
from battery_common import measure, pace, quality, read_page, save
from battery_other import nodriver_probe
from run import HERE, PAGES
import scraper_incremental as scraper


async def manual_nodriver(case, rows, summary):
    import nodriver as uc
    original = uc.start
    process = None
    log = tempfile.TemporaryFile(mode='w+')
    directory = None
    async def attach(**kwargs):
        nonlocal process, directory
        directory = kwargs['user_data_dir']
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        args = [os.getenv('LAB_BROWSER', '/usr/bin/google-chrome'), '--no-sandbox',
                '--disable-dev-shm-usage', '--no-first-run', '--remote-allow-origins=*',
                f'--remote-debugging-port={port}', '--remote-debugging-address=127.0.0.1',
                f'--user-data-dir={directory}']
        if kwargs['headless']:
            args.append('--headless=new')
        process = subprocess.Popen(args+['about:blank'], stdout=log, stderr=log)
        for _ in range(80):
            try:
                response = requests.get(f'http://127.0.0.1:{port}/json/version', timeout=.5)
                response.raise_for_status()
                summary['browser_version'] = response.json().get('Browser')
                return await original(host='127.0.0.1', port=port,
                    browser_executable_path=args[0], sandbox=False, headless=kwargs['headless'])
            except requests.RequestException:
                if process.poll() is not None:
                    break
                await asyncio.sleep(.25)
        log.seek(0)
        raise RuntimeError('Manual Chrome CDP endpoint unavailable: '+log.read()[-1500:])
    uc.start = attach
    try:
        await nodriver_probe(case, rows, summary)
    finally:
        uc.start = original
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        log.close()
        if directory:
            shutil.rmtree(directory, ignore_errors=True)


def cam_trials(case, rows, summary, output):
    seed = HERE/'seed-validated-20261106.json'
    production = HERE.parents[1]/'data'/'pomorska3liga.json'
    before = hashlib.sha256(production.read_bytes()).hexdigest()
    summary.update(seed_sha256=hashlib.sha256(seed.read_bytes()).hexdigest(),
                   seed_provenance_run='42214482012', interval_seconds=15)
    root = Path(tempfile.mkdtemp(prefix='volleystation-followup-'))
    mode = 'cam-fresh' if case == 'cam-fresh-3' else 'cam-restart' if case == 'cam-recover' else 'cam-live'
    session = Session(mode, root)
    last, blocked, cycle, phase = None, False, 1, 'import'
    cycles = []
    def fetch(url):
        nonlocal last, blocked
        if blocked or len(rows) >= 11:
            raise RuntimeError('Follow-up blocked or navigation budget exhausted')
        last = pace(last, 15)
        tick = time.monotonic()
        result = read_page(session.page, url, wait_seconds=45)
        kind = next((kind for kind, target in PAGES if target == url), None)
        if kind is None and '/matches/' in url:
            kind = 'detail'
        row = measure(kind, url, result)
        row.update(cycle=cycle, phase=phase, elapsed_seconds=round(time.monotonic()-tick, 3))
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if not row['ok']:
            blocked = True
            raise RuntimeError('Source refusal or invalid data')
        return BeautifulSoup(result['html'], 'html.parser')
    try:
        if case == 'cam-handoff':
            from curl_cffi import Session as CurlSession
            from curl_cffi.requests.impersonate import REAL_TARGET_MAP
            session.start(1)
            fetch(scraper.SCHEDULE_URL)
            cookies = session.context.cookies(scraper.SCHEDULE_URL)
            summary['handoff_cookie_count'] = len(cookies)
            summary['handoff_clearance_cookie_present'] = any(c['name']=='cf_clearance' for c in cookies)
            summary['handoff_tls_profile'] = REAL_TARGET_MAP.get('firefox')
            summary['browser_version'] = session.context.browser.version
            ua = session.page.evaluate('navigator.userAgent')
            with CurlSession(impersonate='firefox', headers={'User-Agent': ua}) as client:
                for cookie in cookies:
                    client.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'], path=cookie['path'])
                last = pace(last, 15)
                response = client.get(scraper.SCHEDULE_URL, timeout=35)
                row = measure('schedule', scraper.SCHEDULE_URL,
                    {'status':response.status_code,'headers':dict(response.headers),'html':response.text}, browser=False)
                row['phase'] = 'cookie_handoff_to_http'
                rows.append(row)
                summary['handoff_passed'] = row['ok']
            return
        for cycle in range(1, 4 if case in ('cam-fresh-3', 'cam-slow') else 2):
            if cycle > 1:
                time.sleep(30)
            blocked = False
            if session.page is None:
                session.start(cycle)
                summary['browser_version'] = session.context.browser.version
            destination = output/f'cycle-{cycle}.json'
            destination.write_bytes(seed.read_bytes())
            scraper.OUT, scraper.fetch = destination, fetch
            first = len(rows)
            try:
                scraper.main()
                metrics = quality(json.loads(destination.read_text()))
                metrics['quality_passed'] = metrics['quality_passed'] and not blocked
                metrics.update(cycle=cycle, navigations=len(rows)-first)
            except Exception as error:
                metrics = {'cycle':cycle,'quality_passed':False,'navigations':len(rows)-first,'error':str(error)}
            cycles.append(metrics)
            if case == 'cam-fresh-3':
                session.close()
            elif not metrics['quality_passed']:
                break
        if case == 'cam-recover':
            if not blocked and cycles and cycles[0]['quality_passed']:
                session.close(); time.sleep(20); session.start(2)
                phase = 'after_restart'
                try:
                    fetch(scraper.SCHEDULE_URL)
                    summary['restart_probe_passed'] = True
                except Exception:
                    summary['restart_probe_passed'] = False
            if blocked and rows:
                failed_url = rows[-1]['url']
                summary['recovery_target_url'] = failed_url
                time.sleep(60)
                blocked = False; phase = 'same_url_recovery_after_60_seconds'
                try:
                    fetch(failed_url)
                    summary['same_url_recovery_passed'] = True
                except Exception:
                    summary['same_url_recovery_passed'] = False
    finally:
        session.close()
        shutil.rmtree(root, ignore_errors=True)
        summary.update(cycles=cycles, passed_cycles=sum(bool(c['quality_passed']) for c in cycles),
                       identity_config_digests=session.identity_digests,
                       production_unchanged=hashlib.sha256(production.read_bytes()).hexdigest()==before)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case',choices=['nodriver-headless','nodriver-headful','cam-slow','cam-fresh-3','cam-handoff','cam-recover'],required=True)
    args=parser.parse_args()
    output=HERE/'outputs'/'followup'/args.case;output.mkdir(parents=True,exist_ok=True)
    summary={'case':args.case,'run_id':os.getenv('GITHUB_RUN_ID'),'navigation_budget':11}
    rows=[]
    try:
        response=requests.get(scraper.SCHEDULE_URL,timeout=(10,30))
        summary['plain_http_control']=measure('schedule',scraper.SCHEDULE_URL,
            {'status':response.status_code,'headers':dict(response.headers),'html':response.text},browser=False)
        if args.case.startswith('nodriver'):
            summary['manual_chrome_attach']=True
            asyncio.run(manual_nodriver(args.case,rows,summary))
        else:
            cam_trials(args.case,rows,summary,output)
    except Exception as error:
        summary['setup_or_runtime_error']=f'{type(error).__name__}: {error}'
    summary.update(navigations=len(rows),passed_navigations=sum(bool(row['ok']) for row in rows))
    save(output,rows,summary)


if __name__=='__main__':
    main()
