#!/usr/bin/env python3
"""Production VolleyStation scraper for II liga and Pomorska III liga.

Run --help for league selection, browser options and continuous updates.
Results and standings are copied independently from VolleyStation.
"""

import argparse
import copy
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlsplit

from bs4 import BeautifulSoup

# Files and timestamps


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix="." + path.name + ".",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def safe_error(error):
    # Browser exceptions may include proxy URLs: keep credentials out of logs/state.
    return re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[redacted]@", str(error))[:1200]


# VolleyStation page parsers

BASE = "https://pomorskie.volleystation.com/pl/phase-6796-pomorska-iii-liga-meska"
SCHEDULE_URL = BASE + "/schedule/"
RESULTS_URL = BASE + "/results/"
STANDINGS_URL = BASE + "/standings/"
MONTHS = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "października": 10,
    "listopada": 11,
    "grudnia": 12,
}


def parse_date(text):
    match = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", text.lower())
    if not match:
        return None
    day, month_name, year = match.groups()
    month = MONTHS.get(month_name)
    if not month:
        return None
    return f"{int(day):02d}.{month:02d}.{year}"


def heading_date(anchor):
    # VolleyStation groups match links below date headings (e.g. "25 października 2026, Niedziela").
    for previous in anchor.find_all_previous(re.compile(r"^h[1-6]$")):
        result = parse_date(previous.get_text(" ", strip=True))
        if result:
            return result
    # Fallback for a layout version that wraps each day in a section.
    parent = anchor.parent
    for _ in range(4):
        if not parent:
            break
        result = parse_date(parent.get_text(" ", strip=True)[:160])
        if result:
            return result
        parent = parent.parent
    return None


def parse_matches(soup, source_url):
    matches = []
    for anchor in soup.find_all("a", href=True):
        text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
        prefix = re.match(
            r"^(?:(?:TV|Na żywo)\s+)?Runda:\s*(\d+)\s+Nr\s+(\d+)\s+(.+)$", text, re.I
        )
        if not prefix:
            continue
        round_no, match_no, rest = prefix.groups()
        date = heading_date(anchor)
        if not date:
            continue

        # Official VolleyStation labels completed matches with set score (3:0)
        # and scheduled matches with kickoff time (18:00).
        score_match = re.search(r"\s([0-3]):([0-3])\s+", rest)
        if score_match:
            home = rest[: score_match.start()].strip(" ·-")
            away = rest[score_match.end() :].strip(" ·-")
            home_sets, away_sets = int(score_match.group(1)), int(score_match.group(2))
            status = (
                "finished"
                if max(home_sets, away_sets) == 3
                else "live"
                if home_sets + away_sets or text.casefold().startswith("na żywo ")
                else "scheduled"
            )
            time = None
        else:
            time_match = re.search(r"\b(\d{2}:\d{2})\b", rest)
            if not time_match:
                continue
            home = rest[: time_match.start()].strip(" ·-")
            away = rest[time_match.end() :].strip(" ·-")
            home_sets, away_sets = None, None
            status, time = "scheduled", time_match.group(1)

        if not home or not away:
            continue
        # Keep source page and round/match number as a stable identity even if
        # VolleyStation's link path changes between page versions.
        matches.append(
            {
                "id": f"{date}-{round_no}-{match_no}",
                "competition": "Pomorska III Liga Męska",
                "date": date,
                "time": time,
                "status": status,
                "home": home,
                "away": away,
                "home_sets": home_sets,
                "away_sets": away_sets,
                "set_scores": [],
                "current_points": None,
                "round": int(round_no),
                "match_number": int(match_no),
                "source_url": source_url,
                "match_url": urljoin(source_url, anchor.get("href", "")),
            }
        )
    return matches


