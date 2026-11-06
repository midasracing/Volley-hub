"""Shared measurements: a challenge or an empty parser result is never success."""
import json
import time
from pathlib import Path

from bs4 import BeautifulSoup

from run import validate
from transport_support import challenge

WAIT_CONDITION = '''() => !/just a moment|verify you are human|attention required|cierpliwości|cierpliwosci|chwileczkę/i.test(document.title)
  && !document.querySelector('#challenge-running, #challenge-stage, #challenge-form')'''


def read_page(page, url, wait_seconds=45):
    responses = []
    def capture(response):
        if response.request.is_navigation_request() and response.frame == page.main_frame:
            responses.append(response)
    page.on('response', capture)
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=35000)
        initial = challenge(page.content(), {})
        title = page.title().casefold()
        if 'attention required' not in title:
            try:
                page.wait_for_function(WAIT_CONDITION, timeout=wait_seconds*1000)
            except Exception:
                pass
        response = responses[-1] if responses else None
        return {'status': response.status if response else None,
                'headers': response.all_headers() if response else {},
                'html': page.content(), 'challenge_seen_initially': initial}
    finally:
        page.remove_listener('response', capture)


def measure(kind, url, result, browser=True):
    headers = {k.lower(): v for k, v in result['headers'].items()}
    html = result['html']
    title = BeautifulSoup(html, 'html.parser').title
    row = {'url': url, 'page': kind or 'detail-or-profile', 'status': result['status'],
           'challenge': challenge(html, headers), 'challenge_seen_initially': result.get('challenge_seen_initially'),
           'title': title.get_text(strip=True) if title else '', 'cf_ray': headers.get('cf-ray')}
    if kind:
        row.update(validate(kind, html, url))
    else:
        row['valid'] = bool(html.strip())
    row['ok'] = bool((result['status'] == 200 or (browser and result['status'] == 304))
                     and not row['challenge'] and row['valid'])
    return row


def quality(data):
    matches = data.get('matches', [])
    finished = [m for m in matches if m.get('status') == 'finished']
    metrics = {'matches': len(matches), 'finished': len(finished),
               'matches_with_time': sum(bool(m.get('time')) for m in matches),
               'finished_with_full_sets': sum(bool(m.get('set_scores')) and
                  len(m['set_scores']) == (m.get('home_sets') or 0)+(m.get('away_sets') or 0) for m in finished),
               'teams': len(data.get('teams', [])), 'table_rows': len(data.get('table', [])),
               'teams_with_logos': sum(bool(t.get('logo')) for t in data.get('teams', []))}
    metrics['quality_passed'] = bool(metrics['matches'] >= 60 and metrics['matches_with_time'] == metrics['matches']
                                     and metrics['finished_with_full_sets'] == metrics['finished']
                                     and metrics['teams'] == metrics['table_rows'] == metrics['teams_with_logos'] == 9)
    return metrics


def save(output, rows, summary):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output/'requests.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
    (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print('SUMMARY '+json.dumps(summary, ensure_ascii=False), flush=True)


def pace(last, interval):
    if last is not None:
        time.sleep(max(0, interval-(time.monotonic()-last)))
    return time.monotonic()
