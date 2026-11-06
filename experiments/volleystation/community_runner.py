import argparse
import hashlib
import json
import os
import time
from importlib.metadata import version
import requests
from bs4 import BeautifulSoup
from battery_common import measure, pace, quality, save
from render_probe import snapshot, host_display
from run import HERE, PAGES
import scraper_incremental as scraper

def main(Browser, cases, packages):
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=cases,required=True)
    args=parser.parse_args()
    output=HERE/'outputs'/'community'/args.case;output.mkdir(parents=True,exist_ok=True)
    source=HERE.parents[1]/'data'/'pomorska3liga.json';before=hashlib.sha256(source.read_bytes()).hexdigest()
    seed=HERE/'seed-validated-20261106.json'
    rows=[];cycles=[];last=None;blocked=False;cycle=1;engine=None
    summary={'case':args.case,'run_id':os.getenv('GITHUB_RUN_ID'),'versions':{key:version(package) for key,package in packages.items()},
             'display':host_display(),'navigation_budget':12,'interval_seconds':15,'cycles':cycles,'browser_probes':[]}
    def fetch(url):
        nonlocal last,blocked
        if blocked or len(rows)>=12:raise RuntimeError('Source refusal or experiment navigation limit')
        last=pace(last,15);tick=time.monotonic()
        try:
            result=engine.get(url)
            kind=next((kind for kind,target in PAGES if target==url),None)
            if not kind and '/matches/' in url:kind='detail'
            row=measure(kind,url,result)
            row.update(helper_attempted=result['helper_attempted'],helper_error=result['helper_error'],document_responses=result['document_responses'])
        except Exception as error:
            row={'url':url,'ok':False,'error':type(error).__name__+': '+str(error)[:500]};result=None
        row.update(cycle=cycle,elapsed_seconds=round(time.monotonic()-tick,3));rows.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
        if not row['ok']:blocked=True;raise RuntimeError('Document blocked or invalid')
        return BeautifulSoup(result['html'],'html.parser')
    try:
        response=requests.get(scraper.SCHEDULE_URL,timeout=(10,30))
        summary['plain_http_control']=measure('schedule',scraper.SCHEDULE_URL,{'status':response.status_code,'headers':dict(response.headers),'html':response.text},browser=False)
        for cycle in (1,2):
            if cycle>1:time.sleep(30)
            engine=Browser(args.case);engine.start()
            summary['browser_probes'].append(snapshot(engine.cdp.evaluate))
            destination=output/f'cycle-{cycle}.json';destination.write_bytes(seed.read_bytes())
            scraper.OUT,scraper.fetch=destination,fetch;count=len(rows)
            try:
                scraper.main();metrics=quality(json.loads(destination.read_text()))
                metrics['quality_passed']=metrics['quality_passed'] and not blocked
                metrics.update(cycle=cycle,navigations=len(rows)-count)
            except Exception as error:metrics={'cycle':cycle,'quality_passed':False,'error':str(error),'navigations':len(rows)-count}
            cycles.append(metrics);engine.close();engine=None
            if not metrics['quality_passed']:break
    except Exception as error:summary['setup_or_runtime_error']=type(error).__name__+': '+str(error)[:1200]
    finally:
        if engine:
            try:engine.close()
            except Exception as error:summary['close_error']=str(error)[:300]
        summary.update(navigations=len(rows),passed_navigations=sum(bool(r.get('ok')) for r in rows),
                       passed_cycles=sum(bool(c.get('quality_passed')) for c in cycles),production_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==before)
        save(output,rows,summary)