def parse_match_detail(soup):
    """Read kickoff time and individual set scores from an official match page."""
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    kickoff = None
    patterns = [
        r"(?:godzina rozpoczęcia|godzina meczu|początek meczu|rozpoczęcie|start meczu|match start|kick.?off|data i godzina|termin meczu)[^0-9]{0,80}(\d{1,2}:\d{2})",
        r"(?:data|termin)[^0-9]{0,50}\d{1,2}[. /-]\d{1,2}[. /-]\d{4}[^0-9]{0,80}(\d{1,2}:\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            hour, minute = match.group(1).split(":")
            kickoff = f"{int(hour):02d}:{minute}"
            break
    if not kickoff:
        # Match detail pages may display the kickoff as a standalone time rather
        # than next to a Polish label; use the first valid clock token in the page.
        time_match = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", text)
        if time_match:
            kickoff = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"

    if not kickoff:
        # Some versions keep the kickoff in structured metadata rather than visible text.
        for node in soup.select("[datetime], time, [data-start-time], [data-kickoff]"):
            candidate = " ".join(
                str(node.get(attr, ""))
                for attr in ("datetime", "data-start-time", "data-kickoff")
            )
            candidate += " " + node.get_text(" ", strip=True)
            time_match = re.search(
                r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", candidate
            )
            if time_match:
                kickoff = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
                break

    # Match pages render each team's points in paired .team-points-row
    # containers. Each .set-points element is one set's points, not a "25:18"
    # string, so pair the home and away rows by set index.
    set_scores = []
    raw_pairs = []
    team_rows = soup.select(".team-points-row")
    home_row = next((row for row in team_rows if "home" in row.get("class", [])), None)
    away_row = next((row for row in team_rows if "away" in row.get("class", [])), None)

    if home_row and away_row:
        home_points = [
            node.get_text(" ", strip=True) for node in home_row.select(".set-points")
        ]
        away_points = [
            node.get_text(" ", strip=True) for node in away_row.select(".set-points")
        ]
        for home_value, away_value in zip(home_points, away_points):
            if home_value.isdigit() and away_value.isdigit():
                a, b = int(home_value), int(away_value)
                raw_pairs.append((a, b))
                if a != b:
                    set_scores.append(f"{a}:{b}")

    result = {"time": kickoff, "set_scores": set_scores}
    if home_row and away_row:
        for side, row in [("home", home_row), ("away", away_row)]:
            value = row.select_one(".match-points")
            if value and value.get_text(strip=True).isdigit():
                result[side + "_sets"] = int(value.get_text(strip=True))
        if (
            "home_sets" in result
            and "away_sets" in result
            and max(result["home_sets"], result["away_sets"]) < 3
        ):
            count = result["home_sets"] + result["away_sets"]
            result["set_scores"] = [f"{a}:{b}" for a, b in raw_pairs[:count]]
            result["current_points"] = (
                f"{raw_pairs[count][0]}:{raw_pairs[count][1]}"
                if len(raw_pairs) > count
                else None
            )
    return result


def parse_table(soup, expected_teams=9):
    rows = []
    for row in soup.select("table tr"):
        cells = [
            re.sub(r"\s+", " ", cell.get_text(" ", strip=True))
            for cell in row.find_all(["td", "th"], recursive=False)
        ]
        # VolleyStation standings rows contain 18 cells:
        # rank, team, points, matches, sets won/lost, points won/lost,
        # ratios, then match-result counts (3-0, 3-1, 3-2, 2-3, 1-3, 0-3).
        if len(cells) < 18 or not cells[0].isdigit():
            continue
        try:
            rank = int(cells[0])
            points = int(cells[2])
            played = int(cells[3])
            sets_for, sets_against = int(cells[6]), int(cells[7])
            points_for, points_against = int(cells[8]), int(cells[9])
            result_counts = [int(value) for value in cells[12:18]]
            wins = sum(result_counts[:3])
            losses = sum(result_counts[3:])
            rows.append(
                {
                    "rank": rank,
                    "team": cells[1],
                    "played": played,
                    "points": points,
                    "wins": wins,
                    "losses": losses,
                    "sets_for": sets_for,
                    "sets_against": sets_against,
                    "points_for": points_for,
                    "points_against": points_against,
                }
            )
        except (ValueError, IndexError) as exc:
            print(
                f"Skipping invalid standings row {cells[:4]!r}: {exc}", file=sys.stderr
            )
    if rows and expected_teams is not None and len(rows) != expected_teams:
        print(
            f"Warning: expected {expected_teams} standings rows, parsed {len(rows)}",
            file=sys.stderr,
        )
    return rows


def parse_team_logos(soup, page_url, known_logos=None, *, fetch_page):
    """Extract team logos from standings and team profile links."""
    logos = dict(known_logos or {})

    def extract_url(node):
        for attr in (
            "src",
            "data-src",
            "data-lazy-src",
            "data-original",
            "data-image",
            "href",
        ):
            value = (node.get(attr) or "").strip()
            if (
                value
                and not value.startswith("data:")
                and not value.startswith("javascript:")
            ):
                return urljoin(page_url, value)
        for attr in ("srcset", "data-srcset"):
            value = (node.get(attr) or "").strip()
            if value:
                candidate = value.split(",")[0].strip().split()[0]
                if candidate and not candidate.startswith("data:"):
                    return urljoin(page_url, candidate)
        style = node.get("style", "")
        match = re.search(r"url\(['\"]?([^)'\"]+)", style)
        return urljoin(page_url, match.group(1).strip()) if match else ""

    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        team_cell = cells[1]
        name = re.sub(r"\s+", " ", team_cell.get_text(" ", strip=True)).strip()
        if not name or name.isdigit() or name.lower() in {"drużyna", "team"}:
            continue
        candidates = team_cell.select("img, source, [style*='background'], a")
        if not candidates:
            candidates = row.select("img, source, [style*='background']")
        for node in candidates:
            src = extract_url(node)
            if src and re.search(r"\.(?:svg|png|jpe?g|webp)(?:[?#].*)?$", src, re.I):
                logos[name] = src
                break

    # VolleyStation often links each team name to its own profile; logos can be
    # exposed there even when the standings table itself contains no image node.
    for anchor in soup.select('a[href*="/teams/"]'):
        href = urljoin(page_url, anchor.get("href", ""))
        if href.rstrip("/").endswith("/teams"):
            continue
        name = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip()
        # Some layouts wrap the badge in a link and keep the team name elsewhere
        # in the same standings row; use that row's team cell as a fallback.
        if not name:
            row = anchor.find_parent("tr")
            cells = row.find_all(["td", "th"], recursive=False) if row else []
            if len(cells) >= 2:
                name = re.sub(r"\s+", " ", cells[1].get_text(" ", strip=True)).strip()
        if not name or not href or name in logos:
            continue
        try:
            team_soup = fetch_page(href)
        except Exception as exc:
            print(
                f"Warning: couldn't inspect team profile for logo {name!r}: {exc}",
                file=sys.stderr,
            )
            continue

        # The official badge can be embedded in JSON/script markup instead of an <img>.
        # Search the raw profile HTML first for VolleyStation's canonical badge URL.
        html_text = str(team_soup).replace(r"\/", "/").replace(r"\u002F", "/")
        badge_match = re.search(
            r"(?:https?:)?//assets\.volleystation\.com/website/teams/\d+/badge\.png(?:[?#][^\s\"'<>]*)?",
            html_text,
            re.I,
        )
        if badge_match:
            logos[name] = urljoin(href, badge_match.group(0))
            print(f"Team logo mapped: {name} -> {logos[name]}", flush=True)
            continue

        image_candidates = []
        for selector in (
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            'img[alt*="logo" i]',
            'img[class*="logo" i]',
            "img[src]",
            "img[data-src]",
            "img[data-lazy-src]",
            "img[data-original]",
            "img[data-image]",
            "img[srcset]",
            '[style*="background-image"]',
        ):
            image_candidates.extend(team_soup.select(selector))
        for node in image_candidates:
            if node.name == "meta":
                src = urljoin(href, (node.get("content") or "").strip())
            else:
                src = extract_url(node)
            if not src or not re.search(
                r"\.(?:svg|png|jpe?g|webp)(?:[?#].*)?$", src, re.I
            ):
                continue
            if any(
                token in src.lower()
                for token in ("flag", "avatar", "default", "placeholder")
            ):
                continue
            logos[name] = src
            print(f"Team logo mapped: {name} -> {src}", flush=True)
            break

    return logos


# Match schema and source metadata

MATCH_FIELDS = {
    "id",
    "league",
    "competition",
    "date",
    "time",
    "date_iso",
    "round",
    "round_source_label",
    "phase",
    "status",
    "home",
    "away",
    "home_sets",
    "away_sets",
    "set_scores",
    "set_points",
    "home_points",
    "away_points",
    "current_points",
    "source_url",
    "home_team_id",
    "away_team_id",
    "home_logo",
    "away_logo",
    "venue",
    "match_number",
    "term_number",
    "details_checked_at",
    "broadcast",
}


def name_key(value):
    value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode()
        .casefold()
    )
    return re.sub(r"[^a-z0-9]", "", value)


