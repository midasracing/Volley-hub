#!/usr/bin/env python3
"""Fetch II Liga fixtures, results and standings from the official PZPS referee system."""
import json
import re
import unicodedata
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PZPS_URL = "https://sedziowie.pzps.pl/system/mecze-II-liga-mezczyzn/"
PZPS_RESULTS_URL = "https://sedziowie.pzps.pl/system//index.php?mode=12&type=9"
VOLLEYSTATION_TEAMS_URL = "https://2ligamezczyzn.volleystation.com/pl/teams/"
OUT = Path("data/2liga.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VolleyHub/1.0)"}
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
        await new Promise(resolve => setTimeout(resolve, 1000));
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


def clean(value):
    return " ".join(value.replace("\xa0", " ").split())


def norm(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", value)


def parse_pzps():
    response = requests.get(PZPS_URL, timeout=30, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    matches, teams, group = [], set(), ""
    seen = set()
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "tr"]):
        if node.name != "tr":
            heading = clean(" ".join(node.stripped_strings))
            found = re.search(r"Grupa\s+(\d+)", heading, re.I)
            if found:
                group = f"Grupa {found.group(1)}"
            continue
        cells = [clean(td.get_text(" ", strip=True)) for td in node.find_all("td")]
        if len(cells) < 5:
            continue
        date_index = next((i for i, cell in enumerate(cells) if re.search(r"20\d{2}-\d{2}-\d{2}", cell)), None)
        if date_index is None or date_index + 3 >= len(cells):
            continue
        dm = re.search(r"(20\d{2})-(\d{2})-(\d{2})", cells[date_index])
        if not dm:
            continue
        year, month, day = dm.groups()
        date = f"{day}.{month}.{year}"
        tm = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", cells[date_index])
        time = f"{int(tm.group(1)):02d}:{tm.group(2)}" if tm else ""
        home = cells[date_index + 1].strip()
        sep = date_index + 2
        away_index = date_index + 3
        if cells[sep] not in {"-", "–", "—"}:
            sep = next((i for i in range(date_index + 1, len(cells)) if cells[i] in {"-", "–", "—"}), -1)
            if sep < 1 or sep + 1 >= len(cells):
                continue
            home, away_index = cells[sep - 1].strip(), sep + 1
        away = cells[away_index].strip()
        if not home or not away or home.lower() in {"pauzuje", "bye"} or away.lower() in {"pauzuje", "bye"}:
            continue
        if home.lower() in {"i", "ii", "kw"} or away.lower() in {"i", "ii", "kw"}:
            continue
        key = (group, date, time, home, away)
        if key in seen:
            continue
        seen.add(key)
        teams.update((home, away))
        matches.append({
            "date": date, "time": time, "home": home, "away": away,
            "home_sets": None, "away_sets": None, "set_scores": [],
            "status": "scheduled",
            "competition": f"II Liga Mężczyzn · {group}" if group else "II Liga Mężczyzn",
            "group": group,
        })
    if not matches:
        raise RuntimeError("PZPS page loaded, but no match rows were parsed.")
    matches.sort(key=lambda m: (datetime.strptime(m["date"], "%d.%m.%Y"), m["time"]))
    return matches, teams


