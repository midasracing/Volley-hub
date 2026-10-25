#!/usr/bin/env python3
"""Fetch Pomorska III Liga Męska from the official VolleyStation schedule and results pages."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

BASE = "https://pomorskie.volleystation.com/pl/phase-6796-pomorska-iii-liga-meska"
SCHEDULE_URL = BASE + "/schedule/"
RESULTS_URL = BASE + "/results/"
STANDINGS_URL = BASE + "/standings/"
OUT = Path("data/pomorska3liga.json")
MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
    "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8,
    "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
}
def fetch(url):
    """Fetch a VolleyStation page with the existing Puppeteer + Stealth test setup."""
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
          args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        const page = await browser.newPage();
        // Controlled test: browser-like UA + varied viewport. Keep headless mode for CI.
        const chromeVersion = (await browser.version()).match(/Chrome\/(\d+\.\d+\.\d+\.\d+)/)?.[1] || '120.0.0.0';
        await page.setUserAgent(
          'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/' +
          chromeVersion + ' Safari/537.36'
        );
        await page.setViewport({
          width: Math.floor(1024 + Math.random() * 100),
          height: Math.floor(768 + Math.random() * 100)
        });
        await page.setExtraHTTPHeaders({
          'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8'
        });
        const response = await page.goto(process.argv[1], {
          waitUntil: 'domcontentloaded',
          timeout: 60000
        });
        try {
          await page.waitForNetworkIdle({ timeout: 20000 });
        } catch (_) {}
        await new Promise(resolve => setTimeout(resolve, 5000));
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
            timeout=90,
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
    if "Just a moment..." in title or "Verify you are human" in body:
        raise RuntimeError(f"Cloudflare challenge did not clear for {url}; title={title!r}; body={body[:250]!r}")
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

def parse_matches(soup, source_url):
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

    # VolleyStation shows set-by-set points on the individual match page.
    # Collect plausible volleyball set scores, excluding clock times and set-count scores.
    set_scores = []
    score_pattern = re.compile(r"(?<!\d)(\d{1,2})\s*[:\-–]\s*(\d{1,2})(?!\d)")
    score_nodes = soup.select("table td, table th, [class*='set'], [class*='score'], [data-testid*='score']")
    # Prefer the most specific matching nodes so parent containers don't duplicate
    # the same set, while still preserving repeated scores from different sets.
    candidates = []
    for node in score_nodes:
        node_text = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
        if not score_pattern.search(node_text):
            continue
        if any(score_pattern.search(re.sub(r"\s+", " ", child.get_text(" ", strip=True)))
               for child in node.find_all(True)):
            continue
        candidates.append(node_text)

    def is_volleyball_set_score(a, b, token=""):
        # Never interpret a clock token (e.g. 18:00) as a set score.
        if re.fullmatch(r"(?:[01]?\\d|2[0-3]):[0-5]\\d", token.strip()):
            return False
        if a > 40 or b > 40 or a == b:
            return False
        winner, loser = max(a, b), min(a, b)
        # Regular sets are won at 25+; a deciding set is won at 15+.
        # Require a two-point margin and reject impossible artifacts such as 18:0.
        return (winner >= 25 and winner - loser >= 2) or (
            15 <= winner <= 20 and loser <= 18 and winner - loser >= 2
        )

    for node_text in candidates:
        for match in score_pattern.finditer(node_text):
            a, b = int(match.group(1)), int(match.group(2))
            if not is_volleyball_set_score(a, b, match.group(0)):
                continue
            set_scores.append(f"{a}:{b}")

    # Fallback to full page text if scores aren't in identifiable score/table elements.
    if not set_scores:
        for match in score_pattern.finditer(text):
            a, b = int(match.group(1)), int(match.group(2))
            if not is_volleyball_set_score(a, b, match.group(0)):
                continue
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
    if rows and len(rows) != 9:
        print(f"Warning: expected 9 standings rows, parsed {len(rows)}", file=sys.stderr)
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
        name = re.sub(r"\\s+", " ", anchor.get_text(" ", strip=True)).strip()
        # Some layouts wrap the badge in a link and keep the team name elsewhere
        # in the same standings row; use that row's team cell as a fallback.
        if not name:
            row = anchor.find_parent("tr")
            cells = row.find_all(["td", "th"], recursive=False) if row else []
            if len(cells) >= 2:
                name = re.sub(r"\\s+", " ", cells[1].get_text(" ", strip=True)).strip()
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


def main():
    previous = load_previous(OUT)
    # IMPORTANT: VolleyStation separates upcoming fixtures (/schedule/) from
    # played results (/results/). Both pages must be read to build a full calendar.
    schedule = parse_matches(fetch(SCHEDULE_URL), SCHEDULE_URL)
    results = parse_matches(fetch(RESULTS_URL), RESULTS_URL)
    # Start with fixtures, then let official results replace scores/status for the same match.
    # Result pages often omit kickoff time, so never discard a time already found in schedule.
    by_id = {match["id"]: match for match in schedule}
    for result in results:
        fixture = by_id.get(result["id"], {})
        merged = {**fixture, **result}
        if not result.get("time") and fixture.get("time"):
            merged["time"] = fixture["time"]
        by_id[result["id"]] = merged
    matches = list(by_id.values())

    # Finished matches expose kickoff time and point-by-point set scores on the
    # official individual match page, so inspect each completed match directly.
    # Remove bogus scores saved by older parser versions (e.g. "18:0" from 18:00).
    def valid_saved_set_score(value):
        parsed = re.fullmatch(r"(\\d{1,2}):(\\d{1,2})", str(value).strip())
        if not parsed:
            return False
        a, b = map(int, parsed.groups())
        if a > 40 or b > 40 or a == b:
            return False
        winner, loser = max(a, b), min(a, b)
        return (winner >= 25 and winner - loser >= 2) or (
            15 <= winner <= 20 and loser <= 18 and winner - loser >= 2
        )

    for match in matches:
        match["set_scores"] = [
            score for score in (match.get("set_scores") or [])
            if valid_saved_set_score(score)
        ]

    detail_candidates = [
        match for match in matches
        if match.get("status") == "finished" and match.get("match_url")
        and (not match.get("time") or not match.get("set_scores"))
    ]
    detail_times_found = 0
    detail_scores_found = 0
    for match in detail_candidates:
        try:
            detail_soup = fetch(match["match_url"])
            detail_data = parse_match_detail(detail_soup)
            if not match.get("time") and detail_data["time"]:
                match["time"] = detail_data["time"]
                detail_times_found += 1
            if detail_data["set_scores"]:
                match["set_scores"] = detail_data["set_scores"]
                detail_scores_found += 1
        except Exception as exc:
            print(f"Warning: could not read details from match page {match['match_url']}: {exc}", file=sys.stderr)
    print(
        f"Match detail lookup: checked={len(detail_candidates)}, "
        f"kickoff times recovered={detail_times_found}, set-score lists recovered={detail_scores_found}",
        flush=True,
    )

    # Internal helper URL is not needed in the public JSON feed.
    for match in matches:
        match.pop("match_url", None)

    with_time = sum(bool(match.get("time")) for match in matches)
    missing_time = sum(not match.get("time") for match in matches)
    missing_time_finished = sum(not match.get("time") and match.get("status") == "finished" for match in matches)
    print(
        f"Parsed official pages: schedule={len(schedule)}, results={len(results)}, "
        f"unique matches={len(matches)}, with kickoff time={with_time}, "
        f"without time={missing_time} (finished without time={missing_time_finished})",
        flush=True,
    )
    if not matches:
        raise RuntimeError(
            "No recognizable matches found on official VolleyStation schedule or results pages; "
            "refusing to overwrite existing data."
        )

    # Avoid silently publishing a suspiciously incomplete feed if the source layout changes.
    previous_matches = previous.get("matches", [])
    if len(previous_matches) >= 8 and len(matches) < max(4, int(len(previous_matches) * 0.5)):
        raise RuntimeError(
            f"Only {len(matches)} matches parsed, versus {len(previous_matches)} in the last saved feed; "
            "refusing to replace potentially valid data with an incomplete scrape."
        )

    team_logos = {}
    try:
        standings_soup = fetch(STANDINGS_URL)
        standings = parse_table(standings_soup)
        team_logos = parse_team_logos(standings_soup, STANDINGS_URL)
        if len(standings) < 8:
            raise RuntimeError(f"only {len(standings)} standings rows parsed")
        print(f"Official team logos found in standings: {len(team_logos)}", flush=True)
    except Exception as exc:
        print(f"Warning: standings unavailable, keeping previous table: {exc}", file=sys.stderr)
        standings = previous.get("table", [])
        team_logos = {
            team.get("name", ""): team.get("logo", "")
            for team in previous.get("teams", [])
            if team.get("name") and team.get("logo")
        }

    matches.sort(key=lambda m: (
        datetime.strptime(m["date"], "%d.%m.%Y"),
        m["time"] or "99:99",
        m["round"],
        m["match_number"],
    ))
    teams = sorted(
        {name.strip() for match in matches for name in (match["home"], match["away"]) if name and name.strip()},
        key=str.casefold,
    )
    if len(teams) < 8:
        raise RuntimeError(
            f"Only {len(teams)} distinct teams found in parsed matches; refusing to publish incomplete data."
        )
    data = {
        "league": "pomorska3liga",
        "competition": "Pomorska III Liga Męska",
        "source": SCHEDULE_URL,
        "results_source": RESULTS_URL,
        "standings_source": STANDINGS_URL,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "teams": [
            {
                "name": name,
                "logo": team_logos.get(name)
                    or next(
                        (logo for known_name, logo in team_logos.items()
                         if known_name.casefold() == name.casefold()),
                        ""
                    )
                    or next(
                        (team.get("logo", "") for team in previous.get("teams", [])
                         if team.get("name", "").casefold() == name.casefold()),
                        ""
                    ),
            }
            for name in teams
        ],
        "matches": matches,
        "table": standings,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(matches)} matches ({len(results)} from results, {len(schedule)} from schedule), {len(teams)} teams; standings rows: {len(standings)}")

if __name__ == "__main__":
    main()
