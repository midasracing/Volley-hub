# Deep test: SuperLega i SV.League 2026/27

**Data weryfikacji: 5 listopada 2026.** Wygenerowane przez `scripts/update_international.py`,
sprawdzone poleceniem `python scripts/audit_international.py` i testami
`python -m unittest discover -s tests -p 'test_international.py' -v`.

## Wyniki

| Pole | SuperLega (Włochy) | SV.League Men (Japonia) |
|---|---:|---:|
| Mecze | 132 / 132 | 264 / 264 |
| Drużyny | 12 / 12 | 12 / 12 |
| Logotypy | 12 / 12 | 12 / 12 |
| Rozegrane mecze | 24 | 26 |
| Rozegrane mecze z kompletnymi wynikami setów | 24 / 24 | 26 / 26 |
| Wiersze tabeli | 12 | 12 |
| Brakujące godziny rozpoczęcia | 0 | 8 (przyszłe mecze) |
| Błędy audytu formatu | 0 | 0 |

## Źródła

- **Włochy:** oficjalny terminarz i protokoły meczowe `ww2.legavolley.it`.
  Protokoły `TabellinoGara.asp?IdGara=...` podają rzeczywiste punkty każdego
  seta, więc suma punktów i bilans setów są zgodne z protokołem. Logotypy 12
  klubów pochodzą z oficjalnej listy sezonu 2026/27
  `en.volleyballworld.com/volleyball/competitions/superlega/teams/`.
  Tabela jest **obliczana z opublikowanych wyników** (nie zgadujemy punktów ani rankingu).
- **Japonia:** terminarz z `www.svleague.jp/match/sv/men/` i publicznego
  endpointu `mode=ajax`. Wyniki setów pochodzą z opublikowanych rekordów;
  godziny zakończonych meczów potwierdzono na stronach szczegółów.
  Tabela jest pobierana z oficjalnej
  `www.svleague.jp/match/sv/men/standings/?s=2026`.
- Japońskie nazwy 12 drużyn są mapowane na **oficjalne angielskie nazwy w
  alfabecie łacińskim** według
  `scripts/international_names.py`. Nowy, nieznany skrót powoduje błąd
  zamiast pustej/niepoprawnej nazwy.

## Format zgodny z TAURON

Każdy mecz ma bazowe pola `tauron.json`: `id`, `league`, `competition`,
`date`, `time`, `date_iso`, `round`, `round_source_label`, `phase`,
`status`, `home`, `away`, `home_sets`, `away_sets`, `set_scores`,
`set_points`, `home_points`, `away_points`, `current_points`,
`source_url`, identyfikatory i logotypy obu drużyn, `match_number`,
`term_number`, `venue`, `broadcast`, `details_checked_at`.
Wartości nieopublikowane pozostają puste lub `null`, a przyszłe mecze mają
zerowe wyniki i brak LIVE.

## Nierozwiązane kwestie

1. **Osiem japońskich spotkań w marcu i kwietniu 2027** nie ma jeszcze
   opublikowanej godziny rozpoczęcia. Nie przypisujemy im sztucznej godziny.
2. Nazwy hal japońskich pozostają w oryginalnym zapisie w technicznych
   metadanych `venue`; widoczne nazwy drużyn, zespoły tabeli i terminarz
   używają alfabetu łacińskiego.
3. Strumień punktowy **LIVE** z LegaVolley i SV.League wymaga oddzielnego
   pomiaru podczas aktywnych spotkań. Ten import nie udaje danych na żywo.
4. Publiczne źródła nie deklarują nielimitowanej liczby żądań; centralny
   importer wykonuje odczyty tylko dwa razy dziennie. Snapshoty są
   walidowane przed publikacją, a ostatnia poprawna wersja nie zostaje
   zastąpiona podczas błędu.

## Automatyczna kontrola

Workflow `.github/workflows/update-international.yml` uruchamia 15 testów
parsera oraz niezależny walidator obu pełnych plików JSON. Raport
`international-deep-audit.json` jest dołączany do artefaktów każdego
wykonania (7 dni retencji). Każdy błąd schematu lub niespójność meczu
zatrzymuje publikację plików.
