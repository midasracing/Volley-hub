# Lokalny scraper VolleyStation — bez płatnych usług

Pomorska III Liga Męska oraz wszystkie pięć grup II ligi, sezon 2026/2027. Pierwszy silnik to
SeleniumBase UC + CDP; po niepowodzeniu całej aktualizacji uruchamia się Camoufox.
Oba działają na własnym komputerze. Nie potrzeba kont API ani płatnych proxy.

## Instalacja

Sprawdzono Python 3.12 na Linuksie. Zainstaluj Chrome lub Chromium. Następnie
w głównym katalogu repozytorium:

```bash
python3 -m venv .venv-local-scraper
source .venv-local-scraper/bin/activate
python -m pip install -r requirements-local-scraper.txt
python -m camoufox fetch
```

Na Windows aktywacja środowiska w PowerShell to
`.\.venv-local-scraper\Scripts\Activate.ps1` zamiast `source ...`.
Komendy importera są takie same; działania na Windows nie zweryfikowano w tej sesji.
Pierwszy start może pobrać sterownik Chrome, przeglądarkę Camoufox i model fingerprintu.

Zalecany jest zwykły tryb z oknem. Na Linuksie bez pulpitu zainstaluj Xvfb
(`sudo apt-get install xvfb xauth`) i poprzedź komendę importera:

```bash
xvfb-run -a --server-args="-screen 0 1920x1080x24" python -m local_scraper
```

## Uruchomienie

Jedna aktualizacja repozytoryjnego pliku `data/pomorska3liga.json`:

```bash
python -m local_scraper
```

Wszystkie grupy II ligi, z terminarzami i wynikami VolleyStation oraz dokładnie
dopasowanym uzupełnieniem z PZPS:

```bash
python -m local_scraper --league second
python -m local_scraper --league second --watch --public-output public/data/2liga.json
```

II liga zapisuje `data/2liga.json`; domyślna Pomorska — `data/pomorska3liga.json`.
Obie ligi zwracają format pól odpowiadający TAURON Lidze i TAURON 1. Lidze:
daty ISO, ID meczów i profili drużyn, logotypy w meczach, punkty setów jako obiekty,
sumy punktów i statusy `scheduled`/`live`/`finished`. Hala i numer terminu są `null`,
jeśli źródło ich nie potwierdza. Kanały transmisji nie są zgadywane na podstawie
ukrytego znacznika TV. [Raport audytu zgodności](../audits/20261107/RAPORT.md).

Dla widocznego „TV” importer odczytuje stronę konkretnego meczu i zapisuje
osadzony film YouTube jako `broadcast_urls` (kanoniczny URL `watch?v=...`),
z `broadcast_source_url` i `broadcast_checked_at`. Odświeża te linki przy każdym
cyklu, także dla meczów zaplanowanych oraz wyników uzupełnionych z PZPS.
Sam znacznik bez odtwarzacza pozostaje `broadcast: ["TV"]`, bez zgadywanego URL.
Aplikacja pokazuje link „Transmisja · YouTube” lub „Nagranie · YouTube”.
Publikacja odtwarzacza na stronie ligi nie potwierdza dostępności filmu ani rozpoczęcia emisji.

Praca ciągła, z 15 minutami przerwy po zakończeniu każdej aktualizacji, oraz
automatyczna kopia dla lokalnej aplikacji Vite:

```bash
python -m local_scraper --watch --every 900 \
  --public-output public/data/pomorska3liga.json
```

W drugim terminalu uruchom `npm run dev`. Kopia w `public/data/` jest aktualizowana
atomowo po każdym poprawnym imporcie, więc nie trzeba ponownie uruchamiać Vite.
Przy pierwszym uruchomieniu Vite jego skrypt `predev` kopiuje dane z `data/`.
Komputer i proces scrapera muszą pozostać uruchomione; `Ctrl+C` kończy pracę.

Jeśli Chrome nie jest wykrywany automatycznie:

```bash
python -m local_scraper --browser /usr/bin/chromium
```

Próba z osobnym wyjściem, z użyciem istniejącego feedu jako cache:

```bash
python -m local_scraper --output .local-scraper/proba/feed.json \
  --seed data/pomorska3liga.json
```

`--seed` jest używany tylko wtedy, gdy plik wyjściowy jeszcze nie istnieje.
Stary plik nie uzyskuje nowej daty aktualizacji wyłącznie przez użycie go jako cache.
Możliwy jest import bez cache: wymagane szczegóły i logotypy zostaną pobrane ze źródła.
Może to potrwać kilka minut i nadal może zostać zablokowane.

## Co dzieje się po błędzie

1. Każdy silnik działa w osobnym procesie i zachowuje jedną sesję podczas importu.
   Każda następna aktualizacja zaczyna się od nowej sesji/profilu.
2. Minimalny odstęp między rozpoczęciami nawigacji wynosi 15 s; maksymalnie
   40 dokumentów na silnik i 900 s na cały proces silnika. Po błędzie dostępu
   sesja nie generuje dalszych żądań.
3. Po niepowodzeniu UC + CDP następuje 30 s przerwy i jedna próba przez Camoufox.
   HTTP 429 przerywa cały cykl i respektuje `Retry-After` zamiast przełączać silnik.
4. Jeśli oba silniki zawiodą albo kandydat jest niekompletny, poprzedni feed
   zachowuje dokładnie swoją treść i datę. Konsola pokazuje `ALERT`, a pojedyncze
   uruchomienie kończy się kodem 1.
5. Po nieudanym cyklu obowiązuje przerwa 5, 10, 20, następnie maksymalnie 60 minut.
   Dłuższy `Retry-After` ma pierwszeństwo. Stan przerwy przetrwa restart procesu.
   `--watch` dodatkowo zachowuje zadany odstęp między cyklami.
6. Blokada pliku zapobiega równoczesnemu uruchomieniu dwóch lokalnych importerów
   tego samego feedu. Procesy przeglądarki są zamykane także po timeout i `Ctrl+C`.

Każdy kandydat jest sprawdzany w procesie silnika i ponownie przed zapisem:
Pomorska wymaga minimum 60 meczów oraz 9 drużyn i wierszy tabeli; II liga
kompletnych pięciu grup i 532 spotkań sezonu zasadniczego. Sprawdzane są logotypy, godziny,
unikalność meczów, pełne legalne sety, zgodność wyników i punktów z tabelą.
Poprzednio znane mecze i zakończone wyniki nie mogą po cichu zniknąć.
Oficjalne wycofanie meczu lub zmiana fazy wymaga świadomej aktualizacji konfiguracji/cache.

Cache setów jest wykorzystywany przy dokładnej tożsamości meczu i zgodnym wyniku.
Poprawne szczegóły są zapisywane oddzielnie w `details-cache.json` po każdym
odczycie, dzięki czemu import przerwany limitem czasu lub blokadą może zostać
wznowiony bez utraty już pobranych szczegółów. Ten cache nie jest publikowany
jako kompletny feed. Przy pierwszym imporcie z dużą liczbą zakończonych meczów
może być potrzebnych kilka cykli; można też zwiększyć `--document-budget`
(maksymalnie 120) i `--timeout` (maksymalnie 1800 s).
Jeśli świeża tabela ujawnia zmianę małych punktów, powiązane szczegóły są pobierane
ponownie. Pełny audyt szczegółów można wymusić przez `--refresh-details`.
Legalne sety 41:39 i dłuższe oraz przedłużone tie-breaki są obsługiwane.

Zapis do `data/` i opcjonalnej kopii `public/data/` jest atomowy dla każdego pliku
osobno. Jeśli zapis kopii nie powiedzie się, zgłaszany jest błąd publikacji;
poprawny plik główny może już zawierać nową wersję, a poprzednia kopia pozostaje czytelna.
Inny silnik nie jest uruchamiany do naprawiania błędu dysku.