def team_metadata(soup, url):
    teams = {}
    for image in soup.select("img[src]"):
        logo = urljoin(url, image["src"])
        found = re.search(
            r"/website/teams/(\d+)/badge\.(?:png|jpe?g|webp|svg)(?:[?#]|$)", logo, re.I
        )
        if not found:
            continue
        name = re.sub(r"\s+logo$", "", image.get("alt", ""), flags=re.I).strip()
        if not name:
            continue
        anchor = image.find_parent("a", href=True)
        profile = re.search(r"/teams/(\d+)", anchor["href"]) if anchor else None
        teams[name_key(name)] = {
            "name": name,
            "id": profile[1] if profile else None,
            "logo": logo,
            "badge_id": found[1],
            "id_source": urljoin(url, anchor["href"]) if profile else None,
        }
    return teams


def card_metadata(soup, url):
    result = {}
    for card in soup.select('a[href*="/matches/"]'):
        href = urljoin(url, card["href"])
        found = re.search(r"/matches/(\d+)(?:/|$)", href)
        if not found:
            continue
        tv = card.select_one(".stage.live .live-text")
        result[href] = {
            "source_match_id": found[1],
            "broadcast": ["TV"] if tv and tv.get_text(strip=True) == "TV" else [],
        }
    return result


def broadcast_urls(soup):
    """Only a match's embedded player proves a video association, not footer links."""
    urls = []
    for player in soup.select(".video-container iframe[src]"):
        src = player["src"]
        try:
            parsed = urlsplit("https:" + src if src.startswith("//") else src)
        except ValueError:
            continue
        if parsed.scheme != "https" or parsed.netloc.casefold() not in {
            "www.youtube.com",
            "youtube.com",
            "www.youtube-nocookie.com",
            "youtube-nocookie.com",
        }:
            continue
        video = re.fullmatch(r"/embed/([A-Za-z0-9_-]{11})/?", parsed.path)
        if video:
            url = "https://www.youtube.com/watch?v=" + video[1]
            if url not in urls:
                urls.append(url)
    return urls


def normalize(data, teams=None, cards=None):
    teams = teams or {}
    cards = cards or {}
    for team in data["teams"]:
        known = teams.get(name_key(team["name"]), {})
        team["id"] = known.get("id")
        team["id_source"] = known.get("id_source")
        team["badge_id"] = known.get("badge_id")
        if known.get("logo"):
            team["logo"] = known["logo"]
    index = {name_key(t["name"]): t for t in data["teams"]}
    for match in data["matches"]:
        original_source = match["source_url"]
        url = match.pop("match_url", None) or match["source_url"]
        observed = cards.get(url, {})
        match["league"] = data["league"]
        match["competition"] = data["competition"]
        match["date_iso"] = (
            datetime.strptime(match["date"], "%d.%m.%Y").date().isoformat()
        )
        match["phase"] = data.get("phase")
        match["round_source_label"] = "Runda"
        match["source_url"] = url
        found = re.search(r"/matches/(\d+)(?:/|$)", url)
        match["source_match_id"] = observed.get("source_match_id") or (
            found[1] if found else None
        )
        if match["source_match_id"]:
            match["legacy_id"] = match["id"]
            match["id"] = match["source_match_id"]
        match["match_number"] = str(match["match_number"])
        match.setdefault("time_source", original_source if match.get("time") else None)
        for side in ("home", "away"):
            team = index[name_key(match[side])]
            match[side + "_team_id"] = team.get("id")
            match[side + "_logo"] = team.get("logo")
        pairs = [
            tuple(map(int, score.split(":"))) for score in match.get("set_scores", [])
        ]
        match["set_points"] = [{"home": a, "away": b} for a, b in pairs]
        match["home_points"] = sum(a for a, b in pairs)
        match["away_points"] = sum(b for a, b in pairs)
        match.setdefault("current_points", None)
        if match["status"] != "live":
            match["current_points"] = None
        if match["status"] == "scheduled":
            match["home_sets"] = match["away_sets"] = 0
        match.setdefault("venue", None)
        match.setdefault("term_number", None)
        match.setdefault("details_checked_at", None)
        match["broadcast"] = observed.get("broadcast", match.get("broadcast", []))
    return data


# Local browser engines


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
            "enable_ws": True,
            # SB otherwise races for port 9222 when both leagues start together.
            "multi_proxy": True,
        }
        if self.binary:
            options["binary_location"] = self.binary
        if self.profile:
            options["user_data_dir"] = str(self.profile)
        proxy = inherited_proxy()
        if proxy:
            if proxy.username or proxy.password:
                raise ValueError("Proxy z logowaniem wymaga silnika Camoufox")
            # SB's `proxy=` path adds --ignore-certificate-errors. Pass Chrome's
            # native option instead, retaining the configured trust store.
            options["chromium_arg"] = [
                "--proxy-server=" + proxy.scheme + "://" + proxy.netloc
            ]
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
        if parsed.scheme != "https" or parsed.hostname not in {
            "pomorskie.volleystation.com",
            "2ligamezczyzn.volleystation.com",
        }:
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


# League import and validation


class InvalidFeed(ValueError):
    pass


def fixture_key(match):
    return str(match["round"]), str(match["match_number"])


def detail_identity(match):
    return (
        *fixture_key(match),
        *(match.get(k) for k in ("date", "home", "away", "home_sets", "away_sets")),
    )


def source_is_current(value, cfg, detail=False):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    expected_host = urlparse(cfg["base"]).hostname
    return (
        parsed.scheme == "https"
        and expected_host
        in {"pomorskie.volleystation.com", "2ligamezczyzn.volleystation.com"}
        and parsed.hostname == expected_host
        and (not detail or "/matches/" in parsed.path)
    )


def completed_sets(match):
    """Legal best-of-five set sequence; deuce has no arbitrary points ceiling."""
    home, away = match.get("home_sets"), match.get("away_sets")
    if (
        type(home) is not int
        or type(away) is not int
        or sorted((home, away)) not in [[0, 3], [1, 3], [2, 3]]
    ):
        raise InvalidFeed("Nieprawidłowy wynik meczu " + str(match.get("id")))
    scores = match.get("set_scores") or []
    if len(scores) != home + away:
        raise InvalidFeed("Niekompletne sety " + str(match.get("id")))
    pairs = []
    wins = [0, 0]
    for index, score in enumerate(scores):
        if not isinstance(score, str) or not re.fullmatch(r"\d+:\d+", score):
            raise InvalidFeed("Nieprawidłowy zapis seta")
        a, b = map(int, score.split(":"))
        hi, lo = max(a, b), min(a, b)
        target = 15 if index == 4 else 25
        if not (hi >= target and hi - lo >= 2 and (hi == target or hi - lo == 2)):
            raise InvalidFeed("Nielegalny wynik seta " + score)
        wins[int(b > a)] += 1
        pairs.append((a, b))
        if max(wins) == 3 and index != len(scores) - 1:
            raise InvalidFeed("Set rozegrany po zakończeniu meczu")
    if wins != [home, away]:
        raise InvalidFeed("Punkty setów nie zgadzają się z wynikiem meczu")
    return pairs


