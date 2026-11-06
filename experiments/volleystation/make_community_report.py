"""Build the community supplement from downloaded Actions artifacts."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUNS=(42297682083,42298090306,42298531363)


def independently_check(path):
    data=json.loads(path.read_text());errors=[];ids=set();totals=collections.defaultdict(collections.Counter)
    for match in data['matches']:
        if match['id'] in ids:errors.append('duplicate match id: '+match['id'])
        ids.add(match['id'])
        if match['status']!='finished':continue
        sets=[tuple(map(int,s.split(':'))) for s in match['set_scores']]
        home,away=match['home_sets'],match['away_sets']
        if (sum(a>b for a,b in sets),sum(a<b for a,b in sets))!=(home,away):errors.append('set winners: '+match['id'])
        if max(home,away)!=3 or min(home,away)>2:errors.append('match result: '+match['id'])
        for index,(a,b) in enumerate(sets):
            target=15 if index==4 else 25;hi,lo=max(a,b),min(a,b)
            if not (hi>=target and hi-lo>=2 and (hi==target or hi-lo==2)):errors.append('illegal set: '+match['id'])
        for team,won,sets_for,sets_against,pts_for,pts_against in [
            (match['home'],home>away,home,away,sum(s[0] for s in sets),sum(s[1] for s in sets)),
            (match['away'],away>home,away,home,sum(s[1] for s in sets),sum(s[0] for s in sets))]:
            totals[team].update(played=1,wins=int(won),losses=int(not won),sets_for=sets_for,sets_against=sets_against,
                points_for=pts_for,points_against=pts_against,points=(2 if won else 1) if min(home,away)==2 else (3 if won else 0))
    for row in data['table']:
        for key in ['played','wins','losses','points','sets_for','sets_against','points_for','points_against']:
            if row[key]!=totals[row['team']][key]:errors.append('table '+key+': '+row['team'])
    return {'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'errors':errors,'passed':not errors}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('evidence_root',type=Path);args=parser.parse_args()
    output=HERE/'report-community';output.mkdir(exist_ok=True)
    evidence=[];checks=[];table=[]
    for run in RUNS:
        for path in sorted((args.evidence_root/f'github-run-{run}').glob('community-*/summary.json')):
            summary=json.loads(path.read_text());case=summary.get('case','fingerprint-restarts')
            rows_path=path.with_name('requests.jsonl')
            rows=[json.loads(line) for line in rows_path.read_text().splitlines()] if rows_path.exists() else []
            evidence.append({'run_id':run,'case':case,'summary':summary,'requests':rows})
            if case=='fingerprint-restarts':continue
            passed=[c for c in summary['cycles'] if c['quality_passed']]
            assert len(rows)==summary['navigations']
            assert sum(bool(r['ok']) for r in rows)==summary['passed_navigations']
            assert summary['production_unchanged']
            for cycle in passed:
                check=independently_check(path.with_name(f"cycle-{cycle['cycle']}.json"))
                check['file']=f"{run}/{path.parent.name}/cycle-{cycle['cycle']}.json"
                checks.append(check)
            table.append({'run_id':run,'case':case,'valid_documents':summary['passed_navigations'],
                'documents':len(rows),'complete_cycles':len(passed),'attempted_cycles':len(summary['cycles']),
                'helper_attempts':sum(bool(r.get('helper_attempted')) for r in rows),
                'setup_error':summary.get('setup_or_runtime_error','')})
    assert len([e for e in evidence if e['case']!='fingerprint-restarts'])==9
    assert all(c['passed'] for c in checks)
    for name,value in [('dane-pomiarowe.json',evidence),('kontrola-eksportow.json',checks)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    with (output/'wyniki.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    lines=['| Run | Wariant | Poprawne dokumenty | Kompletne aktualizacje | Próby obsługi challenge |',
           '| --- | --- | ---: | ---: | ---: |']
    for t in table:
        result=f"{t['complete_cycles']}/{t['attempted_cycles']}" if t['attempted_cycles'] else 'błąd startu'
        lines.append(f"| {t['run_id']} | {t['case']} | {t['valid_documents']}/{t['documents']} | {result} | {t['helper_attempts']} |")
    (output/'tabela.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'scenarios':len(table),'documents':sum(t['documents'] for t in table),
        'valid_documents':sum(t['valid_documents'] for t in table),'complete_cycles':sum(t['complete_cycles'] for t in table),
        'checked_exports':len(checks),'all_exports_passed':all(c['passed'] for c in checks)},indent=2))


if __name__=='__main__':main()