## Stan i diagnostyka

```bash
python -m local_scraper --status
```

Wynik zawiera `feed_status` (`fresh`, `stale`, `missing`, `invalid`), `age_seconds`,
datę ostatniego sukcesu, użyty silnik i opis ostatnich prób. Próg świeżości
wynosi 30 minut; można go ustawić przez `--max-age`. Kod wyjścia to 0 tylko dla
poprawnego, świeżego feedu i udanego ostatniego cyklu.

Przy niestandardowym `--output` lub `--state-dir` podaj je również przy `--status`.
Sam odczyt stanu nie uruchamia przeglądarki ani nie odświeża daty danych.

Domyślny stan znajduje się w `.local-scraper/<identyfikator-pliku>/status.json`,
a zdarzenia w `events.jsonl` w tym samym katalogu. Logi mają rotację: do czterech
plików po około 1 MB. Nie zapisują pełnego HTML, wartości cookies ani profili.
Jeśli środowisko ma `HTTPS_PROXY`/`HTTP_PROXY`, przeglądarki korzystają z niego;
zaufanie TLS pozostaje włączone. Na zwykłym komputerze bez tych zmiennych łączą się
bezpośrednio. Nie przenoś cookies pomiędzy silnikami.

Jeśli używasz własnego proxy HTTPS ze znanym, zaufanym CA, a Camoufox zgłasza
`SEC_ERROR_UNKNOWN_ISSUER`, na Linuksie można zainstalować `libnss3-tools` i podać
`--camoufox-ca /sciezka/do/zaufanego-ca.crt`. Certyfikat jest importowany wyłącznie
do tymczasowego profilu Camoufox. Nie zmienia to globalnego magazynu certyfikatów
i nie wyłącza sprawdzania TLS. Na zwykłym połączeniu bez takiego proxy ta opcja
nie jest potrzebna; Chrome korzysta z własnego/systemowego magazynu zaufania.

`--engine seleniumbase` i `--engine camoufox` pozwalają sprawdzić osobne silniki.
`--headless` jest opcją diagnostyczną; wcześniejsze dobre wyniki dotyczą trybu z oknem.

## Sprawdzenie

```bash
python -m unittest discover -s tests -p 'test_local_scraper.py' -v
python -m pip check
```

Testy offline obejmują cache, pełny import na fixture HTML, korektę małych punktów,
długie sety, brakujące mecze, błędy silników, nieprawidłowe „sukcesy”, zachowanie
starego pliku, przełączenie silników, blokadę równoległości, ograniczenie czasu
i zamknięcie procesu potomnego. [Wynik prób rzeczywistych](WERYFIKACJA.md).

To rozwiązanie zwiększa odporność, ale nie zapewnia nieprzerwanie świeżych danych
przy blokadzie całego IP. Cache podtrzymuje dostępność ostatnich poprawnych danych;
ich rzeczywisty wiek pozostaje widoczny w stanie i przez `updated_at` w aplikacji.
Wynik trwającego meczu jest odczytywany ze szczegółów podczas cyklu aktualizacji;
nie jest przechowywany w cache wyników zakończonych. Nie oznacza to stałego strumienia
punkt po punkcie — kolejne odczyty zależą od wybranego harmonogramu.

## Osobny test hal

Publiczne szczegóły PZPS udostępniają lokalizacje II ligi, a publiczne obsady
PWZPS — wybrane bieżące mecze Pomorskiej III ligi.
[Wynik testu 532 stron II ligi i trzech meczów III ligi](../audits/20261107/venues/RAPORT.md).
Narzędzia `python -m local_scraper.capture_venues` i `python -m local_scraper.venue_audit`
służą do oddzielnego audytu; nie zmieniają głównych feedów ani nie rozwiązują
automatycznie konfliktów godzin między źródłami.