def live_sets(match):
    home, away = match.get("home_sets"), match.get("away_sets")
    if (
        type(home) is not int
        or type(away) is not int
        or not 0 <= home < 3
        or not 0 <= away < 3
    ):
        raise InvalidFeed("Nieprawidłowy wynik trwającego meczu")
    pairs = []
    wins = [0, 0]
    for index, value in enumerate(match.get("set_scores", [])):
        a, b = map(int, value.split(":"))
        hi, lo = max(a, b), min(a, b)
        target = 15 if index == 4 else 25
        if not (hi >= target and hi - lo >= 2 and (hi == target or hi - lo == 2)):
            raise InvalidFeed("Niepełny set nie może być zapisany jako zakończony")
        pairs.append((a, b))
        wins[int(b > a)] += 1
    if wins != [home, away]:
        raise InvalidFeed("Sety nie odpowiadają wynikowi LIVE")
    return pairs


def standings_discrepancies(matches, table):
    counts = defaultdict(Counter)
    for match in matches:
        if match["status"] != "finished":
            continue
        pairs = completed_sets(match)
        hs, vs = match["home_sets"], match["away_sets"]
        for name, a, b, pf, pa in [
            (match["home"], hs, vs, sum(p[0] for p in pairs), sum(p[1] for p in pairs)),
            (match["away"], vs, hs, sum(p[1] for p in pairs), sum(p[0] for p in pairs)),
        ]:
            counts[name].update(
                played=1,
                wins=int(a > b),
                losses=int(a < b),
                sets_for=a,
                sets_against=b,
                points_for=pf,
                points_against=pa,
                points=(2 if a > b else 1) if min(a, b) == 2 else (3 if a > b else 0),
            )
    keys = (
        "played",
        "wins",
        "losses",
        "sets_for",
        "sets_against",
        "points_for",
        "points_against",
        "points",
    )
    return {
        row["team"]: [
            k
            for k in keys
            if type(row.get(k)) is not int or row[k] != counts[row["team"]][k]
        ]
        for row in table
        if any(
            type(row.get(k)) is not int or row[k] != counts[row["team"]][k]
            for k in keys
        )
    }


def validate_feed(
    data,
    previous=None,
    *,
    expected_teams=9,
    min_matches=60,
    expected_source=SCHEDULE_URL,
    expected_league="pomorska3liga",
):
    if data.get("league") != expected_league or data.get("source") != expected_source:
        raise InvalidFeed("Inna liga lub faza rozgrywek")
    if data.get("source_policy") != "volleystation_only":
        raise InvalidFeed("Feed nie potwierdza wyłącznego źródła VolleyStation")
    matches, teams, table = (
        data.get("matches", []),
        data.get("teams", []),
        data.get("table", []),
    )
    if (
        len(matches) < min_matches
        or len(teams) != expected_teams
        or len(table) != expected_teams
    ):
        raise InvalidFeed("Niekompletna liczba meczów, drużyn lub wierszy tabeli")
    names = {t["name"] for t in teams}
    if len(names) != expected_teams or {row["team"] for row in table} != names:
        raise InvalidFeed("Tabela nie odpowiada drużynom")
    if sorted(row["rank"] for row in table) != list(range(1, expected_teams + 1)):
        raise InvalidFeed("Nieprawidłowe miejsca w tabeli")
    if any(urlparse(t.get("logo", "")).scheme not in ("http", "https") for t in teams):
        raise InvalidFeed("Brak logotypu drużyny")
    table_fields = (
        "played",
        "wins",
        "losses",
        "sets_for",
        "sets_against",
        "points_for",
        "points_against",
        "points",
    )
    if any(type(row.get(key)) is not int for row in table for key in table_fields):
        raise InvalidFeed("Niekompletne wartości tabeli źródłowej")
    ids = set()
    keys = set()
    for match in matches:
        source_cfg = {"base": expected_source}
        if not source_is_current(match.get("source_url"), source_cfg):
            raise InvalidFeed("Mecz pochodzi spoza VolleyStation")
        if match.get("venue") is not None and not source_is_current(
            match.get("venue_source_url"), source_cfg
        ):
            raise InvalidFeed("Hala nie ma potwierdzenia VolleyStation")
        if match.get("broadcast_urls") and not source_is_current(
            match.get("broadcast_source_url"), source_cfg, detail=True
        ):
            raise InvalidFeed(
                "Transmisja nie ma potwierdzenia na stronie meczu VolleyStation"
            )
        if not source_is_current(match.get("time_source"), source_cfg):
            raise InvalidFeed("Godzina spoza VolleyStation lub bez pochodzenia")
        if match["status"] == "finished" and not source_is_current(
            match.get("set_scores_source"), source_cfg, detail=True
        ):
            raise InvalidFeed("Punkty setów spoza strony meczu VolleyStation")
        if match["id"] in ids or fixture_key(match) in keys:
            raise InvalidFeed("Powtórzony mecz")
        ids.add(match["id"])
        keys.add(fixture_key(match))
        datetime.strptime(match["date"], "%d.%m.%Y")
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", match.get("time") or ""):
            raise InvalidFeed("Brak prawidłowej godziny meczu")
        if (
            match["home"] not in names
            or match["away"] not in names
            or match["home"] == match["away"]
        ):
            raise InvalidFeed("Nieprawidłowe drużyny meczu")
        if match["status"] == "finished":
            completed_sets(match)
        elif match["status"] == "live":
            live_sets(match)
        elif match["status"] != "scheduled":
            raise InvalidFeed("Nieobsługiwany status meczu")
    if previous:
        if previous.get("source") != expected_source:
            raise InvalidFeed("Cache pochodzi z innej fazy rozgrywek")
        old_keys = {fixture_key(m) for m in previous.get("matches", [])}
        if not old_keys.issubset(keys):
            raise InvalidFeed("Zniknęły mecze z poprzedniego feedu")
        old_results = {
            fixture_key(m)
            for m in previous.get("matches", [])
            if m.get("status") == "finished"
        }
        if not old_results.issubset(
            {fixture_key(m) for m in matches if m["status"] == "finished"}
        ):
            raise InvalidFeed("Zniknęły zakończone wyniki; wymagana kontrola źródła")
    return {
        "matches": len(matches),
        "finished": sum(m["status"] == "finished" for m in matches),
        "teams": len(teams),
    }


