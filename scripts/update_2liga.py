#!/usr/bin/env python3
"""Fetch all II Liga Mężczyzn groups from the official VolleyStation pages."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

ROOT_URL = "https://2ligamezczyzn.volleystation.com/pl/teams/"
OUT = Path("data/2liga.json")
LEAGUE_NAME = "II Liga Mężczyzn"
MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
    "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8,
    "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
}
def fetch(url):
    """Fetch VolleyStation in a real Puppeteer session, retaining warm-up cookies."""
    import subprocess

    node_script = r"""
    const puppeteer = require('puppeteer-extra');
    const StealthPlugin = require('puppeteer-extra-plugin-stealth');
    puppeteer.use(StealthPlugin());

    (async () => {
      let browser;
      try {
        browser = await puppeteer.launch({
          headless: true,
          args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage'
          ]
        });
        const page = await browser.newPage();
        const chromeVersion = (await browser.version()).match(/Chrome\/(\d+\.\d+\.\d+\.\d+)/)?.[1];
        if (!chromeVersion) throw new Error('Could not determine Chromium version');

        // Keep the User-Agent aligned with the actual Chromium binary. Avoid
        // randomized fingerprints, which can make a session less consistent.
        await page.setUserAgent(
          'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/' +
          chromeVersion + ' Safari/537.36'
        );
        await page.setViewport({ width: 1365, height: 900, deviceScaleFactor: 1 });
        await page.setExtraHTTPHeaders({
          'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7'
        });
        page.setDefaultNavigationTimeout(60000);

        const targetUrl = new URL(process.argv[1]);
        const landingUrl = targetUrl.origin + '/pl/teams/';

        // Establish first-party cookies on the league site before visiting a
        // deeper route. The target request then uses the same page/session.
        if (targetUrl.pathname.replace(/\/+$/, '') !== '/pl/teams') {
          const landingResponse = await page.goto(landingUrl, {
            waitUntil: 'domcontentloaded',
            timeout: 60000
          });
          try { await page.waitForNetworkIdle({ timeout: 15000 }); } catch (_) {}
          await new Promise(resolve => setTimeout(resolve, 2000));
          const landingState = await page.evaluate(() => ({
            title: document.title || '',
            body: (document.body?.innerText || '').slice(0, 500)
          }));
          if (landingResponse && landingResponse.status() === 403) {
            throw new Error('League landing page returned HTTP 403: ' + landingState.title + ' ' + landingState.body);
          }
        }

        let response = await page.goto(process.argv[1], {
          waitUntil: 'domcontentloaded',
          timeout: 60000
        });
        try { await page.waitForNetworkIdle({ timeout: 20000 }); } catch (_) {}
        await new Promise(resolve => setTimeout(resolve, 1500));

        // Wait for a legitimate site challenge to finish; do not inject scripts
        // or skip verification. If it remains, return diagnostics and fail closed.
        for (let i = 0; i < 20; i++) {
          const state = await page.evaluate(() => ({
            title: document.title || '',
            body: (document.body?.innerText || '').slice(0, 500)
          }));
          const challenge = /just a moment|verify you are human|checking your browser|cierpliwości/i.test(
            state.title + ' ' + state.body
          );
          if (!challenge) break;
          await new Promise(resolve => setTimeout(resolve, 1500));
        }

        const result = {
          status: response ? response.status() : null,
          title: await page.title(),
          body: (await page.evaluate(() => document.body ? document.body.innerText : '')).slice(0, 500),
          html: await page.content()
        };
        process.stdout.write(JSON.stringify(result));
      } catch (error) {
        process.stderr.write(error.name + ': ' + error.message);
        process.exitCode = 1;
      } finally {
        if (browser) await browser.close();
      }
    })();
    """
    try:
        result = subprocess.run(
            ["node", "-e", node_script, url],
            check=True,
            capture_output=True,
            text=True,
            timeout=150,
        )
        page_data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        details = getattr(exc, "stderr", None) or str(exc)
        raise RuntimeError(f"Puppeteer Stealth fetch failed for {url}: {details}") from exc

    status = page_data["status"]
    title = page_data["title"]
    body = page_data["body"]
    print(f"VolleyStation fetch: HTTP {status}; title={title!r}", flush=True)
    if status == 403:
        raise RuntimeError(f"VolleyStation HTTP 403 for {url}; title={title!r}; body={body[:250]!r}")
    if re.search(r"just a moment|verify you are human|checking your browser|cierpliwości", title + " " + body, re.I):
        raise RuntimeError(f"VolleyStation challenge did not clear for {url}; title={title!r}; body={body[:250]!r}")
    return BeautifulSoup(page_data["html"], "html.parser")

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

def parse_matches(soup, source_url, group_name):
    matches = []
    for anchor in soup.find_all("a", href=True):
        text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
        prefix = re.match(r"^(?:TV\s+)?Runda:\s*(\d+)\s+Nr\s+(\d+)\s+(.+)$", text, re.I)
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
            home = rest[:score_match.start()].strip(" ·-")
            away = rest[score_match.end():].strip(" ·-")
            home_sets, away_sets = int(score_match.group(1)), int(score_match.group(2))
            status, time = "finished", None
        else:
            time_match = re.search(r"\b(\d{2}:\d{2})\b", rest)
            if not time_match:
                continue
            home = rest[:time_match.start()].strip(" ·-")
            away = rest[time_match.end():].strip(" ·-")
            home_sets, away_sets = None, None
            status, time = "scheduled", time_match.group(1)

        if not home or not away:
            continue
        # Keep source page and round/match number as a stable identity even if
        # VolleyStation's link path changes between page versions.
        matches.append({
            "id": f"{group_name}-{date}-{round_no}-{match_no}",
            "competition": f"{LEAGUE_NAME} · {group_name}",
            "group": group_name,
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
        })
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
            candidate = " ".join(str(node.get(attr, "")) for attr in ("datetime", "data-start-time", "data-kickoff"))
            candidate += " " + node.get_text(" ", strip=True)
            time_match = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", candidate)
            if time_match:
                kickoff = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
                break

    # Match pages render each team's points in paired .team-points-row
    # containers. Each .set-points element is one set's points, not a "25:18"
    # string, so pair the home and away rows by set index.
    set_scores = []
    team_rows = soup.select(".team-points-row")
    home_row = next((row for row in team_rows if "home" in row.get("class", [])), None)
    away_row = next((row for row in team_rows if "away" in row.get("class", [])), None)

    if home_row and away_row:
        home_points = [
            node.get_text(" ", strip=True)
            for node in home_row.select(".set-points")
        ]
        away_points = [
            node.get_text(" ", strip=True)
            for node in away_row.select(".set-points")
        ]
        for home_value, away_value in zip(home_points, away_points):
            if home_value.isdigit() and away_value.isdigit():
                a, b = int(home_value), int(away_value)
                if 0 <= a <= 40 and 0 <= b <= 40 and a != b:
                    set_scores.append(f"{a}:{b}")


    return {"time": kickoff, "set_scores": set_scores}

def parse_table(soup):
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
            if wins + losses != played:
                raise ValueError(
                    f"result counts ({wins + losses}) do not match played ({played})"
                )
            rows.append({
                "rank": rank, "team": cells[1], "played": played,
                "points": points, "wins": wins, "losses": losses,
                "sets_for": sets_for, "sets_against": sets_against,
                "points_for": points_for, "points_against": points_against,
            })
        except (ValueError, IndexError) as exc:
            print(f"Skipping invalid standings row {cells[:4]!r}: {exc}", file=sys.stderr)
    if rows and len(rows) not in (9, 10):
        print(f"Warning: unexpected standings row count: {len(rows)}", file=sys.stderr)
    return rows

def parse_team_logos(soup, page_url):
    """Extract team logos from standings and team profile links."""
    logos = {}

    def extract_url(node):
        for attr in ("src", "data-src", "data-lazy-src", "data-original", "data-image", "href"):
            value = (node.get(attr) or "").strip()
            if value and not value.startswith("data:") and not value.startswith("javascript:"):
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
            team_soup = fetch(href)
        except Exception as exc:
            print(f"Warning: couldn't inspect team profile for logo {name!r}: {exc}", file=sys.stderr)
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
            'meta[property="og:image"]', 'meta[name="twitter:image"]',
            'img[alt*="logo" i]', 'img[class*="logo" i]',
            'img[src]', 'img[data-src]', 'img[data-lazy-src]',
            'img[data-original]', 'img[data-image]', 'img[srcset]',
            '[style*="background-image"]',
        ):
            image_candidates.extend(team_soup.select(selector))
        for node in image_candidates:
            if node.name == "meta":
                src = urljoin(href, (node.get("content") or "").strip())
            else:
                src = extract_url(node)
            if not src or not re.search(r"\.(?:svg|png|jpe?g|webp)(?:[?#].*)?$", src, re.I):
                continue
            if any(token in src.lower() for token in ("flag", "avatar", "default", "placeholder")):
                continue
            logos[name] = src
            print(f"Team logo mapped: {name} -> {src}", flush=True)
            break

    return logos

def load_previous(path):
    """Keep the last good data available if the official site temporarily fails."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def discover_group_urls(teams_soup):
    """Find current-season group URLs from VolleyStation's own phase selector/links."""
    candidates = []
    for node in teams_soup.select("option, a[href]"):
        label = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        raw_url = node.get("value") if node.name == "option" else node.get("href")
        if not raw_url:
            continue
        url = urljoin(ROOT_URL, raw_url)
        if re.search(r"2\s*liga\s*m[eę]żczyzn\s*grupa\s*[1-5]", label, re.I):
            if "/phase-" in url:
                group_match = re.search(r"grupa\s*([1-5])", label, re.I)
                if group_match:
                    candidates.append((int(group_match.group(1)), url.rstrip("/")))
    # Some VolleyStation page versions expose the phase URLs as links but omit
    # the phase label from visible text. Fall back to matching the URL slug.
    for node in teams_soup.select('a[href*="/phase-"], option[value*="/phase-"]'):
        raw_url = node.get("href") or node.get("value") or ""
        label = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        url = urljoin(ROOT_URL, raw_url).rstrip("/")
        phase_match = re.search(r"2-liga-mezczyzn-grupa-([1-5])", url, re.I)
        if phase_match and re.search(r"2\s*liga\s*m[eę]żczyzn\s*grupa", label, re.I):
            candidates.append((int(phase_match.group(1)), url))
    groups = {}
    for number, url in candidates:
        groups.setdefault(number, url)
    if len(groups) < 5:
        raise RuntimeError(
            f"Could not discover all five current II Liga group phases from {ROOT_URL}; "
            f"found groups {sorted(groups)}. Refusing to replace existing data."
        )
    return [(f"Grupa {number}", groups[number]) for number in sorted(groups)]


