"""Headed, local browser engines with one session per import and bounded access."""

import os
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup


class AccessError(RuntimeError):
    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after


def is_challenge(html, headers=None):
    headers = {k.lower(): str(v).lower() for k, v in (headers or {}).items()}
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True).casefold() if soup.title else ""
    return (
        headers.get("cf-mitigated") == "challenge"
        or any(
            token in title
            for token in (
                "just a moment",
                "attention required",
                "verify you are human",
                "cierpliwości",
                "cierpliwosci",
                "chwileczkę",
            )
        )
        or bool(soup.select("#challenge-running, #challenge-stage, #challenge-form"))
    )


def inherited_proxy():
    value = (
        os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
        or os.getenv("HTTP_PROXY")
        or os.getenv("http_proxy")
    )
    if not value:
        return None
    parsed = urlparse(value if "://" in value else "http://" + value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Nieobsługiwany adres proxy ze środowiska")
    return parsed


class SeleniumBrowser:
    def __init__(self, binary=None, headless=False, profile=None):
        self.binary = binary
        self.headless = headless
        self.manager = self.owner = self.cdp = None
        self.responses = []
        self.origin = None
        self.profile = profile

    def start(self):
        import mycdp
        from seleniumbase import SB

        if self.binary and not Path(self.binary).is_file():
            raise FileNotFoundError("Nie znaleziono wskazanego pliku Chrome/Chromium")
        options = {
            "uc": True,
            "headed": not self.headless,
            "headless": self.headless,
            "incognito": True,
        }
        if self.binary:
            options["binary_location"] = self.binary
        if self.profile:
            options["user_data_dir"] = str(self.profile)
        proxy = inherited_proxy()
        if proxy:
            options["proxy"] = proxy.netloc
        self.manager = SB(**options)
        self.owner = self.manager.__enter__()
        self.owner.activate_cdp_mode("about:blank")
        self.cdp = self.owner.cdp

        async def capture(event, *args):
            if (
                event.type_ == mycdp.network.ResourceType.DOCUMENT
                and urlparse(event.response.url).netloc == self.origin
            ):
                self.responses.append(event.response)

        self.cdp.add_handler(mycdp.network.ResponseReceived, capture)
        self.cdp.loop.run_until_complete(self.cdp.page.send(mycdp.network.enable()))

    def get(self, url):
        self.origin = urlparse(url).netloc
        self.responses = []
        self.cdp.goto(url)
        self.cdp.sleep(5)
        html = self.cdp.get_page_source(include_shadow_dom=False)
        initial = is_challenge(html)
        helper = False
        helper_error = None
        if initial and "attention required" not in self.cdp.get_title().casefold():
            helper = True
            try:
                self.cdp.solve_captcha()
            except Exception as error:
                helper_error = type(error).__name__
        deadline = time.monotonic() + 45
        while (
            is_challenge(html)
            and "attention required" not in self.cdp.get_title().casefold()
            and time.monotonic() < deadline
        ):
            self.cdp.sleep(1.5)
            html = self.cdp.get_page_source(include_shadow_dom=False)
        html = self.cdp.get_page_source(include_shadow_dom=False)
        response = self.responses[-1] if self.responses else None
        return {
            "status": int(response.status) if response else None,
            "headers": dict(response.headers) if response else {},
            "html": html,
            "initial_challenge": initial,
            "helper_attempted": helper,
            "helper_error": helper_error,
        }

    def close(self):
        if self.manager and self.owner:
            self.manager.__exit__(None, None, None)
        self.manager = self.owner = self.cdp = None


class CamoufoxBrowser:
    def __init__(self, binary=None, headless=False, profile=None, ca_certificate=None):
        self.headless = headless
        self.manager = self.context = self.page = None
        self.profile = profile
        self.ca_certificate = ca_certificate

    def start(self):
        from camoufox.sync_api import Camoufox

        self.profile = self.profile or tempfile.mkdtemp(prefix="kiedysiatka-camoufox-")
        if self.ca_certificate:
            utility = shutil.which("certutil")
            if not utility:
                raise RuntimeError(
                    "Import CA wymaga narzędzia NSS certutil (libnss3-tools na Linuksie)"
                )
            Path(self.profile).mkdir(parents=True, exist_ok=True)
            database = "sql:" + str(self.profile)
            subprocess.run(
                [utility, "-N", "-d", database, "--empty-password"],
                check=True,
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                [
                    utility,
                    "-A",
                    "-d",
                    database,
                    "-n",
                    "configured-local-proxy-ca",
                    "-t",
                    "C,,",
                    "-i",
                    str(self.ca_certificate),
                ],
                check=True,
                capture_output=True,
                timeout=10,
            )
        options = {
            "headless": self.headless,
            "persistent_context": True,
            "user_data_dir": self.profile,
            "os": {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}[
                platform.system()
            ],
        }
        # Use the actual host OS/display and the library's generated fingerprint.
        proxy = inherited_proxy()
        if proxy:
            options["proxy"] = {
                "server": proxy.scheme
                + "://"
                + proxy.hostname
                + (":" + str(proxy.port) if proxy.port else "")
            }
            if proxy.username:
                options["proxy"].update(
                    username=proxy.username, password=proxy.password or ""
                )
        self.manager = Camoufox(**options)
        self.context = self.manager.__enter__()
        self.page = (
            self.context.pages[0] if self.context.pages else self.context.new_page()
        )

    def get(self, url):
        responses = []

        def capture(response):
            if (
                response.request.is_navigation_request()
                and response.frame == self.page.main_frame
            ):
                responses.append(response)

        self.page.on("response", capture)
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=35000)
            html = self.page.content()
            initial = is_challenge(html)
            deadline = time.monotonic() + 45
            while (
                is_challenge(html)
                and "attention required" not in self.page.title().casefold()
                and time.monotonic() < deadline
            ):
                self.page.wait_for_timeout(1500)
                html = self.page.content()
            response = responses[-1] if responses else None
            return {
                "status": response.status if response else None,
                "headers": response.all_headers() if response else {},
                "html": self.page.content(),
                "initial_challenge": initial,
                "helper_attempted": False,
            }
        finally:
            self.page.remove_listener("response", capture)

    def close(self):
        try:
            if self.manager and self.context:
                self.manager.__exit__(None, None, None)
        finally:
            if self.profile:
                shutil.rmtree(self.profile, ignore_errors=True)
            self.manager = self.context = self.page = None