def parse_pzps_results(matches):
    """Parse played scores and standings from the official PZPS results page."""
    response = requests.get(PZPS_RESULTS_URL, timeout=30, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    # Rows on this page contain: match id, ISO date, home, separator, away, set score.
    for row in soup.find_all("tr"):
        cells = [clean(td.get_text(" ", strip=True)) for td in row.find_all("td")]
        if len(cells) < 6:
            continue
        date_index = next((i for i, cell in enumerate(cells) if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", cell)), None)
        if date_index is None or date_index + 4 >= len(cells):
            continue
        home = cells[date_index + 1].strip()
        away_index = date_index + 3
        if cells[date_index + 2] not in {"-", "–", "—"}:
            sep = next((i for i in range(date_index + 1, len(cells)) if cells[i] in {"-", "–", "—"}), -1)
            if sep < 1 or sep + 1 >= len(cells):
                continue
            home, away_index = cells[sep - 1], sep + 1
        away = cells[away_index].strip()
        score_cell = " ".join(cells[away_index + 1:])
        set_match = re.search(r"\b([0-3])\s*:\s*([0-3])\b", score_cell)
        if not home or not away or not set_match:
            continue
        year, month, day = cells[date_index].split("-")
        results.append({
            "date": f"{day}.{month}.{year}", "home": home, "away": away,
            "home_sets": int(set_match.group(1)), "away_sets": int(set_match.group(2)),
            "set_scores": re.findall(r"\b\d{1,2}\s*:\s*\d{1,2}\b", score_cell)[1:]
        })

    # Match results onto the fixture list by team pair. PZPS occasionally uses
    # a leading zero/spacing variation in team names, so compare normalized names.
    for result in results:
        pair = {norm(result["home"]), norm(result["away"])}
        candidates = [m for m in matches
                      if {norm(m["home"]), norm(m["away"])} == pair]
        if not candidates:
            candidates = [m for m in matches
                          if all(any(n.startswith(norm(team)[:12]) or norm(team).startswith(n[:12])
                                     for n in (norm(m["home"]), norm(m["away"])))
                                 for team in (result["home"], result["away"]))]
        if candidates:
            match = next((m for m in candidates if m["date"] == result["date"]), candidates[0])
            match.update({k: result[k] for k in ("home_sets", "away_sets", "set_scores")})
            match["status"] = "finished" if result["home_sets"] + result["away_sets"] > 0 else "scheduled"

    # Parse standings tables when the page exposes them. Keep rows grouped by
    # team membership from the fixture list; do not fabricate standings.
    tables_by_group = {f"Grupa {i}": [] for i in range(1, 6)}
    team_group = {}
    for match in matches:
        if match.get("group"):
            team_group[norm(match["home"])] = match["group"]
            team_group[norm(match["away"])] = match["group"]
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        header_text = " ".join(clean(c.get_text(" ", strip=True)).lower()
                                for row in rows[:2] for c in row.find_all(["th", "td"]))
        # Only parse a table that looks like a league standings table.
        if not any(word in header_text for word in ("mecze", "mecz", "zwyci", "poraż", "poraz", "punkty", "pkt", "stosunek")):
            continue
        for row in rows:
            cells = [clean(c.get_text(" ", strip=True)) for c in row.find_all(["th", "td"])]
            if len(cells) < 5:
                continue
            team_cell = next((c for c in cells if norm(c) in team_group), None)
            if not team_cell:
                continue
            group = team_group[norm(team_cell)]
            nums = [int(c) for c in cells if re.fullmatch(r"\d+", c)]
            ratios = [tuple(map(int, match.groups())) for c in cells
                      for match in [re.fullmatch(r"(\d+)\s*:\s*(\d+)", c)] if match]
            if len(nums) < 3:
                continue
            tables_by_group[group].append({
                "rank": nums[0] if nums[0] <= 20 else len(tables_by_group[group]) + 1,
                "team": team_cell,
                "played": nums[1] if len(nums) > 1 else 0,
                "wins": nums[2] if len(nums) > 2 else 0,
                "losses": nums[3] if len(nums) > 3 else 0,
                "sets_for": ratios[0][0] if ratios else 0,
                "sets_against": ratios[0][1] if ratios else 0,
                "points_for": ratios[1][0] if len(ratios) > 1 else 0,
                "points_against": ratios[1][1] if len(ratios) > 1 else 0,
                "points": nums[-1] if nums else 0,
            })
    for group in tables_by_group:
        seen = set()
        tables_by_group[group] = [r for r in tables_by_group[group]
                                  if not (norm(r["team"]) in seen or seen.add(norm(r["team"])))]
        tables_by_group[group].sort(key=lambda r: r["rank"])
    return tables_by_group

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


def main():
    # Fixtures, results and standings remain sourced from the official PZPS referee system.
    matches, teams = parse_pzps()
    tables_by_group = parse_pzps_results(matches)

    # Team badges are enriched separately from VolleyStation using the same
    # Puppeteer + Stealth fetcher and profile-page logo extraction as III Liga.
    logos = {}
    try:
        teams_soup = fetch(VOLLEYSTATION_TEAMS_URL)
        logos = parse_team_logos(teams_soup, VOLLEYSTATION_TEAMS_URL)
        print(f"VolleyStation logos found: {len(logos)}", flush=True)
    except Exception as exc:
        print(f"Warning: VolleyStation logos unavailable; keeping previous logos: {exc}", file=sys.stderr)
    try:
        previous = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    previous_logos = {
        team.get("name", ""): team.get("logo", "")
        for group in previous.get("groups", [])
        for team in group.get("teams", [])
        if team.get("name") and team.get("logo")
    }
    def team_logo(name):
        for known_name, logo in logos.items():
            if known_name.casefold() == name.casefold():
                return logo
        normalized = norm(name)
        for known_name, logo in logos.items():
            if norm(known_name) == normalized or (normalized and norm(known_name) in normalized) or (norm(known_name) and normalized in norm(known_name)):
                return logo
        for known_name, logo in previous_logos.items():
            if known_name.casefold() == name.casefold() or norm(known_name) == normalized:
                return logo
        return ""
    groups = []
    for number in range(1, 6):
        group_name = f"Grupa {number}"
        group_matches = [m for m in matches if m.get("group") == group_name]
        group_teams = sorted({name for m in group_matches for name in (m["home"], m["away"])})
        table = tables_by_group.get(group_name, [])
        groups.append({
            "name": group_name,
            "teams": [{"name": n, "logo": team_logo(n)} for n in group_teams],
            "matches": group_matches,
            "table": table,
            "results_source": PZPS_RESULTS_URL,
        })
        print(f"{group_name}: {len(group_matches)} fixtures, {sum(m['status']=='finished' for m in group_matches)} results, {len(table)} table rows")

    data = {
        "competition": "II Liga Mężczyzn",
        "source": PZPS_URL,
        "results_source": PZPS_RESULTS_URL,
        "logos_source": VOLLEYSTATION_TEAMS_URL,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "groups": groups,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(matches)} fixtures across {len(teams)} teams to {OUT}")


if __name__ == "__main__":
    main()