def page_url(base, section):
    base = base.rstrip("/")
    if base.endswith("/teams"):
        base = base[:-6]
    return base + f"/{section}/"


def main():
    previous = load_previous(OUT)
    # Start from the official teams page so phase IDs follow the current season
    # instead of being hard-coded to last season's phase IDs.
    teams_soup = fetch(ROOT_URL)
    group_sources = discover_group_urls(teams_soup)
    groups_out = []
    total_matches = 0
    total_teams = set()
    total_standings = 0

    previous_groups = {
        group.get("name", ""): group
        for group in previous.get("groups", [])
    }

    for group_name, phase_base in group_sources:
        schedule_url = page_url(phase_base, "schedule")
        results_url = page_url(phase_base, "results")
        standings_url = page_url(phase_base, "standings")
        old_group = previous_groups.get(group_name, {})

        schedule = parse_matches(fetch(schedule_url), schedule_url, group_name)
        results = parse_matches(fetch(results_url), results_url, group_name)
        by_id = {match["id"]: match for match in schedule}
        for result in results:
            fixture = by_id.get(result["id"], {})
            merged = {**fixture, **result}
            if not result.get("time") and fixture.get("time"):
                merged["time"] = fixture["time"]
            by_id[result["id"]] = merged
        matches = list(by_id.values())

        def valid_saved_set_score(value):
            parsed = re.fullmatch(r"(\d{1,2}):(\d{1,2})", str(value).strip())
            if not parsed:
                return False
            a, b = map(int, parsed.groups())
            if a > 40 or b > 40 or a == b:
                return False
            winner, loser = max(a, b), min(a, b)
            return (winner >= 25 and winner - loser >= 2) or (
                winner == 15 and loser <= 13
            ) or (15 < winner <= 20 and winner - loser == 2)

        for match in matches:
            match["set_scores"] = [
                score for score in (match.get("set_scores") or [])
                if valid_saved_set_score(score)
            ]

        detail_candidates = [
            match for match in matches
            if match.get("status") == "finished" and match.get("match_url")
            and not match.get("set_scores")
        ]
        for match in detail_candidates:
            try:
                detail_data = parse_match_detail(fetch(match["match_url"]))
                if not match.get("time") and detail_data["time"]:
                    match["time"] = detail_data["time"]
                if detail_data["set_scores"]:
                    match["set_scores"] = detail_data["set_scores"]
            except Exception as exc:
                print(f"Warning: could not read match detail {match.get('match_url')}: {exc}", file=sys.stderr)

        for match in matches:
            match.pop("match_url", None)
            total_teams.update((match["home"], match["away"]))

        if not matches:
            raise RuntimeError(
                f"No matches parsed for {group_name} from official VolleyStation pages; "
                "refusing to overwrite existing data."
            )
        old_matches = old_group.get("matches", [])
        if len(old_matches) >= 8 and len(matches) < max(4, int(len(old_matches) * 0.5)):
            raise RuntimeError(
                f"Only {len(matches)} matches parsed for {group_name}, versus "
                f"{len(old_matches)} in the previous feed; refusing incomplete data."
            )

        try:
            standings_soup = fetch(standings_url)
            table = parse_table(standings_soup)
            team_logos = parse_team_logos(standings_soup, standings_url)
            if len(table) < 8:
                raise RuntimeError(f"only {len(table)} standings rows parsed")
            print(f"{group_name}: found {len(team_logos)} team logos", flush=True)
        except Exception as exc:
            print(f"Warning: {group_name} standings unavailable, keeping previous table/logos: {exc}", file=sys.stderr)
            table = old_group.get("table", [])
            team_logos = {
                team.get("name", ""): team.get("logo", "")
                for team in old_group.get("teams", [])
                if team.get("name") and team.get("logo")
            }

        teams = sorted(
            {name.strip() for match in matches for name in (match["home"], match["away"]) if name and name.strip()},
            key=str.casefold,
        )
        group_data = {
            "name": group_name,
            "source": schedule_url,
            "results_source": results_url,
            "standings_source": standings_url,
            "teams": [
                {
                    "name": name,
                    "logo": team_logos.get(name)
                        or next((logo for known_name, logo in team_logos.items()
                                 if known_name.casefold() == name.casefold()), "")
                        or next((team.get("logo", "") for team in old_group.get("teams", [])
                                 if team.get("name", "").casefold() == name.casefold()), ""),
                }
                for name in teams
            ],
            "matches": sorted(matches, key=lambda match: (
                datetime.strptime(match["date"], "%d.%m.%Y"),
                match.get("time") or "99:99",
                match.get("round", 0),
                match.get("match_number", 0),
            )),
            "table": table,
        }
        groups_out.append(group_data)
        total_matches += len(matches)
        total_standings += len(table)
        print(
            f"{group_name}: schedule={len(schedule)}, results={len(results)}, "
            f"matches={len(matches)}, teams={len(teams)}, table={len(table)}",
            flush=True,
        )

    if len(groups_out) != 5 or len(total_teams) < 40:
        raise RuntimeError(
            f"Unexpected II Liga coverage: groups={len(groups_out)}, teams={len(total_teams)}; "
            "refusing to replace existing data."
        )

    data = {
        "competition": LEAGUE_NAME,
        "source": ROOT_URL,
        "results_source": ROOT_URL,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "groups": groups_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Saved II Liga data: {total_matches} matches, {len(total_teams)} teams, "
        f"{total_standings} standings rows across {len(groups_out)} groups",
        flush=True,
    )

if __name__ == "__main__":
    main()
