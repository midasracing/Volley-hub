#!/usr/bin/env python3
"""Refresh TAURON Liga Mężczyzn data from the official public pages."""
import json, re, html, datetime
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

BASE = "https://www.tauronliga.pl"
HEADERS = {"User-Agent": "VolleyHub/1.0 (+https://github.com/midasracing/Volley-hub)"}
TEAM_NAMES = [
"PGE GiEK SKRA Bełchatów","Energa Trefl Gdańsk","ZAKSA Kędzierzyn-Koźle","BOGDANKA LUK Lublin",
"Ślepsk Malow Suwałki","Jastrzębie Barkom","Podziemia Kredowe ChKS Chełm","Stilon Gorzów",
"Energa Indykpol AZS Olsztyn","Steam Hemarpol Politechnika Częstochowa","Aluron CMC Warta Zawiercie",
"GKS Katowice","PGE Projekt Warszawa","Asseco Resovia Rzeszów","NEONET Norwid Częstochowa"
]
def get(url):
    req=Request(url,headers=HEADERS)
    with urlopen(req,timeout=30) as r: return r.read()
def norm(s): return re.sub(r"\\s+"," ",html.unescape(s or "")).strip()
def team_in(text):
    return next((n for n in sorted(TEAM_NAMES,key=len,reverse=True) if n.lower() in text.lower()),None)
def parse_table(soup):
    out=[]
    for tr in soup.select("tr"):
        cells=[norm(c.get_text(" ",strip=True)) for c in tr.find_all(["td","th"],recursive=False)]
        if len(cells)<8: continue
        name=team_in(" ".join(cells))
        if not name: continue
        nums=[]
        for c in cells:
            v=c.replace(" ","")
            if re.fullmatch(r"\\d+",v): nums.append(int(v))
        if len(nums)<8: continue
        # The official table begins with rank, points, matches played, wins and losses.
        out.append({"rank":nums[0],"team":name,"points":nums[1],"played":nums[2],"wins":nums[3],"losses":nums[4],"sets_for":nums[5],"sets_against":nums[6],"points_for":nums[7],"points_against":nums[8] if len(nums)>8 else 0})
    # Keep one official row per club, preserving the first row in the published order.
    unique={}
    for row in out: unique.setdefault(row["team"],row)
    return list(unique.values())
def parse_matches(soup):
    found={}
    # Each official match card contains club logo alt text and a result between the team names.
    for img in soup.find_all("img"):
        n=team_in(norm(img.get("alt",""))+" "+norm(img.get("title","")))
        if not n: continue
        a=img.find_parent("a")
        if not a: continue
        node=a
        for _ in range(7):
            node=node.parent
            if not node: break
            text=norm(node.get_text(" ",strip=True))
            names=[]
            for im in node.find_all("img"):
                tn=team_in(norm(im.get("alt",""))+" "+norm(im.get("title","")))
                if tn and tn not in names: names.append(tn)
            if len(names)!=2 or len(text)>1800: continue
            # Prefer the score directly between the first and second club names.
            pos1=text.lower().find(names[0].lower()); pos2=text.lower().find(names[1].lower())
            if pos1<0 or pos2<0: continue
            middle=text[min(pos1+len(names[0]),pos2):max(pos1+len(names[0]),pos2)]
            score=re.search(r"(?<!\\d)([0-3])\\s+([0-3])(?!\\d)",middle)
            if not score: continue
            home,away=(names[0],names[1]) if pos1<pos2 else (names[1],names[0])
            hs,aws=(int(score.group(1)),int(score.group(2))) if pos1<pos2 else (int(score.group(2)),int(score.group(1)))
            # Set points appear after the score; retain compact pairs where available.
            set_scores=[]
            tail=text[max(pos1,pos2):]
            pairs=re.findall(r"(?<!\\d)(\\d{1,2})\\s+(\\d{1,2})(?!\\d)",tail)
            for x,y in pairs[:5]:
                if int(x)>=15 and int(y)>=15: set_scores.append(f"{x}:{y}")
            date_match=re.search(r"(?:poniedziałek|wtorek|środa|czwartek|piątek|sobota|niedziela),?\\s+\\d{1,2}\\s+[a-ząćęłńóśźż]+(?:,?\\s+\\d{1,2}:\\d{2})?",text,re.I)
            status="finished" if (hs+aws)>0 else "scheduled"
            key=(home,away,hs,aws)
            found.setdefault(key,{"date":date_match.group(0) if date_match else "Sezon 2026/27","status":status,"home":home,"away":away,"home_sets":hs,"away_sets":aws,"set_scores":set_scores})
            break
    return list(found.values())
def main():
    games=BeautifulSoup(get(BASE+"/games/nocookies/1.html"),"html.parser")
    table=BeautifulSoup(get(BASE+"/table/nocookies/1.html"),"html.parser")
    matches=parse_matches(games); standings=parse_table(table)
    if not matches: raise RuntimeError("No matches parsed; refusing to overwrite feed with empty data.")
    if len(standings)<8: raise RuntimeError("Too few table rows parsed; refusing to overwrite feed.")
    payload={"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"matches":matches,"table":standings,"source":BASE}
    path=Path("data/tauron.json"); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
    print(f"Updated {len(matches)} matches and {len(standings)} table rows.")
if __name__=="__main__": main()
