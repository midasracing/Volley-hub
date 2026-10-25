#!/usr/bin/env python3
"""Fetch Pomorska III Liga Męska from the official VolleyStation schedule and results pages."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

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
        })
    return matches

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
    # Start with fixtures, then let official results replace them for the same match.
    # This prevents a stale schedule entry from overwriting a completed result.
    by_id = {match["id"]: match for match in schedule}
    by_id.update({match["id"]: match for match in results})
    matches = list(by_id.values())
    print(
        f"Parsed official pages: schedule={len(schedule)}, results={len(results)}, "
        f"unique matches={len(matches)}",
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

    try:
        standings = parse_table(fetch(STANDINGS_URL))
        if len(standings) < 8:
            raise RuntimeError(f"only {len(standings)} standings rows parsed")
    except Exception as exc:
        print(f"Warning: standings unavailable, keeping previous table: {exc}", file=sys.stderr)
        standings = previous.get("table", [])

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
        "teams": [{"name": name, "logo": ""} for name in teams],
        "matches": matches,
        "table": standings,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(matches)} matches ({len(results)} from results, {len(schedule)} from schedule), {len(teams)} teams; standings rows: {len(standings)}")

if __name__ == "__main__":
    main()
