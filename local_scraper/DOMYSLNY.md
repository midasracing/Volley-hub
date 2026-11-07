# Weryfikacja domyślnego importera — 7 listopada 2026

Domyślnym importerem II ligi (pięć grup) i Pomorskiej III ligi jest lokalny
SeleniumBase UC + CDP z zapasowym Camoufox. Obie dotychczasowe komendy
`scripts/update_2liga.py` i `scripts/update_pomorska3liga.py` uruchamiają ten importer.
Jedyne źródło danych to VolleyStation. Stare harmonogramy zapisujące te ligi
zostały zastąpione ręcznymi zadaniami testowymi bez uprawnień zapisu.

## Próba rzeczywista

Szczegóły bieżącego importu i skróty opublikowanych plików zawiera
[default-verification.json](default-verification.json). Próby wykonano na Linuksie
z Chromium 156, Camoufox i Xvfb, z włączoną weryfikacją TLS. Import korzystał z wcześniej
zweryfikowanych wyników jako cache; wszystkie nowe wyniki i aktualne listy/tabele
odczytywał ze źródła. Próba używa domyślnych limitów: 40 dokumentów i 900 s na silnik. Checkpointy szczegółów pozwalają
wznawiać większy pierwszy import bez publikowania częściowego feedu.

Próby wcześniejszych silników, w tym rzeczywisty Camoufox i wymuszone
przełączenie po braku Chrome, opisuje [WERYFIKACJA.md](WERYFIKACJA.md).
Wynik jednej sesji nie gwarantuje przyszłej dostępności źródła ani całego IP.

Zakończony import: **532 spotkania II ligi (165 wyników końcowych)** i
**72 spotkania Pomorskiej III ligi (19 wyników końcowych)**. Pełne feedy zapisał
Camoufox. Po naprawie konfiguracji SeleniumBase osobny import Pomorskiej III ligi
również zakończył się sukcesem. Wszystkie mecze mają godziny, identyfikatory
VolleyStation i logotypy; wszystkie wyniki końcowe mają komplet punktów setowych.
Tabele grup 2 i 3 różniły się od zestawienia wyników — zachowano je dokładnie
według publikacji VolleyStation, bez przeliczania.

## Poprawki ujawnione podczas próby

- Etykieta „Na żywo” nie gubi meczu, także przy wyniku 0:0.
- Odtwarzacz YouTube pozostaje wykrywany, gdy etykieta LIVE zastępuje TV. Karta 0:0 bez etykiety LIVE także może wyprzedzać tabelę.
- Tabela i wyniki są niezależnymi publikacjami VolleyStation. Tabela jest
  kopiowana ze strony z zachowaniem wierszy, kolejności, miejsc i punktów.
  Nie jest odtwarzana z wyników. Różnice w licznikach są diagnostyką
  `source_table_discrepancies`; nie zatrzymują importu i nie zmieniają danych.
  Testy obejmują opóźnienie tabeli, zmianę kolejności i karę punktową.

## Testy

- Python: 51 testów (32 importera, 10 zgodności formatu, 3 komend/audytu,
  6 regresji TAURON).
- JavaScript: 23 testy.
- Dwie równoległe sesje Chrome otrzymały osobne porty CDP. Obie odrzuciły
  niezaufany certyfikat TLS; żadna nie miała flag wyłączających sprawdzanie TLS.
- Kontrola importów i błędów Pythona: Ruff `--select F,I`; `git diff --check`.
- Przeglądarka: 38/39 istniejących testów mobilnego Chromium przeszło.
  Jedyny błąd, odstęp logo od nagłówka (`e2e/app.spec.js:109`, 51 px zamiast
  mniej niż 35 px), odtworzono także na niezmienionym `main` z commitu
  `761704b960c81f05a523862deddf85b070ed0888`. Ten test pozostaje bez zmian.
- Dodatkowa próba UI przeszła: link transmisji jest klikalny, tabela zachowuje
  wiersze źródła, a informacja o różnicach znika po wybraniu innej grupy.

## Działanie ciągłe i publikacja

Na własnym komputerze należy uruchomić osobno obie komendy z `--watch`, zgodnie
z [instrukcją](README.md#uruchomienie). Jednorazowy test nie uruchamia stałej usługi.
Lokalny zapis odświeża aplikację Vite przez `--public-output`. GitHub Pages otrzyma
kolejne dane po zatwierdzeniu i wypchnięciu `data/*.json` do repozytorium.