def build_feed(
    fetch,
    previous=None,
    refresh_details=False,
    detail_cache=None,
    on_detail=None,
    config=None,
    known_teams=None,
):
    cfg = {
        "base": BASE,
        "competition": "Pomorska III Liga Męska",
        "league": "pomorska3liga",
        "expected_teams": 9,
        "min_matches": 60,
        "phase": "Pomorska III Liga Męska",
        **(config or {}),
    }
    schedule_url = cfg["base"] + "/schedule/"
    results_url = cfg["base"] + "/results/"
    standings_url = cfg["base"] + "/standings/"
    previous = previous or {}
    if previous and previous.get("source") != schedule_url:
        raise InvalidFeed("Cache pochodzi z innej fazy rozgrywek")
    schedule_soup = fetch(schedule_url)
    results_soup = fetch(results_url)
    schedule = parse_matches(schedule_soup, schedule_url)
    results = parse_matches(results_soup, results_url)
    observed_teams = {
        **(known_teams or {}),
        **team_metadata(schedule_soup, schedule_url),
        **team_metadata(results_soup, results_url),
    }
    if known_teams is None:
        previous_teams = {
            name_key(t["name"]): t
            for t in previous.get("teams", [])
            if t.get("id") and t.get("id_source")
        }
        if len(previous_teams) == cfg["expected_teams"]:
            official_teams = previous_teams
        else:
            official_teams = team_metadata(
                fetch(cfg["base"] + "/teams/"), cfg["base"] + "/teams/"
            )
    else:
        official_teams = known_teams
    for key, known in official_teams.items():
        observed_teams.setdefault(key, dict(known))
        observed_teams[key].update(
            id=known.get("id"),
            id_source=known.get("id_source"),
            badge_id=known.get("badge_id"),
        )
    observed_cards = {
        **card_metadata(schedule_soup, schedule_url),
        **card_metadata(results_soup, results_url),
    }
    standings_soup = fetch(standings_url)
    table = parse_table(standings_soup, expected_teams=cfg["expected_teams"])
    if len(table) != cfg["expected_teams"]:
        raise InvalidFeed("Niekompletna tabela źródłowa")
    by_key = {fixture_key(m): m for m in schedule}
    if len(by_key) != len(schedule) or len({fixture_key(m) for m in results}) != len(
        results
    ):
        raise InvalidFeed("Duplikaty w źródle")
    for result in results:
        if result["status"] != "finished":
            raise InvalidFeed("Nieprawidłowa strona wyników")
        fixture = by_key.get(fixture_key(result), {})
        result = {**fixture, **result}
        if not result.get("time") and fixture.get("time"):
            result["time"] = fixture["time"]
        by_key[fixture_key(result)] = result
    matches = list(by_key.values())
    cached = {
        detail_identity(m): m
        for m in previous.get("matches", [])
        if m.get("status") == "finished"
        and source_is_current(m.get("set_scores_source"), cfg, detail=True)
    }
    cached.update(
        {
            detail_identity(m): m
            for m in (detail_cache or [])
            if m.get("status") == "finished"
            and source_is_current(m.get("set_scores_source"), cfg, detail=True)
        }
    )
    reused = []
    detail_requests = 0

    def detail(match):
        nonlocal detail_requests
        detail_requests += 1
        soup = fetch(match["match_url"])
        values = parse_match_detail(soup)
        # A live card can replace its TV label with "Na żywo". The player
        # remains on the match page, which is already being read for scores.
        match["broadcast_urls"] = broadcast_urls(soup)
        match["broadcast_source_url"] = match["match_url"]
        match["broadcast_checked_at"] = now()
        match["set_scores"] = values["set_scores"]
        match["current_points"] = values.get("current_points")
        if (
            match["status"] in ("live", "scheduled")
            and "home_sets" in values
            and "away_sets" in values
        ):
            match["home_sets"] = values["home_sets"]
            match["away_sets"] = values["away_sets"]
            if max(values["home_sets"], values["away_sets"]) == 3:
                match["status"] = "finished"
            elif values["home_sets"] + values["away_sets"] or values.get(
                "current_points"
            ) not in (None, "0:0"):
                match["status"] = "live"
        if not match.get("time"):
            match["time"] = values["time"]
            match["time_source"] = match["match_url"]
        if match["status"] == "live":
            live_sets(match)
        elif match["status"] == "finished":
            completed_sets(match)
        match["details_checked_at"] = now()
        match["set_scores_source"] = match["match_url"]
        if on_detail and match["status"] == "finished":
            on_detail(copy.deepcopy(match))

    for match in matches:
        if match["status"] == "live" or (
            match["status"] == "scheduled" and not match.get("time")
        ):
            detail(match)
            continue
        if match["status"] != "finished":
            continue
        if match.get("set_scores") and match.get("time") and not refresh_details:
            completed_sets(match)
            reused.append(match)
            continue
        old = cached.get(detail_identity(match))
        if old and not refresh_details:
            try:
                completed_sets(old)
                match["set_scores"] = copy.deepcopy(old["set_scores"])
                match["set_scores_source"] = old["set_scores_source"]
                match["details_checked_at"] = old.get("details_checked_at")
                if not match.get("time") and source_is_current(
                    old.get("time_source"), cfg
                ):
                    match["time"] = old.get("time")
                    match["time_source"] = old["time_source"]
                if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", match.get("time") or ""):
                    reused.append(match)
                    continue
            except (InvalidFeed, TypeError, ValueError):
                pass
        detail(match)
    # Visible TV markers may occur on scheduled fixtures and cached results,
    # neither of which otherwise requires a detail request. Refresh links every
    # cycle, including archived videos; a marker alone never invents a URL.
    broadcast_requests = 0
    previous_streams = {
        (fixture_key(m), m["date"], m["home"], m["away"]): m
        for m in previous.get("matches", [])
        if m.get("broadcast_urls")
        and source_is_current(m.get("broadcast_source_url"), cfg, detail=True)
    }
    for match in matches:
        known_stream = previous_streams.get(
            (fixture_key(match), match["date"], match["home"], match["away"])
        )
        if (
            observed_cards.get(match["match_url"], {}).get("broadcast")
            or match.get("broadcast_urls")
            or known_stream
        ):
            match["broadcast_urls"] = broadcast_urls(fetch(match["match_url"]))
            match["broadcast_source_url"] = match["match_url"]
            match["broadcast_checked_at"] = now()
            broadcast_requests += 1
    known = {
        t["name"]: t["logo"]
        for t in previous.get("teams", [])
        if t.get("name") and t.get("logo")
    }
    known.update({t["name"]: t["logo"] for t in observed_teams.values()})
    logos = parse_team_logos(
        standings_soup, standings_url, known_logos=known, fetch_page=fetch
    )
    matches.sort(
        key=lambda m: (
            datetime.strptime(m["date"], "%d.%m.%Y"),
            m["time"] or "99:99",
            m["round"],
            m["match_number"],
        )
    )
    names = sorted({m[k] for m in matches for k in ("home", "away")}, key=str.casefold)
    data = {
        "league": cfg["league"],
        "source_policy": "volleystation_only",
        "competition": cfg["competition"],
        "phase": cfg["phase"],
        "source": schedule_url,
        "results_source": results_url,
        "standings_source": standings_url,
        "updated_at": now(),
        "teams": [{"name": name, "logo": logos.get(name, "")} for name in names],
        "matches": matches,
        "table": table,
    }
    normalize(data, observed_teams, observed_cards)
    # Tables and results are independent source publications. Never rewrite or
    # reject the published table to make it agree with calculated standings.
    data["source_table_discrepancies"] = standings_discrepancies(matches, table)
    metrics = validate_feed(
        data,
        previous,
        expected_teams=cfg["expected_teams"],
        min_matches=cfg["min_matches"],
        expected_source=schedule_url,
        expected_league=cfg["league"],
    )
    metrics.update(
        reused_details=len(reused),
        refetched_cached_details=0,
        detail_requests=detail_requests,
        broadcast_requests=broadcast_requests,
    )
    return data, metrics


