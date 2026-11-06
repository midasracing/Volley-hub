"""Verify an incremental import with cached complete results and a stable browser identity."""
import hashlib
import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from camoufox.sync_api import Camoufox
from camoufox.utils import launch_options

from alternatives import Alternative
from run import HERE, PAGES, validate
import scraper_incremental as scraper
from transport_support import challenge


class PersistentCamoufox(Alternative):
    def __init__(self, profile, options=None):
        super().__init__('camoufox', True)
        self.profile = profile
        self.options = options

    def start(self):
        if self.options is None:
            self.options = launch_options(headless=False, user_data_dir=str(self.profile))
        self.manager = Camoufox(from_options=self.options, persistent_context=True)
        context = self.manager.__enter__()
        self.client = context.browser
        self.page = context.pages[0] if context.pages else context.new_page()


def main():
    output = HERE / 'outputs' / 'camoufox-incremental'
    output.mkdir(parents=True, exist_ok=True)
    production = HERE.parents[1] / 'data' / 'pomorska3liga.json'
    before = hashlib.sha256(production.read_bytes()).hexdigest()
    seed = json.loads(production.read_text())
    profile = Path(tempfile.mkdtemp(prefix='volleystation-camoufox-'))
    engine = PersistentCamoufox(profile)
    blocked, phase, detail_url = False, 'full_import', None
    rows = []
    summary = {'started_at': datetime.now(timezone.utc).isoformat(), 'engine': 'camoufox-headful',
               'quality_passed': False, 'seeded_from_existing_feed': True, 'restart_passed': False,
               'seed_feed_sha256': before,
               'seed_logos_available': sum(bool(t.get('logo')) for t in seed.get('teams', [])),
               'seed_finished_with_sets': sum(bool(m.get('set_scores')) for m in seed.get('matches', []) if m.get('status') == 'finished'),
               'identity_reused_after_restart': True}

    def fetch(url):
        nonlocal blocked, detail_url
        if blocked or len(rows) >= 12:
            raise RuntimeError('Blocked or experiment browser request budget exhausted')
        time.sleep(3)
        tick = time.monotonic()
        result = engine.get(url)
        headers = {k.lower(): v for k, v in result['headers'].items()}
        html = result['html']
        title = BeautifulSoup(html, 'html.parser').title
        row = {'phase': phase, 'url': url, 'status': result['status'], 'challenge': challenge(html, headers),
               'challenge_seen_initially': result.get('challenge_seen_initially'), 'cf_ray': headers.get('cf-ray'),
               'title': title.get_text(strip=True) if title else '', 'elapsed_seconds': round(time.monotonic()-tick, 3)}
        kind = next((kind for kind, target in PAGES if target == url), None)
        if kind:
            row.update(validate(kind, html, url))
        row['ok'] = result['status'] in (200, 304) and not row['challenge']
        rows.append(row)
        print(f"{phase} request={len(rows)} status={row['status']} challenge={row['challenge']}", flush=True)
        if not row['ok']:
            blocked = True
            raise RuntimeError('HTTP refusal/challenge; no further browser requests')
        if url == scraper.RESULTS_URL and detail_url is None:
            matches = scraper.parse_matches(BeautifulSoup(html, 'html.parser'), url)
            detail_url = next((m['match_url'] for m in matches if m['status'] == 'finished'), None)
        return BeautifulSoup(html, 'html.parser')

    try:
        control = requests.get(scraper.SCHEDULE_URL, timeout=(10, 30))
        summary['plain_http_control'] = {'status': control.status_code,
                                        'challenge': challenge(control.text, {k.lower(): v for k, v in control.headers.items()})}
        print('Plain HTTP control:', summary['plain_http_control'], flush=True)
        engine.start()
        scraper.OUT = output / 'pomorska3liga.json'
        scraper.OUT.write_bytes(production.read_bytes())
        scraper.fetch = fetch
        scraper.main()
        data = json.loads(scraper.OUT.read_text())
        matches = data['matches']
        finished = [m for m in matches if m['status'] == 'finished']
        summary.update(matches=len(matches), finished=len(finished), table_rows=len(data['table']),
                       teams=len(data['teams']), teams_with_logos=sum(bool(t.get('logo')) for t in data['teams']),
                       matches_with_time=sum(bool(m.get('time')) for m in matches),
                       finished_with_full_sets=sum(bool(m['set_scores']) and len(m['set_scores']) == m['home_sets']+m['away_sets'] for m in finished))
        summary['quality_passed'] = bool(not blocked and len(matches) >= 60 and len(data['table']) == 9
                                         and summary['teams_with_logos'] == 9
                                         and summary['matches_with_time'] == len(matches)
                                         and summary['finished_with_full_sets'] == len(finished))
        if not blocked:
            pages = PAGES[:3]
            hashes = {row['url']: row.get('data_sha256') for row in rows}
            for phase in ('after_restart',):
                if phase == 'after_restart':
                    engine.close()
                    engine = PersistentCamoufox(profile, options=engine.options)
                    engine.start()
                passed = True
                for kind, url in pages:
                    soup = fetch(url)
                    check = validate(kind, str(soup), url)
                    rows[-1].update(check)
                    passed = passed and check['valid']
                    rows[-1]['same_data_after_restart'] = hashes.get(url) == check['data_sha256']
                summary['restart_passed'] = bool(passed and all(row.get('same_data_after_restart') for row in rows if row['phase'] == 'after_restart'))
    except Exception as error:
        summary['error'] = f'{type(error).__name__}: {error}'
        print(summary['error'], flush=True)
    finally:
        try:
            engine.close()
        except Exception as error:
            summary['close_error'] = str(error)
        shutil.rmtree(profile, ignore_errors=True)
        summary.update(browser_requests=len(rows), production_unchanged=hashlib.sha256(production.read_bytes()).hexdigest() == before)
        (output / 'requests.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows))
        (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
