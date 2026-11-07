# II liga i Pomorska III liga — wyłącznie VolleyStation

**Importer i zapisane feedy korzystają wyłącznie z VolleyStation. Usunięto
uzupełnianie godzin i punktów setów z PZPS. Nie włączono katalogu hal PZPS/PWZPS.**

| Zakres zachowanego snapshotu | Mecze | Zakończone z pełnymi setami | Zaplanowane | LIVE |
| --- | ---: | ---: | ---: | ---: |
| II liga, wszystkie 5 grup | 532 | 152 | 380 | 0 |
| Pomorska III liga | 72 | 17 | 54 | 1 |

Wszystkie 604 mecze mają godziny i wymagane pola wspólnego formatu. Tabele,
wyniki i punkty setów są zgodne z przechwyconymi stronami VolleyStation.
Sześć odnośników YouTube nadal pochodzi z odtwarzaczy na stronach meczów.
`venue` i `term_number` pozostają `null`; nie wypełnia ich inne źródło.

## Zmiana importera

- II liga pobiera terminarze, wyniki i tabele pięciu grup oraz listę drużyn z VolleyStation.
- Punkty wszystkich 152 zakończonych meczów II ligi odczytano ze stron ich meczów
  VolleyStation. Do istniejącego materiału dodano 142 brakujące dokumenty przez
  zwykłe HTTPS, bez logowania i płatnych usług, z odstępem co najmniej 5 sekund.
- Oba feedy i każda grupa II ligi zawierają `source_policy: "volleystation_only"`.
- Cache z innych źródeł jest pomijany osobno dla punktów i godzin. Dane są ponownie
  pobierane z VolleyStation. Walidacja przed publikacją sprawdza pochodzenie;
  sam znacznik polityki nie zastępuje kontroli adresów źródłowych.
- Transport lokalnego importera dopuszcza wyłącznie dwa właściwe hosty VolleyStation.
- `scripts/update_2liga.py` uruchamia ten sam lokalny importer. Dawny workflow
  zapisujący dane z PZPS nie ma harmonogramu ani uprawnień zapisu; pozostały
  w nim wyłącznie ręczne testy offline. Lokalna aktualizacja ciągła wymaga `--watch`.
- Historyczne raporty porównujące PZPS/PWZPS pozostają archiwum. Nie są źródłem feedów.

## Sprawdzenie

Porównanie obu zestawów przechwyceń źródłowych przeszło bez różnic dla wszystkich
604 meczów. Obejmuje niezależny od parsera odczyt kart, tabel, godzin i punktów
setów oraz sprawdzenie pełnego formatu i pochodzenia. Strony główne UC + CDP
oraz Camoufox pochodzą z wcześniejszych prób; nowe szczegóły HTTP są wspólnym
materiałem obu odtworzeń. Nie jest to nowy podwójny odczyt całego sezonu przez przeglądarki.

Sprawdzono też ponowny import z cache: II liga zachowuje komplet 152 wyników bez
ponownego pobierania ich szczegółów; nadal odczytuje bieżące strony list i linki TV.
Pomorska ponownie odczytuje szczegóły LIVE. Wszystkie wywołania mają host VolleyStation.

**42 testy Python, 23 testy JavaScript, kontrola stylu i build produkcyjny przeszły.**
Nowe regresje sprawdzają odrzucanie punktów i godzin z obcego cache, niezależną
walidację źródła przed publikacją oraz blokadę nawigacji poza VolleyStation.

## Aktualność

To migracja źródła istniejącego snapshotu. Zachowano `updated_at` stron głównych:
II liga **07.11.2026, 11:58 UTC**, Pomorska **07.11.2026, 12:01 UTC**.
Dodatkowe szczegóły mają własne czasy odczytu w metadanych. Nie odświeżono daty
całego terminarza wyłącznie z powodu migracji i odtworzenia audytu.
**Te liczby nie są zapewnieniem bieżącego stanu wyników z późniejszej godziny.**
Godziny pozostają zgodne z VolleyStation także wtedy, gdy inne serwisy pokazują
inny termin. Aktualizacje działają po uruchomieniu lokalnego importera:

```bash
python -m local_scraper --league second --watch --public-output public/data/2liga.json
python -m local_scraper --watch --public-output public/data/pomorska3liga.json
```

Na początku import bez zaufanego cache może wymagać kilku cykli na zebranie
wszystkich historycznych szczegółów. Poprawne odczyty są zapisywane w checkpointach;
niekompletny kandydat nie zastępuje opublikowanego feedu.

- [Pełny raport porównania i manifest źródeł](report.json)
- [Kontrola migracji, cache i testów](migration.json)
- [Aktualny snapshot II ligi](../../../data/2liga.json)
- [Aktualny snapshot Pomorskiej III ligi](../../../data/pomorska3liga.json)
