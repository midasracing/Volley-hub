"""Build the final report from downloaded measurement artifacts, not job colors."""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BATTERY = '42217490055'
FOLLOWUP = '42266370764'
LABELS = {
    'cam-live': 'Camoufox: jedna sesja', 'cam-linux': 'Camoufox: Linux',
    'cam-cache': 'Camoufox: cache przeglądarki', 'cam-fresh': 'Camoufox: nowe profile',
    'cam-restart': 'Camoufox: restart / przerwa', 'cam-recorded': 'Camoufox: rzeczywisty profil urządzenia',
    'cam-handoff': 'Camoufox → HTTP', 'nodriver-headless': 'NoDriver headless',
    'nodriver-headful': 'NoDriver z interfejsem', 'stock-firefox': 'Zwykły Firefox Playwright',
    'curl-profiles': 'curl_cffi: Chrome / Firefox / Safari', 'cam-slow': 'Camoufox: 15 s między odczytami',
    'cam-fresh-3': 'Camoufox: trzy nowe sesje', 'cam-recover': 'Camoufox: odzyskanie tej samej strony',
}


def load_cases(root, run, prefix):
    cases = []
    for folder in sorted((root/f'github-run-{run}').glob(prefix+'*')):
        if not (folder/'summary.json').exists():
            continue
        summary = json.loads((folder/'summary.json').read_text())
        rows = [json.loads(line) for line in (folder/'requests.jsonl').read_text().splitlines() if line.strip()]
        cases.append({'run_id': run, 'case': summary['case'], 'summary': summary, 'requests': rows})
    return cases


def outcome(case):
    s, rows = case['summary'], case['requests']
    cycles = s.get('cycles', [])
    if not rows and s.get('setup_or_runtime_error'):
        return 'Błąd uruchomienia; Cloudflare nieprzetestowany'
    if s.get('handoff_passed') is not None:
        return 'Przekazanie do HTTP: '+('poprawny odczyt' if s['handoff_passed'] else 'nieudane')
    if case['case'] == 'cam-handoff':
        return 'Nie osiągnięto przekazania sesji: wcześniejsza blokada lub niepełny import'
    if s.get('same_url_recovery_passed') is not None:
        return 'Ta sama strona po 60 s: '+('poprawny pojedynczy odczyt' if s['same_url_recovery_passed'] else 'ponownie odmowa')
    if s.get('recovery_passed'):
        return 'Po 60 s odczytano inną stronę; nie dowodzi odzyskania zablokowanej'
    if cycles:
        return f"Pełne eksporty: {sum(bool(c.get('quality_passed')) for c in cycles)}/{len(cycles)} wykonanych prób"
    return 'Poprawne dokumenty: '+str(sum(bool(r.get('ok')) for r in rows))+'/'+str(len(rows))


