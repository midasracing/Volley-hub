"""Run the complete copied scraper with one selected engine and a request budget."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from bs4 import BeautifulSoup

from run import Engine, HERE, scraper
from transport_support import challenge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', choices=['http', 'stealth', 'rebrowser', 'patchright'], default='http')
    parser.add_argument('--max-requests', type=int, default=40)
    args = parser.parse_args()
    if not 1 <= args.max_requests <= 40:
        parser.error('Request budget must be 1..40')
    if 'LAB_PROXY' not in os.environ and os.getenv('HTTPS_PROXY'):
        os.environ['LAB_PROXY'] = os.environ['HTTPS_PROXY']
    production = HERE.parents[1] / 'data' / 'pomorska3liga.json'
    previous_hash = hashlib.sha256(production.read_bytes()).hexdigest()
    profile = Path(tempfile.mkdtemp(prefix='volleystation-full-'))
    engine = Engine(args.engine, profile)
    scraper.OUT = HERE / 'outputs' / args.engine / 'pomorska3liga.json'
    requests_used = 0
    failed = False
    records = []

    def fetch(url):
        nonlocal requests_used, failed
        if failed or requests_used >= args.max_requests:
            raise RuntimeError('Access failed or experiment request budget exhausted')
        time.sleep(3)
        requests_used += 1
        result = engine.get(url)
        headers = {k.lower(): v for k, v in result['headers'].items()}
        blocked = challenge(result['html'], headers)
        records.append({'url': url, 'status': result['status'], 'challenge': blocked})
        document_available = result['status'] == 200 or (args.engine != 'http' and result['status'] == 304)
        if not document_available or blocked:
            failed = True
            raise RuntimeError(f"HTTP {result['status']}/challenge; experiment stopped")
        return BeautifulSoup(result['html'], 'html.parser')

    try:
        engine.start()
        scraper.fetch = fetch
        scraper.main()
        data = json.loads(scraper.OUT.read_text())
        matches = data['matches']
        finished = [m for m in matches if m['status'] == 'finished']
        summary = {
            'engine': args.engine, 'requests': requests_used, 'matches': len(matches),
            'finished': len(finished), 'finished_with_sets': sum(bool(m['set_scores']) for m in finished),
            'finished_with_full_sets': sum(len(m['set_scores']) == (m['home_sets'] or 0) + (m['away_sets'] or 0)
                                           and bool(m['set_scores']) for m in finished),
            'teams': len(data['teams']), 'standings': len(data['table']),
            'teams_with_logos': sum(bool(t.get('logo')) for t in data['teams']),
            'matches_with_time': sum(bool(m.get('time')) for m in matches),
            'production_unchanged': hashlib.sha256(production.read_bytes()).hexdigest() == previous_hash,
            'requests_log': records,
        }
        summary_path = scraper.OUT.with_name('summary.json')
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({k: v for k, v in summary.items() if k != 'requests_log'}, ensure_ascii=False), flush=True)
    finally:
        engine.close()
        shutil.rmtree(profile, ignore_errors=True)
        assert hashlib.sha256(production.read_bytes()).hexdigest() == previous_hash, 'Production feed changed!'


if __name__ == '__main__':
    main()
