"""Read-only probe for public Italy/Japan league data endpoints."""
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

TARGETS = {
    "italy_schedule": "https://www.legavolley.it/calendario/",
    "italy_ical": "https://www.legavolley.it/ical-calendar/",
    "japan_schedule": "https://www.svleague.jp/match/sv/men/",
    "japan_match": "https://www.svleague.jp/match/detail/37994/",
}

def safe_url(value):
    p = urlparse(value)
    return p._replace(query="", fragment="").geturl()

def http_probe(name, url):
    result = {"name": name, "url": url}
    try:
        r = requests.get(url, timeout=(5, 20))
        result.update(status=r.status_code, bytes=len(r.content), content_type=r.headers.get("Content-Type"))
        if r.status_code != 200 or "html" not in r.headers.get("Content-Type","").lower():
            return result
        soup = BeautifulSoup(r.text, "html.parser")
        result["title"] = soup.title.get_text(" ", strip=True)[:120] if soup.title else ""
        result["scripts"] = [safe_url(urljoin(url, s["src"])) for s in soup.select("script[src]")][:25]
        result["json_scripts"] = [{"id":s.get("id"),"type":s.get("type"),"bytes":len(s.text)}
                                  for s in soup.select("script[type*=json],script#__NEXT_DATA__")][:10]
        result["forms"] = [safe_url(urljoin(url, f.get("action", ""))) for f in soup.select("form")][:10]
        result["feed_links"] = [safe_url(urljoin(url, a["href"])) for a in soup.select("a[href]")
                                if re.search(r"\.(ics|json|csv)([?#]|$)|/api/",a["href"],re.I)][:20]
        result["markers"] = {m:(m.lower() in r.text.lower()) for m in
                             ["__NEXT_DATA__", "__NUXT__", "graphql", "admin-ajax.php", "wp-json", "fetch(", "XMLHttpRequest"]}
        if name == "italy_ical":
            feeds = re.findall(r"https?://calendar\.google\.com/calendar/ical/[^\s\"'<>]+",r.text)
            result["google_ical_feeds"] = len(feeds)
            result["first_feed_url"] = safe_url(feeds[0]) if feeds else None
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)[:150]
    return result

async def browser_probe(browser, name, url):
    p = await browser.new_page()
    result = {"name": name, "requests": [], "responses": [], "websockets": []}
    tasks = []
    def request(req):
        if req.resource_type in ("xhr","fetch","eventsource") and len(result["requests"]) < 35:
            result["requests"].append({"method":req.method, "url":safe_url(req.url), "type":req.resource_type})
    async def response(resp):
        if resp.request.resource_type not in ("xhr","fetch","eventsource") or len(result["responses"]) >= 25:
            return
        ct = resp.headers.get("content-type","")
        item = {"status":resp.status,"url":safe_url(resp.url),"content_type":ct}
        if "json" in ct.lower() and int(resp.headers.get("content-length","0") or 0) < 180000:
            try:
                item["preview"] = (await resp.text())[:800]
            except Exception:
                pass
        result["responses"].append(item)
    p.on("request",request)
    p.on("response",lambda r: tasks.append(asyncio.create_task(response(r))))
    p.on("websocket",lambda w: result["websockets"].append(safe_url(w.url)))
    try:
        response = await p.goto(url,wait_until="domcontentloaded",timeout=28000)
        result["status"] = response.status if response else None
        result["title"] = (await p.title())[:120]
        await p.wait_for_timeout(4500)
        if name == "japan_schedule" and result["status"] == 200:
            button = p.get_by_text("次の月へ",exact=False)
            if await button.count():
                try:
                    await button.first.click(timeout=4000)
                    await p.wait_for_timeout(2000)
                    result["next_month_clicked"] = True
                except Exception as exc:
                    result["click_error"] = type(exc).__name__
        result["final_url"] = safe_url(p.url)
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)[:160]
    await asyncio.gather(*tasks,return_exceptions=True)
    await p.close()
    return result

async def main():
    report = {"http":[],"browser":[]}
    for name,url in TARGETS.items():
        r = http_probe(name,url)
        report["http"].append(r)
        print("HTTP",name,r.get("status"),"bytes",r.get("bytes"),"title",r.get("title"),"feeds",r.get("google_ical_feeds"))
        print("  SCRIPTS",r.get("scripts",[])[:8],"FORM",r.get("forms",[]),"MARKERS",r.get("markers"))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for name in ["italy_schedule","japan_schedule","japan_match"]:
                r = await browser_probe(browser,name,TARGETS[name])
                report["browser"].append(r)
                print("BROWSER",name,r.get("status"),"requests",len(r["requests"]),"error",r.get("error"))
                for request in r["requests"]:
                    print("  REQUEST",request)
                for response in r["responses"]:
                    print("  RESPONSE",response)
                for ws in r["websockets"]:
                    print("  WS",ws)
        finally:
            await browser.close()
    path = Path("diagnostics/artifacts/international-api-probe.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")

if __name__ == "__main__":
    asyncio.run(main())