def validate_output(data, previous=None):
    if data.get("league") == "second":
        return validate_second(data, previous)
    return validate_feed(data, previous)


# All five II liga groups

VOLLEYSTATION_TEAMS_URL = "https://2ligamezczyzn.volleystation.com/pl/teams/"

COUNTS = {1: 10, 2: 11, 3: 12, 4: 10, 5: 11}


def group_configs(soup):
    configs = {}
    for anchor in soup.select('a[href*="phase-"]'):
        label = " ".join(anchor.get_text(" ", strip=True).split())
        match = re.fullmatch(r"2 liga mężczyzn grupa ([1-5])", label, re.I)
        if not match:
            continue
        number = int(match[1])
        base = urljoin(VOLLEYSTATION_TEAMS_URL, anchor["href"]).rsplit("/teams/", 1)[0]
        configs[number] = {
            "base": base,
            "league": "second",
            "competition": "II Liga Mężczyzn",
            "expected_teams": COUNTS[number],
            "min_matches": COUNTS[number] * (COUNTS[number] - 1),
            "phase": label,
            "group": f"Grupa {number}",
        }
    if set(configs) != set(COUNTS):
        raise InvalidFeed("Nie znaleziono pięciu faz grupowych II ligi")
    return configs


def validate_second(data, previous=None):
    if data.get("league") != "second" or data.get("source") != VOLLEYSTATION_TEAMS_URL:
        raise InvalidFeed("Nieprawidłowe źródło II ligi")
    if data.get("source_policy") != "volleystation_only":
        raise InvalidFeed("II liga musi pochodzić wyłącznie z VolleyStation")
    groups = data.get("groups", [])
    if len(groups) != 5 or {g["name"] for g in groups} != {
        f"Grupa {n}" for n in COUNTS
    }:
        raise InvalidFeed("Niekompletne grupy II ligi")
    metrics = {"matches": 0, "finished": 0, "teams": 0}
    for group in groups:
        number = int(group["name"].split()[-1])
        n = COUNTS[number]
        old = next(
            (
                g
                for g in (previous or {}).get("groups", [])
                if g["name"] == group["name"] and g.get("source") == group["source"]
            ),
            None,
        )
        values = validate_feed(
            group,
            old,
            expected_teams=n,
            min_matches=n * (n - 1),
            expected_source=group["source"],
            expected_league="second",
        )
        if len(group["matches"]) != n * (n - 1):
            raise InvalidFeed("Niepełny sezon zasadniczy " + group["name"])
        for k in metrics:
            metrics[k] += values[k]
    return metrics


def build_second(
    fetch, previous=None, refresh_details=False, detail_cache=None, on_detail=None
):
    teams_page = fetch(VOLLEYSTATION_TEAMS_URL)
    configs = group_configs(teams_page)
    teams = team_metadata(teams_page, VOLLEYSTATION_TEAMS_URL)
    groups = []
    extra = {"detail_requests": 0, "reused_details": 0, "refetched_cached_details": 0}
    for number, cfg in sorted(configs.items()):
        old = next(
            (
                g
                for g in (previous or {}).get("groups", [])
                if g["name"] == cfg["group"]
                and g.get("source") == cfg["base"] + "/schedule/"
            ),
            {},
        )
        data, metrics = build_feed(
            fetch,
            old,
            refresh_details,
            detail_cache,
            on_detail,
            config=cfg,
            known_teams=teams,
        )
        data["name"] = cfg["group"]
        for match in data["matches"]:
            match["group"] = cfg["group"]
        groups.append(data)
        for k in extra:
            extra[k] += metrics[k]
    data = {
        "league": "second",
        "competition": "II Liga Mężczyzn",
        "source": VOLLEYSTATION_TEAMS_URL,
        "results_source": VOLLEYSTATION_TEAMS_URL,
        "source_policy": "volleystation_only",
        "updated_at": now(),
        "groups": groups,
    }
    metrics = validate_second(data, previous)
    metrics.update(extra)
    return data, metrics


# Isolated browser process


