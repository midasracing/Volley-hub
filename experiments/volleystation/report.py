"""Generate an inspectable report from the recorded network trials."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import median


def render(path):
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    corrected = 0
    for row in records:
        # Earlier lab runs incorrectly rejected a browser's valid cached DOM
        # when the conditional navigation returned HTTP 304. Keep raw logs intact.
        if (not row['ok'] and row['engine'] != 'http' and row.get('status') == 304
                and row.get('valid') and not row.get('challenge')):
            row['ok'] = True
            corrected += 1
    meta = json.loads(path.with_suffix('.meta.json').read_text())
    lines = ['# Próby VolleyStation', '', f"Start: {meta['started_at']}", '',
             '| Silnik | Poprawne odczyty / próby | Challenge | Mediana czasu [s] |',
             '| --- | ---: | ---: | ---: |']
    groups = defaultdict(list)
    for row in records:
        groups[row['engine']].append(row)
    for name, rows in groups.items():
        lines.append(f"| {name} | {sum(bool(r['ok']) for r in rows)} / {len(rows)} | "
                     f"{sum(bool(r.get('challenge')) for r in rows)} | "
                     f"{median(r['elapsed_seconds'] for r in rows):.3f} |")
    lines += ['', '## Zgodność danych', '',
              '| Strona | Liczby odczytanych rekordów | Zgodne dane we wszystkich udanych odczytach |',
              '| --- | --- | --- |']
    for page in ('schedule', 'results', 'standings', 'teams', 'detail'):
        rows = [r for r in records if r['page'] == page and r['ok']]
        counts = sorted({r['parsed_count'] for r in rows})
        hashes = {r['data_sha256'] for r in rows}
        lines.append(f"| {page} | {', '.join(map(str, counts)) or 'brak'} | "
                     f"{'tak' if len(hashes) == 1 and len(rows) > 1 else 'nie / za mało danych'} |")
    errors = [r for r in records if not r['ok']]
    if corrected:
        lines += ['', f'Uwaga: {corrected} odpowiedzi HTTP 304 miało poprawny DOM z cache przeglądarki. '
                  'Raport liczy je jako poprawne odczyty; surowe logi zachowują pierwotną, błędną klasyfikację miernika.']
    if errors:
        lines += ['', '## Nieudane próby', '']
        for row in errors:
            lines.append(f"- {row['engine']}, seria {row['round']}, {row['page']}: "
                         f"HTTP {row.get('status')}; {row.get('error', 'blokada lub niepoprawne dane')}")
    observed = any(r.get('challenge') for r in records)
    on_github = meta.get('environment') == 'github-actions'
    lines += ['', '## Ograniczenia', '',
              ('Test na jednym runnerze GitHub Actions.' if on_github else
               'Krótki test w jednym środowisku. Nie potwierdzono stałości wyjściowego IP.'),
              'Pierwszy odczyt przeglądarki obejmuje uruchomienie procesu. Czasy pozostałych odczytów obejmują transport i parser.',
              ('Próby po restarcie procesów używały tego samego profilu w obrębie zadania.' if meta.get('restart_between_rounds')
               else 'Nie testowano trwałości profilu po restarcie procesu.'),
              ('Wystąpił challenge; wynik dotyczy wyłącznie zapisanych prób.' if observed else
               '**Nie zaobserwowano challenge Cloudflare: brak podstaw do rankingu skuteczności obejścia.**'), '',
              'Wersje: `' + json.dumps(meta['versions'], ensure_ascii=False) + '`',
              f"Tryb z interfejsem: {meta['headful']}. Odstęp: {meta['interval_seconds']} s.", '']
    if meta.get('tls_intercepted'):
        lines += ['Proxy środowiska kończy połączenia TLS. Wynik nie porównuje fingerprintów TLS '
                  'bezpośrednich połączeń przeglądarek z serwerem źródłowym.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('results', type=Path, nargs='?', default=Path(__file__).with_name('results.jsonl'))
    args = parser.parse_args()
    output = args.results.with_suffix('.md')
    output.write_text(render(args.results))
    print(output)