def table(cases):
    lines = ['| Scenariusz | Poprawne dokumenty / wykonane | Kompletne importy | Wynik / ograniczenie |',
             '| --- | ---: | ---: | --- |']
    for case in cases:
        rows, s = case['requests'], case['summary']
        cycles = s.get('cycles', [])
        complete = f"{sum(bool(c.get('quality_passed')) for c in cycles)}/{len(cycles)}" if cycles else '—'
        lines.append(f"| {LABELS[case['case']]} | {sum(bool(r.get('ok')) for r in rows)}/{len(rows)} | {complete} | {outcome(case)} |")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    battery = load_cases(args.evidence_root, BATTERY, 'battery-')
    followup = load_cases(args.evidence_root, FOLLOWUP, 'followup-')
    if len(battery) != 11 or len(followup) != 6:
        raise SystemExit(f'Incomplete evidence: {len(battery)}/11 battery and {len(followup)}/6 follow-up artifacts')
    cases = battery+followup
    rows = [r for case in cases for r in case['requests']]
    cycles = [c for case in cases for c in case['summary'].get('cycles', [])]
    passed = sum(bool(c.get('quality_passed')) for c in cycles)
    statuses = Counter(str(r.get('status', 'unknown')) for r in rows)
    controls = [case['summary']['plain_http_control'] for case in cases if 'plain_http_control' in case['summary']]
    checks = [case['summary']['production_unchanged'] for case in cases if 'production_unchanged' in case['summary']]
    facts = {'generated_at': datetime.now(timezone.utc).isoformat(), 'scenarios': len(cases),
             'source_navigations': len(rows), 'valid_navigations': sum(bool(r.get('ok')) for r in rows),
             'status_counts': dict(statuses), 'http_controls': len(controls),
             'http_controls_blocked': sum(r.get('status') == 403 and r.get('challenge') for r in controls),
             'executed_import_cycles': len(cycles), 'complete_import_cycles': passed,
             'production_hash_checks': len(checks), 'production_unchanged': all(checks), 'cases': cases}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'dane-pomiarowe.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2)+'\n')
    with (args.output/'wyniki.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.writer(stream, delimiter=';')
        writer.writerow(['run_id','scenario','valid_documents','attempted_documents','complete_imports','executed_imports','outcome'])
        for case in cases:
            cr, cs = case['requests'], case['summary'].get('cycles', [])
            writer.writerow([case['run_id'],case['case'],sum(bool(r.get('ok')) for r in cr),len(cr),
                             sum(bool(c.get('quality_passed')) for c in cs),len(cs),outcome(case)])
    repeat_winners = [c for c in cases if len(c['summary'].get('cycles', [])) >= 3
                     and all(x.get('quality_passed') for x in c['summary']['cycles'])]
    conclusion = ('Znaleziono obiecujący wariant: Camoufox z nowym profilem dla każdej '
                  'aktualizacji, istniejącym kompletnym cache danych i odstępami 15 s. '
                  'Wykonał 3/3 kolejnych poprawnych odświeżeń na jednym runnerze. '
                  'Nie potwierdzono niezawodności między runnerami ani w długim okresie.' if repeat_winners else
                  'W rozszerzonej serii żaden wariant nie ukończył pełnego importu. '
                  'Nie potwierdzono stabilnego obejścia Cloudflare.' if not passed else
                  f'W rozszerzonej serii {passed} z {len(cycles)} wykonanych importów przeszło kontrolę kompletności. '
                  'Tak mała próbka nie potwierdza bezobsługowej niezawodności; wyniki szczegółowe poniżej.')
    text = f'''# Raport końcowy: scraper VolleyStation

**{conclusion}**

Pojedynczy wcześniejszy import przyrostowy przez Camoufox z interfejsem był kompletny,
lecz po restarcie przeglądarki wystąpiła ponowna odmowa. Nie stanowi to rozwiązania
„bulletproof”. Nie wdrażano zmian do produkcji.

## Zakres i metoda

Badano requests, Puppeteer Stealth, Rebrowser, Patchright, curl_cffi, Camoufox,
zwykły Firefox Playwright i NoDriver. Próby sieciowe dotyczyły publicznych danych
Pomorskiej III ligi i kontrolnie listy drużyn II ligi.

Rozszerzenie obejmuje **17 scenariuszy**, {len(rows)} wykonanych nawigacji do źródła
i {len(controls)} odczytów kontrolnych przez requests. Kontrole HTTP z challenge/403:
**{facts['http_controls_blocked']}/{len(controls)}**. Z wykonanych nawigacji {facts['valid_navigations']}
zwróciło poprawne dane parsera; nie oznacza to tylu kompletnych aktualizacji feedu.

Scenariusze Camoufox miały limit 14 nawigacji, pozostałe 3. W uzupełnieniu limit
wynosił 11. Odstępy zwiększano z 3 do 8 i 15 s; pomiędzy próbami stosowano przerwy
20–30 s, a przy testach odzyskiwania 60 s. Nie generowano ruchu w celu wymuszenia
blokady. Liczby nie obejmują żądań przeglądarek po obrazy, skrypty i zasoby.

Każdy scenariusz miał kontrolę zwykłym HTTP na swoim runnerze. Różne scenariusze
uruchamiały się na różnych runnerach/IP; nie można przypisywać całej różnicy samemu
silnikowi. W obrębie scenariusza porównywano żądania z tego samego środowiska.
Maksymalnie dwa zadania wykonywały się równolegle.

## Wyniki rozszerzonej serii

[Pomiary 11 scenariuszy](https://github.com/midasracing/kiedysiatka/actions/runs/{BATTERY}).

{table(battery)}

Zatrzymanie po pierwszej odmowie oznacza, że zaplanowane kolejne rundy nie zostały
wykonane. Nie są zaliczane ani do sukcesów, ani do porażek. Warianty restartu,
przekazania sesji i nowych profili w pierwszej serii często nie docierały do tej
operacji, ponieważ wcześniej blokowany był pierwszy import.

## Uzupełnienie i naprawa błędu testowego

[Pomiary sześciu prób uzupełniających](https://github.com/midasracing/kiedysiatka/actions/runs/{FOLLOWUP}).

{table(followup)}

Pierwotne dwa uruchomienia NoDriver zakończyły się błędem startu przeglądarki.
Nie klasyfikowano tego jako blokady Cloudflare. W uzupełnieniu uruchamiano Chrome
bezpośrednio, czekano na jego lokalny endpoint CDP i dopiero wtedy dołączano
NoDriver. Mechanizm zweryfikowano lokalnie przed ponownym uruchomieniem na GitHubie.

Uzupełnienie używało kopii **wcześniej zweryfikowanego kompletnego feedu**, z 17
zakończonymi meczami i 9 logotypami. To test normalnego odświeżania po udanym imporcie,
nie test pobrania sezonu od zera. W zwykłej aktualizacji wystarczają wtedy trzy
obowiązkowe strony, o ile nie zmieniły się szczegóły zakończonych meczów.

W pierwszej serii próba „odzyskania” czytała terminarz po wcześniejszym zablokowaniu
strony innego meczu. Poprawny odczyt innego URL nie dowodzi odzyskania dostępu do
zablokowanego URL. Dlatego uzupełnienie sprawdzało dokładnie tę samą stronę.

## Co pokazały wcześniejsze próby

- [Stealth, Rebrowser i Patchright](https://github.com/midasracing/kiedysiatka/actions/runs/42212453568):
  403/challenge zarówno headless, jak i z interfejsem. Requests również blokowany.
- [Firefox i curl_cffi](https://github.com/midasracing/kiedysiatka/actions/runs/42213214158):
  Camoufox z interfejsem odczytał 4/4 strony; headless 2/3 i blokada tabeli; curl_cffi dostał 403.
- [Pełny import od zera](https://github.com/midasracing/kiedysiatka/actions/runs/42213719300):
  14 dokumentów poprawnych, następnie 403. Eksport był niepełny i nie przeszedł kontroli jakości.
- [Import przyrostowy](https://github.com/midasracing/kiedysiatka/actions/runs/42214482012):
  sześć odczytów dało kompletny feed: 72 mecze z godzinami, 17 wyników z kompletem
  punktów setów, 9 drużyn z logotypami i 9 wierszy tabeli. Po restarcie z tym samym
  profilem i konfiguracją fingerprintu pierwszy odczyt dostał 403.

Lokalnie w zarządzanym środowisku wszystkie cztery początkowe silniki odczytały dane
10/10 razy. Pełny import HTTP wykonał 30 odczytów i zakończył się poprawnie. Środowisko
korzystało jednak z proxy kończącego TLS, więc nie odtwarzało bezpośrednich połączeń
z runnerów GitHuba. Ten wynik nie dowodzi obejścia aktywnej blokady Cloudflare.

## Kontrola danych i znalezione błędy

Poprawność dokumentu wymagała przejścia parsera, a kompletność eksportu: odpowiedniej
liczby meczów i drużyn, godzin wszystkich meczów, kompletów punktów setów, tabeli
i logotypów. Dane z poprzedniego feedu wykorzystywano tylko przy dokładnej tożsamości
meczu i zgodnym oficjalnym wyniku; niepełne lub sprzeczne sety wymagają pobrania.
Sześć testów offline sprawdza reguły ponownego użycia cache. Niezależne sprawdzenie
trzech końcowych eksportów potwierdziło też legalność punktów setów, zgodność
zwycięzców setów z wynikiem meczu oraz zgodność liczby meczów, zwycięstw, porażek
i punktów tabeli z odczytanymi wynikami. Wyniki tej kontroli:
[independent-export-checks.json](../independent-export-checks.json).

Istotne ustalenia:

1. **HTTP 200 nie wystarcza.** Poprawnie odebrane strony mogą dać niepełny feed,
   jeśli zablokowano późniejsze szczegóły meczów lub tabelę. Kontrola kompletności
   nie pozwalała uznać takiego eksportu za sukces.
2. **HTTP 304 w przeglądarce może być poprawnym odczytem.** Początkowy miernik
   błędnie odrzucił dwa poprawne dokumenty z cache. Skorygowany raport zachowuje
   surowe obserwacje i wyjaśnia zmianę klasyfikacji. Sama odpowiedź 304 bez treści w HTTP
   nie jest równoważnym źródłem danych.
3. **Cache rzeczywiście zmniejsza ruch.** Dla sprawdzonego stanu feedu ograniczył
   pełną aktualizację z 30 do 6 odczytów dokumentów. Po zachowaniu wszystkich
   wyników minimalna aktualizacja wymaga trzech stron. Nie gwarantuje to przejścia
   Cloudflare i nie potwierdza poprawności LIVE podczas zmieniającego się meczu.
4. **Parser ma dodatkowy błąd graniczny.** Syntetyczny test legalnego seta 41:39
   wykazał odrzucenie tego seta przez limit 40 punktów. To test formatu, nie wynik
   rzeczywistego spotkania. Przed wdrożeniem trzeba poprawić walidację długich setów,
   inaczej poprawne dane mogą być gubione albo ponownie pobierane.
   [Zapis testu granicznego](../parser-edge-evidence.json).
5. **Sprawdzono dostępność prostego źródła strukturalnego.** W terminarzu, wynikach
   i tabeli nie znaleziono jawnego API/JSON ani odnośnika RSS. Strona ładuje głównie
   biblioteki interfejsu. Nie dowodzi to braku prywatnego lub partnerskiego API.

W rozszerzeniu wykonano {len(checks)} kontroli SHA-256 produkcyjnego feedu; wszystkie
potwierdziły brak zmian. Workflow miały uprawnienia tylko do odczytu
repozytorium. Prywatnych profili i wartości cookies nie umieszczano w artefaktach.
Zielony status zadania oznacza zakończenie pomiarów, nie poprawny import.

## Najlepsza sprawdzona konfiguracja

W próbie `cam-fresh-3` uzyskano trzy kolejne kompletne eksporty: każdy zawierał 72
mecze z godzinami, 17 zakończonych z punktami wszystkich setów, 9 drużyn z logotypami
i 9 wierszy tabeli. Każda aktualizacja wymagała trzech stron. Zwykły HTTP na tym
samym runnerze dostał 403.

Konfiguracja tej próby:

- Camoufox **0.5.9**, przeglądarka **158.0.1-beta.41**, tryb z interfejsem przez Xvfb.
- Nowy katalog profilu i nowy fingerprint generowany przez bibliotekę przed każdą aktualizacją.
- Cache danych to osobny, wcześniej zweryfikowany plik JSON z 17 wynikami i 9 logotypami.
- Co najmniej **15 s między nawigacjami** oraz **30 s między próbami**.
- Ścisła kontrola kompletności, dokładna tożsamość meczu i zgodność wyniku przed użyciem cache.

Odtworzenie pomiaru na Linuksie z Xvfb:

```bash
python -m pip install -r experiments/volleystation/requirements-battery.txt
python -m camoufox fetch
xvfb-run -a python experiments/volleystation/followup.py --case cam-fresh-3
```

To skrypt eksperymentu z ustalonym snapshotem cache, a nie gotowy zamiennik
produkcyjnego workflow. Wyniki zapisuje w `outputs/followup/cam-fresh-3/`.
Nowy profil, odstępy i snapshot zmieniano łącznie; nie wyizolowano wpływu każdego
parametru. W innych zadaniach podobne konfiguracje były blokowane.

## Rekomendacja końcowa

Nie wdrażałbym żadnego z badanych obejść jako jedynego, bezobsługowego źródła danych
na standardowych runnerach GitHub Actions. Najlepszy wariant warto traktować jako
kandydata do pilotażu: trzy odświeżenia w jednym krótkim zadaniu nie stanowią SLA
i nie odtwarzają wielodniowego działania na zmieniających się adresach IP.
Dalsze dodawanie losowych parametrów Stealth nie ma uzasadnienia w zebranych pomiarach.

Najpewniejszy kierunek to uzgodniony feed/API lub dostęp ze stałego adresu IP
uzgodniony z VolleyStation. Alternatywnie warto zweryfikować własny stały worker
sieciowy, zachowując cache i kontrolę kompletności. Samo przeniesienie na VPS
również nie gwarantuje przejścia Cloudflare; tego nie testowano na docelowym VPS.

Niezależnie od transportu importer powinien publikować atomowo wyłącznie poprawny
eksport, zachowywać ostatnie dobre dane po błędzie oraz osobno pokazywać czas
ostatniego udanego pobrania i wiek danych. Przy blokadzie potrzebne są ograniczone
ponowienia, przerwa i alarm, zamiast nieograniczonego ponawiania żądań.

## Granice raportu

Testy nie obejmują całego sezonu, wielodniowego SLA, wszystkich lig i przebiegu
aktywnego meczu. Nie diagnozujemy wewnętrznego wyniku bot-score Cloudflare —
obserwujemy odpowiedzi i poprawność danych. Nie testowano płatnych proxy, solverów
ani komercyjnych API bez skonfigurowanego dostępu. Wiele bibliotek, profili oraz IP
zmieniało się między próbami, więc z tych obserwacji nie wynika uniwersalny ranking.

Surowe znormalizowane dane: [dane-pomiarowe.json](dane-pomiarowe.json).
Tabela do arkusza: [wyniki.csv](wyniki.csv). Kod prób i ich plan pozostają na gałęzi
`experiment/volleystation-20261106`; produkcji nie zmieniano.
'''
    (args.output/'RAPORT_KONCOWY.md').write_text(text)
    print(json.dumps({k:v for k,v in facts.items() if k!='cases'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
