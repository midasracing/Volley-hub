"""TAURON-compatible match fields, with explicit unknown source metadata."""

import re
import unicodedata
from datetime import datetime
from urllib.parse import urljoin, urlsplit

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
