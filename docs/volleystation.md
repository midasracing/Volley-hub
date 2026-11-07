# Produkcyjny scraper VolleyStation

Jedyny importer II ligi (wszystkie pięć grup) i Pomorskiej III ligi męskiej,
sezon 2026/2027. Domyślnie używa SeleniumBase UC + CDP, a po niepowodzeniu
Camoufox. Działa lokalnie, bez płatnych usług i kluczy API.

Wyniki i tabele są pobierane niezależnie z VolleyStation. Tabela zachowuje
kolejność wierszy, miejsca i wartości opublikowane przez ligę. Nie przeliczamy
jej z wyników; rozbieżności są wyłącznie diagnostyką `source_table_discrepancies`.
Nie uzupełniamy danych z PZPS ani PWZPS. Hala pozostaje `null`, gdy źródło jej
nie podaje. Link transmisji pochodzi z odtwarzacza na stronie konkretnego meczu.

## Instalacja

Wymagane: Python 3.12 oraz Chrome lub Chromium. W katalogu repozytorium:

```bash
python3 -m venv .venv-local-scraper
source .venv-local-scraper/bin/activate
python -m pip install -r requirements-local-scraper.txt
python -m camoufox fetch
```

Na Windows aktywuj środowisko przez `.\.venv-local-scraper\Scripts\Activate.ps1`.
Weryfikację działania przeprowadzono na Linuksie. Pierwsze uruchomienie może
pobrać sterownik Chrome i model fingerprintu. Zalecany jest tryb z oknem.
Na Linuksie bez pulpitu zainstaluj `xvfb` i `xauth`, a polecenia poprzedź
`xvfb-run -a --server-args="-screen 0 1920x1080x24"`.

## Uruchomienie

Jednorazowy import obu lig, kolejno:

```bash
python scripts/update_volleystation.py --league second
python scripts/update_volleystation.py --league pomorska3liga
```

Obie ligi obsługuje jeden plik `scripts/update_volleystation.py`, obok pozostałych
scraperów projektu. Opcja `--league` wybiera ligę; domyślnie jest to Pomorska III liga.
Parsery, walidacja, oba silniki i obsługa procesów są w tym samym skrypcie.
Proces przeglądarki uruchamia odizolowaną kopię tego samego pliku.

Praca ciągła — uruchom każde polecenie w osobnym terminalu:

```bash
python scripts/update_volleystation.py --league second --watch --public-output public/data/2liga.json
python scripts/update_volleystation.py --league pomorska3liga --watch --public-output public/data/pomorska3liga.json
```

Pliki główne to `data/2liga.json` i `data/pomorska3liga.json`. Kopie
`public/data/` odświeżają lokalną aplikację Vite. Komputer i procesy muszą działać.
GitHub Pages otrzymuje kolejne dane po zatwierdzeniu i wypchnięciu zmian `data/`
do repozytorium. `Ctrl+C` zamyka scraper i jego przeglądarkę.

Gdy Chrome nie jest wykrywany, dodaj `--browser /usr/bin/chromium`.
`--engine seleniumbase` lub `--engine camoufox` wybiera konkretny silnik.
`--headless` włącza tryb bez okna; domyślne ustawienie pozostaje z oknem.

## Aktualizacje i błędy

Każdy cykl używa nowego profilu i jednej sesji na import. Odstęp między
nawigacjami wynosi minimum 15 s. Domyślne limity to 40 dokumentów i 900 s na
silnik. Po niepowodzeniu SeleniumBase następuje 30 s przerwy i próba Camoufox.
HTTP 429 przerywa cykl i respektuje `Retry-After`.

Publikowany jest wyłącznie kompletny, zwalidowany feed. Po błędzie źródła
poprzednie dane i ich data aktualizacji pozostają zachowane. Zapis jest atomowy
osobno dla pliku głównego i kopii publicznej. Blokada pliku chroni przed
równoczesnym zapisem tego samego feedu. Po nieudanych cyklach obowiązują przerwy
5, 10, 20, następnie maksymalnie 60 minut; dłuższy `Retry-After` ma pierwszeństwo.
`--watch` czeka domyślnie 900 s po zakończeniu cyklu.

Zakończone wyniki są przechowywane w cache po sprawdzeniu tożsamości, wyniku
i pochodzenia z VolleyStation. Wyniki LIVE są odczytywane na nowo. Checkpointy
szczegółów pozwalają wznowić duży pierwszy import po przerwaniu, bez publikowania
częściowego feedu. Przy dużym imporcie można zwiększyć `--document-budget` do
120 i `--timeout` do 1800 s. `--refresh-details` ponownie odczytuje szczegóły
zakończonych meczów. Dane LIVE odświeżają się zgodnie z cyklami importera.

## Stan i konfiguracja sieci

```bash
python scripts/update_volleystation.py --league second --status
python scripts/update_volleystation.py --league pomorska3liga --status
```

Stan i zdarzenia znajdują się w ignorowanym przez Git `.local-scraper/`.
`--status` pokazuje rzeczywisty wiek danych; próg świeżości to 30 minut,
zmieniany przez `--max-age`. Sam odczyt stanu nie uruchamia przeglądarki.
Po błędzie pojawia się `ALERT`, a jednorazowa aktualizacja zwraca kod 1.

Przeglądarki zachowują weryfikację TLS i konfigurację proxy ze środowiska.
SeleniumBase otrzymuje osobny port CDP dla równoległych procesów. Przy zaufanym
proxy HTTPS i błędzie certyfikatu w Camoufox można podać
`--camoufox-ca /sciezka/do/ca.crt`; na Linuksie wymaga to `libnss3-tools`.
Certyfikat trafia wyłącznie do tymczasowego profilu. Proxy wymagające logowania
obsługuje Camoufox. Nie przenosimy cookies pomiędzy silnikami.

Blokada całego IP lub niedostępność VolleyStation może zatrzymać aktualizacje.
Importer zachowuje wtedy ostatnie poprawne dane z ich rzeczywistą datą.