def worker_main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--engine", choices=("seleniumbase", "camoufox"), required=True)
    p.add_argument(
        "--league", choices=("pomorska3liga", "second"), default="pomorska3liga"
    )
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--events", type=Path, required=True)
    p.add_argument("--browser")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--refresh-details", action="store_true")
    p.add_argument("--camoufox-ca", type=Path)
    p.add_argument("--document-budget", type=int, default=40)
    args = p.parse_args(argv)
    report = {"engine": args.engine, "started_at": now(), "ok": False}

    def record(event):

        append_event(args.events, {"engine": args.engine, **event})

    options = {"profile": args.candidate.parent / (args.engine + "-profile")}
    if args.engine == "camoufox":
        options["ca_certificate"] = args.camoufox_ca
    browser = (SeleniumBrowser if args.engine == "seleniumbase" else CamoufoxBrowser)(
        args.browser, args.headless, **options
    )
    session = Session(browser, record, budget=args.document_budget)
    try:
        previous = read_json(args.previous, {})
        if args.league == "second":
            builder = build_second
            cache_source = VOLLEYSTATION_TEAMS_URL
        else:
            builder = build_feed
            cache_source = SCHEDULE_URL
        cache_path = args.events.parent / "details-cache.json"
        try:
            cache = read_json(cache_path, {})
        except ValueError:
            record({"event": "detail_cache_unreadable"})
            cache = {}
        cached_matches = (
            cache.get("matches", [])
            if isinstance(cache, dict) and cache.get("source") == cache_source
            else []
        )
        saved = {detail_identity(m): m for m in cached_matches}

        def remember(match):
            match.pop("match_url", None)
            saved[detail_identity(match)] = match
            atomic_json(
                cache_path,
                {"source": cache_source, "matches": list(saved.values())[-600:]},
            )

        browser.start()
        data, metrics = builder(
            session.fetch,
            previous,
            args.refresh_details,
            detail_cache=cached_matches,
            on_detail=remember,
        )
        atomic_json(args.candidate, data)
        report.update(ok=True, metrics=metrics)
    except Exception as error:
        report.update(
            error=type(error).__name__ + ": " + safe_error(error),
            retry_after=max(getattr(error, "retry_after", 0), session.retry_after),
        )
    finally:
        try:
            browser.close()
        except Exception as error:
            report["close_error"] = safe_error(error)
        report.update(finished_at=now(), documents=session.requests)
        atomic_json(args.report, report)
        record({"event": "attempt_finished", **report})
    return 0 if report["ok"] else 1


# CLI, failover and atomic publication

ROOT = Path(__file__).resolve().parents[1]


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp bez strefy czasowej")
    return parsed.astimezone(timezone.utc)


def append_event(path, event):
    # Parent and worker write serially; retain at most four 1 MB event files.
    import logging
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(
        path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    try:
        handler.emit(
            logging.LogRecord(
                "local-scraper",
                logging.INFO,
                "",
                0,
                json.dumps({"at": now(), **event}, ensure_ascii=False),
                (),
                None,
            )
        )
    finally:
        handler.close()


def run_worker(engine, previous, candidate, report, events, args):
    import psutil

    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--engine",
        engine,
        "--league",
        args.league,
        "--previous",
        str(previous),
        "--candidate",
        str(candidate),
        "--report",
        str(report),
        "--events",
        str(events),
        "--document-budget",
        str(args.document_budget),
    ]
    if args.browser:
        command += ["--browser", args.browser]
    if args.headless:
        command += ["--headless"]
    if args.refresh_details:
        command += ["--refresh-details"]
    if args.camoufox_ca:
        command += ["--camoufox-ca", str(args.camoufox_ca)]
    started = time.monotonic()
    children = {}
    timed_out = False
    with tempfile.TemporaryFile() as diagnostic:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=diagnostic,
            stderr=diagnostic,
            start_new_session=os.name != "nt",
        )
        parent = psutil.Process(process.pid)
        try:
            while process.poll() is None:
                try:
                    for child in parent.children(recursive=True):
                        children[(child.pid, child.create_time())] = child
                except psutil.Error:
                    pass
                remaining = args.timeout - (time.monotonic() - started)
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    process.wait(timeout=min(1, remaining))
                except subprocess.TimeoutExpired:
                    pass
        finally:
            # Also runs on Ctrl+C: close the browser tree before releasing the feed lock.
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            for child in reversed(list(children.values())):
                try:
                    child.terminate()
                except psutil.Error:
                    pass
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            _, alive = psutil.wait_procs(list(children.values()), timeout=2)
            for child in alive:
                try:
                    child.kill()
                except psutil.Error:
                    pass
            psutil.wait_procs(alive, timeout=2)
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if timed_out:
            return {
                "engine": engine,
                "ok": False,
                "error": f"Przekroczono limit {args.timeout} s",
            }
        try:
            result = read_json(report)
        except (ValueError, OSError):
            result = None
        if not isinstance(result, dict):
            diagnostic.seek(0, 2)
            size = diagnostic.tell()
            diagnostic.seek(max(0, size - 2000))
            detail = safe_error(diagnostic.read().decode("utf-8", errors="replace"))
            return {
                "engine": engine,
                "ok": False,
                "error": f"Proces zakończył się kodem {process.returncode}: {detail}",
            }
        if process.returncode != 0:
            result["ok"] = False
        return result


def freshness(output, max_age):
    try:
        data = read_json(output)
        if data is None:
            return {"feed_status": "missing", "age_seconds": None}
        validate_output(data)
        age = (
            datetime.now(timezone.utc) - timestamp(data["updated_at"])
        ).total_seconds()
        if age < -300:
            raise ValueError("Data aktualizacji jest w przyszłości")
        return {
            "feed_status": "fresh" if age <= max_age else "stale",
            "age_seconds": max(0, round(age)),
            "feed_updated_at": data["updated_at"],
        }
    except (ValueError, TypeError, KeyError, OSError) as error:
        return {
            "feed_status": "invalid",
            "age_seconds": None,
            "feed_error": safe_error(error),
        }


