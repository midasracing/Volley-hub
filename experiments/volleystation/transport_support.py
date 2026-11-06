"""Bounded VolleyStation transport; successful HTML only, never a challenge as data."""
import atexit
import json
import os
import random
import select
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


class AccessBlocked(RuntimeError):
    pass


def atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=f'.{path.name}.', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def challenge(html, headers):
    if headers.get('cf-mitigated', '').lower() == 'challenge':
        return True
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True).casefold() if soup.title else ''
    return (any(s in title for s in ('just a moment', 'attention required', 'verify you are human', 'cierpliwości', 'cierpliwosci', 'chwileczkę'))
            or bool(soup.select('#challenge-running, #challenge-stage, #challenge-form')))


def retry_after(value):
    try:
        return max(0, float(value))
    except (TypeError, ValueError):
        try:
            return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 0


class VolleyStationClient:
    def __init__(self, mode=None, interval=None, attempts=3):
        self.mode = mode or os.getenv('VS_TRANSPORT', 'auto')
        if self.mode not in {'auto', 'http', 'browser'}:
            raise ValueError('VS_TRANSPORT must be auto, http or browser')
        self.interval = float(os.getenv('VS_MIN_INTERVAL', '2')) if interval is None else interval
        if not 0 <= self.interval <= 60 or not 1 <= attempts <= 3:
            raise ValueError('interval must be 0..60 seconds; attempts must be 1..3')
        self.attempts = attempts
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'KiedySiatka/2.0 (+https://github.com/midasracing/kiedysiatka)',
                                     'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8'})
        self.browser = None
        self.browser_hosts = set()
        self.blocked_hosts = set()
        self.cache = {}
        self.last_request = None

    def close(self):
        self.session.close()
        if self.browser:
            process, self.browser = self.browser, None
            try:
                process.stdin.close()
                process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                process.wait()
            finally:
                process.stdout.close()

    def _pace(self):
        if self.last_request is not None:
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()

    def _browser_get(self, url):
        if self.browser is None:
            self.browser = subprocess.Popen(
                ['node', str(Path(__file__).with_name('volleystation_browser.cjs'))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        try:
            self.browser.stdin.write(json.dumps({'url': url}) + '\n')
            self.browser.stdin.flush()
            ready, _, _ = select.select([self.browser.stdout], [], [], 80)
            if not ready:
                raise RuntimeError('VolleyStation browser exceeded 80s deadline')
            line = self.browser.stdout.readline()
            if not line:
                raise RuntimeError('VolleyStation browser exited without a response')
            data = json.loads(line)
            if data.get('error'):
                raise RuntimeError(f"VolleyStation browser: {data['error']}")
            return data['status'], data['headers'], data['html']
        except Exception as exc:
            self.close()
            raise RuntimeError('VolleyStation browser transport failed') from exc

    def fetch(self, url):
        parsed = urlparse(url)
        host = parsed.hostname or ''
        if (parsed.scheme != 'https' or not host.endswith('.volleystation.com')
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError('Expected an HTTPS VolleyStation subdomain URL')
        if host in self.blocked_hosts:
            raise AccessBlocked(f'VolleyStation access blocked for {host}; no more requests this run')
        if url in self.cache:
            return BeautifulSoup(self.cache[url], 'html.parser')
        browser = self.mode == 'browser' or host in self.browser_hosts
        attempt = 0
        while attempt < self.attempts:
            self._pace()
            try:
                if browser:
                    try:
                        status, headers, html = self._browser_get(url)
                    except RuntimeError:
                        self.blocked_hosts.add(host)
                        raise
                else:
                    response = self.session.get(url, timeout=(10, 30))
                    status, headers, html = response.status_code, response.headers, response.text
            except (requests.ConnectionError, requests.Timeout) as exc:
                attempt += 1
                if attempt == self.attempts:
                    self.blocked_hosts.add(host)
                    raise RuntimeError('VolleyStation network retries exhausted') from exc
                time.sleep(2 ** attempt + random.uniform(0, 1))
                continue
            headers = {key.lower(): value for key, value in headers.items()}
            is_challenge = challenge(html, headers)
            if status in (401, 403) or (is_challenge and status != 429):
                if self.mode == 'auto' and not browser and status != 401:
                    browser = True
                    self.browser_hosts.add(host)
                    continue
                self.blocked_hosts.add(host)
                raise AccessBlocked(f'VolleyStation HTTP {status}/challenge at {host}; keeping previous data')
            if status == 429 or status in (500, 502, 503, 504):
                attempt += 1
                delay = max(retry_after(headers.get('retry-after')), 2 ** attempt + random.uniform(0, 1))
                if attempt == self.attempts or delay > 60:
                    # Do not let optional logo/detail lookups hammer a rate-limited host.
                    self.blocked_hosts.add(host)
                    raise RuntimeError(f'VolleyStation HTTP {status}; retry budget exhausted or Retry-After >60s')
                time.sleep(delay)
                continue
            if not 200 <= status < 300 or not html.strip():
                raise RuntimeError(f'VolleyStation HTTP {status} or empty response at {host}')
            if 'html' not in headers.get('content-type', '').lower():
                raise RuntimeError(f'VolleyStation returned non-HTML content at {host}')
            self.cache[url] = html
            return BeautifulSoup(html, 'html.parser')
        raise RuntimeError('VolleyStation request budget exhausted')


_client = None


def fetch(url):
    global _client
    if _client is None:
        _client = VolleyStationClient()
        atexit.register(_client.close)
    return _client.fetch(url)