class Session:
    def __init__(self, browser, record, interval=15, budget=40):
        self.browser = browser
        self.record = record
        self.interval = interval
        self.budget = budget
        self.last = None
        self.requests = 0
        self.failed = False
        self.cache = {}
        self.retry_after = 0

    def fetch(self, url):
        if self.failed:
            raise AccessError("Sesja została zatrzymana po błędzie")
        if url in self.cache:
            return BeautifulSoup(self.cache[url], "html.parser")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "pomorskie.volleystation.com":
            raise AccessError("Nieoczekiwany adres źródłowy")
        if self.requests >= self.budget:
            raise AccessError("Przekroczono limit dokumentów na aktualizację")
        if self.last is not None:
            time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        self.requests += 1
        started = time.monotonic()
        try:
            result = self.browser.get(url)
            headers = {k.lower(): str(v) for k, v in result["headers"].items()}
            status = result["status"]
            html = result["html"]
            self.record(
                {
                    "event": "document",
                    "url": url,
                    "status": status,
                    "challenge": is_challenge(html, headers),
                    "initial_challenge": result.get("initial_challenge"),
                    "helper_attempted": result.get("helper_attempted"),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            )
            if status == 429:
                from datetime import datetime, timezone
                from email.utils import parsedate_to_datetime

                value = headers.get("retry-after", "300")
                try:
                    delay = float(value)
                except ValueError:
                    try:
                        delay = (
                            parsedate_to_datetime(value) - datetime.now(timezone.utc)
                        ).total_seconds()
                    except (ValueError, TypeError):
                        delay = 300
                self.retry_after = max(300, delay)
                raise AccessError(
                    "Źródło ograniczyło częstotliwość żądań (429)",
                    retry_after=self.retry_after,
                )
            if (
                status not in (200, 304)
                or is_challenge(html, headers)
                or not html.strip()
            ):
                raise AccessError(
                    f"Brak poprawnego dokumentu źródłowego: HTTP {status}"
                )
            self.cache[url] = html
            return BeautifulSoup(html, "html.parser")
        except Exception:
            self.failed = True
            raise