def cycle(args, execute=run_worker, sleep=time.sleep):
    state = read_json(args.state_dir / "status.json", {})
    retry_at = state.get("next_attempt_at")
    if retry_at and timestamp(retry_at) > datetime.now(timezone.utc):
        print(
            f"Przerwa po błędzie do {retry_at}. Feed pozostaje bez zmian.",
            file=sys.stderr,
        )
        return False
    previous_path = args.output if args.output.exists() else args.seed
    previous = read_json(previous_path, {}) if previous_path else {}
    if not isinstance(previous, dict):
        raise ValueError("Cache nie jest obiektem JSON")
    state.update(last_attempt_at=now(), status="running", output=str(args.output))
    atomic_json(args.state_dir / "status.json", state)
    engines = ("seleniumbase", "camoufox") if args.engine == "auto" else (args.engine,)
    attempts = []
    events = args.state_dir / "events.jsonl"
    retry_after = 0
    try:
        with tempfile.TemporaryDirectory(
            prefix="attempt-", dir=args.state_dir
        ) as temporary:
            folder = Path(temporary)
            previous_file = folder / "previous.json"
            atomic_json(previous_file, previous)
            for index, engine in enumerate(engines):
                if index:
                    sleep(args.fallback_delay)
                candidate = folder / (engine + ".json")
                report = folder / (engine + "-report.json")
                append_event(events, {"event": "attempt_started", "engine": engine})
                publishing = False
                try:
                    attempt = execute(
                        engine, previous_file, candidate, report, events, args
                    )
                    if attempt.get("ok"):
                        data = read_json(candidate)
                        metrics = validate_output(data, previous)
                        age = (
                            datetime.now(timezone.utc) - timestamp(data["updated_at"])
                        ).total_seconds()
                        if not -300 <= age <= args.timeout + 60:
                            raise ValueError("Kandydat ma nieaktualny znacznik czasu")
                        publishing = True
                        atomic_json(args.output, data)
                        if args.public_output:
                            atomic_json(args.public_output, data)
                        state.update(
                            status="ok",
                            last_success_at=data["updated_at"],
                            last_success_engine=engine,
                            consecutive_failures=0,
                            next_attempt_at=None,
                            attempts=attempts + [attempt],
                            metrics=metrics,
                        )
                        atomic_json(args.state_dir / "status.json", state)
                        append_event(
                            events, {"event": "published", "engine": engine, **metrics}
                        )
                        print(
                            f"OK: {engine}; {metrics['matches']} meczów, {metrics['finished']} wyników; {args.output}",
                            flush=True,
                        )
                        return True
                except Exception as error:
                    attempt = {
                        "engine": engine,
                        "ok": False,
                        "error": type(error).__name__ + ": " + safe_error(error),
                    }
                attempts.append(attempt)
                retry_after = max(retry_after, attempt.get("retry_after", 0))
                append_event(events, {"event": "attempt_failed", **attempt})
                if retry_after or publishing:
                    break  # A disk failure cannot be fixed by another browser.
    except BaseException:
        state.update(status="interrupted", attempts=attempts)
        atomic_json(args.state_dir / "status.json", state)
        raise
    failures = state.get("consecutive_failures", 0) + 1
    delay = max(retry_after, min(3600, 300 * 2 ** min(failures - 1, 4)))
    state.update(
        status="error",
        consecutive_failures=failures,
        attempts=attempts,
        next_attempt_at=(
            datetime.now(timezone.utc) + timedelta(seconds=delay)
        ).isoformat(),
    )
    atomic_json(args.state_dir / "status.json", state)
    print(
        "ALERT: aktualizacja lub publikacja nie została ukończona. "
        + "; ".join(a.get("error", "nieznany błąd") for a in attempts),
        file=sys.stderr,
        flush=True,
    )
    return False


def arguments(argv=None):
    p = argparse.ArgumentParser(
        description="Lokalny scraper II i Pomorskiej III ligi: UC + CDP → Camoufox."
    )
    p.add_argument(
        "--league",
        choices=("pomorska3liga", "second"),
        default="pomorska3liga",
        help="Pomorska III liga lub wszystkie grupy II ligi.",
    )
    p.add_argument("--output", type=Path)
    p.add_argument(
        "--seed",
        type=Path,
        help="Poprzedni feed, używany tylko gdy --output jeszcze nie istnieje.",
    )
    p.add_argument(
        "--public-output",
        type=Path,
        help="Dodatkowa atomowa kopia dla lokalnej aplikacji, np. public/data/pomorska3liga.json.",
    )
    p.add_argument("--state-dir", type=Path)
    p.add_argument(
        "--engine", choices=("auto", "seleniumbase", "camoufox"), default="auto"
    )
    p.add_argument("--browser", help="Opcjonalna ścieżka do Chrome/Chromium.")
    p.add_argument(
        "--camoufox-ca",
        type=Path,
        help="Opcjonalny zaufany certyfikat CA proxy dla prywatnego profilu Camoufox.",
    )
    p.add_argument(
        "--headless",
        action="store_true",
        help="Tryb diagnostyczny; zalecana przeglądarka z interfejsem.",
    )
    p.add_argument(
        "--refresh-details",
        action="store_true",
        help="Pobierz ponownie szczegóły zakończonych meczów.",
    )
    p.add_argument(
        "--watch", action="store_true", help="Powtarzaj aktualizacje do Ctrl+C."
    )
    p.add_argument(
        "--every",
        type=int,
        default=900,
        help="Odstęp po zakończeniu cyklu w sekundach, minimum 300.",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Limit czasu na jeden silnik: 30–1800 s.",
    )
    p.add_argument(
        "--document-budget",
        type=int,
        default=40,
        help="Limit dokumentów na silnik: 3–120; domyślnie 40.",
    )
    p.add_argument(
        "--fallback-delay",
        type=int,
        default=30,
        help="Przerwa przed silnikiem zapasowym: 15–300 s.",
    )
    p.add_argument(
        "--status",
        action="store_true",
        help="Pokaż stan i wiek feedu bez uruchamiania przeglądarki.",
    )
    p.add_argument(
        "--max-age",
        type=int,
        default=1800,
        help="Próg świeżości feedu w sekundach dla --status.",
    )
    args = p.parse_args(argv)
    if (
        args.every < 300
        or not 30 <= args.timeout <= 1800
        or not 15 <= args.fallback_delay <= 300
        or args.max_age < 1
        or not 3 <= args.document_budget <= 120
    ):
        p.error("Nieprawidłowe odstępy, limit czasu lub próg świeżości.")
    args.output = (
        args.output
        or ROOT
        / "data"
        / ("2liga.json" if args.league == "second" else "pomorska3liga.json")
    ).resolve()
    if args.public_output:
        args.public_output = args.public_output.resolve()
    if args.seed:
        args.seed = args.seed.resolve()
    if args.camoufox_ca:
        args.camoufox_ca = args.camoufox_ca.resolve()
        if not args.camoufox_ca.is_file():
            p.error("Nie znaleziono pliku certyfikatu CA.")
    key = hashlib.sha256(str(args.output).encode()).hexdigest()[:12]
    args.state_dir = (args.state_dir or ROOT / ".local-scraper" / key).resolve()
    return args


def main(argv=None):
    args = arguments(argv)
    if args.status:
        state = read_json(args.state_dir / "status.json", {})
        result = {**state, **freshness(args.output, args.max_age)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return (
            0
            if result["feed_status"] == "fresh" and result.get("status") == "ok"
            else 1
        )
    from filelock import FileLock, Timeout

    args.state_dir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(args.output) + ".local-scraper.lock")
    try:
        with lock.acquire(timeout=0):
            while True:
                ok = cycle(args)
                if not args.watch:
                    return 0 if ok else 1
                time.sleep(args.every)
    except Timeout:
        print(
            "Ten feed aktualizuje już inny proces lokalnego scrapera.", file=sys.stderr
        )
        return 2
    except KeyboardInterrupt:
        print("Zatrzymano lokalny scraper.", file=sys.stderr)
        return 130
    except Exception as error:
        print("ALERT: " + safe_error(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]:
        raise SystemExit(worker_main(sys.argv[2:]))
    raise SystemExit(main())
