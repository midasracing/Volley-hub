<p align="center">
  <a href="https://midasracing.github.io/kiedysiatka/">
    <img src="public/kiedy-siatka-logo.svg" alt="Kiedy Siatka?" width="310" />
  </a>
</p>

<p align="center">
  Terminarze, wyniki i tabele polskiej siatkówki. Bez szukania ich na kilku stronach.
</p>

<p align="center">
  <a href="https://midasracing.github.io/kiedysiatka/"><strong>Otwórz aplikację</strong></a>
  &nbsp;·&nbsp;
  <a href="#uruchomienie">Uruchom lokalnie</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/midasracing/kiedysiatka/issues">Zgłoś problem</a>
</p>

---

## O projekcie

**Kiedy Siatka?** to niezależna aplikacja webowa do śledzenia polskich rozgrywek siatkarskich. Została zaprojektowana przede wszystkim z myślą o telefonach, ale działa również na komputerach.

Nie wymaga zakładania konta. Dzięki obsłudze PWA można dodać ją do ekranu głównego, a wybrane drużyny i ligi zapisywać lokalnie w przeglądarce.

## Funkcje

- **Mecze i wyniki** — spotkania na dziś, nadchodzące mecze, rezultaty, sety i status spotkania.
- **Terminarze i tabele** — przeglądanie rozgrywek, grup i drużyn.
- **Ulubione** — szybki dostęp do obserwowanych drużyn i lig; ustawienia są przechowywane przez `localStorage`.
- **Wyszukiwanie** — znajdowanie drużyn i lig bez przeklikiwania kolejnych ekranów.
- **Mobilny interfejs** — widoki dopasowane do małych ekranów, czytelna nawigacja i instalowalna aplikacja PWA.

## Rozgrywki

| Rozgrywki | Dane w repozytorium |
| --- | --- |
| TAURON Liga | [`data/tauron.json`](data/tauron.json) |
| TAURON 1. Liga | [`data/tauron1liga.json`](data/tauron1liga.json) |
| II Liga Mężczyzn | [`data/2liga.json`](data/2liga.json) |
| Pomorska III Liga Mężczyzn | [`data/pomorska3liga.json`](data/pomorska3liga.json) |
| SuperLega Credem Banca (Włochy, mężczyźni) | [`data/italy.json`](data/italy.json) |
| SV.League Men (Japonia, mężczyźni) | [`data/japan.json`](data/japan.json) |

Dostępność i aktualność danych zależą od zewnętrznych źródeł ligowych. Wyniki nie są generowane ani uzupełniane fikcyjnymi wartościami.

## Skąd pochodzą dane?

Dla **II ligi i Pomorskiej III ligi domyślny jest lokalny importer VolleyStation**:
SeleniumBase UC + CDP, a po niepowodzeniu Camoufox. Godziny, wyniki, punkty setów,
tabele i linki transmisji pochodzą wyłącznie z VolleyStation. Nie uzupełniamy ich
z PZPS ani PWZPS. Brakujące hale pozostają puste. Tabele są kopiowane
bezpośrednio ze stron lig, z zachowaniem ich klasyfikacji i wartości; nie przeliczamy ich z wyników.
[Weryfikacja domyślnego importera](local_scraper/DOMYSLNY.md).

Pozostałe ligi mają własne zadania GitHub Actions. Dawne zadania zapisujące II
i Pomorską III ligę zostały wyłączone; lokalny importer aktualizuje `data/*.json`
i opcjonalnie `public/data/*.json`. Komputer i proces `--watch` muszą działać,
żeby te dwie ligi otrzymywały kolejne aktualizacje. Publikacja nowych plików
na GitHub Pages następuje po zatwierdzeniu i wypchnięciu zmian w `data/` do repozytorium.

```text
VolleyStation → lokalny importer II i Pomorskiej III ligi
Pozostałe źródła → istniejące skrypty i GitHub Actions
                         ↓
                    data/*.json
                         ↓
                scripts/sync-data.mjs
                         ↓
                 public/data/*.json
                         ↓
                  React + Vite / PWA
```

Aplikacja regularnie sprawdza dostępność nowych danych, a gdy połączenie się nie powiedzie, zachowuje ostatni pobrany stan. Częstotliwość odświeżania ekranu nie oznacza, że źródło publikuje wyniki z taką samą częstotliwością. Informacje punkt po punkcie wymagają odpowiednio aktualnego zewnętrznego źródła.

## Uruchomienie

Domyślne komendy po [instalacji zależności Python i przeglądarki](local_scraper/README.md#instalacja):

```bash
python scripts/update_2liga.py --watch --public-output public/data/2liga.json
python scripts/update_pomorska3liga.py --watch --public-output public/data/pomorska3liga.json
```

Uruchom je w osobnych terminalach z aktywnym środowiskiem Python. Obie korzystają
z tego samego importera. Dla samego frontendu wymagane są **Node.js 20+** i npm.

```bash
git clone https://github.com/midasracing/kiedysiatka.git
cd kiedysiatka
npm install
npm run dev
```

Po uruchomieniu Vite wyświetli lokalny adres aplikacji.

| Polecenie | Działanie |
| --- | --- |
| `npm run dev` | Serwer developerski |
| `npm test` | Testy logiki (Node Test Runner) |
| `npm run test:e2e` | Testy przeglądarkowe (Playwright) |
| `npm run build` | Build produkcyjny |
| `npm run preview` | Podgląd buildu |

Przed uruchomieniem serwera i budowaniem aplikacji wykonywany jest `scripts/sync-data.mjs`, który synchronizuje pliki JSON do katalogu `public/data/`.

## Włochy i Japonia: oficjalne terminarze bez płatnego API

[Importer ligi włoskiej i japońskiej](scripts/update_international.py) pobiera publiczne terminarze
męskich rozgrywek. Dla SuperLegi czyta dwie części kalendarza `ww2.legavolley.it`
(Andata i Ritorno); dla SV.League używa opublikowanego na stronie terminarza
endpointu `?s=...&y=...&m=...&d=...&mode=ajax`, zwracającego fragmenty HTML.
Nie wymaga przeglądarki, stealth ani płatnego klucza.

Importer zapisuje mecze, drużyny, daty, godziny i oficjalne wyniki zakończonych spotkań
do `data/italy.json` i `data/japan.json`. Godziny japońskich spotkań
są przeliczane z Asia/Tokyo na **Europe/Warsaw**. Jeśli strona pomija godzinę
zakończonego meczu, pozostaje ona pusta, chyba że zachowaliśmy ją
z poprzedniego odczytu. **LIVE dla Włoch i Japonii nie pochodzi z Betclic**:
LegaVolley używa publicznego endpointu
`https://live-cya6b4dqare7anh8.z01.azurefd.net/` (odświeżanie co 30 s w oficjalnym skrypcie strony `https://ww2.legavolley.it/lvc/`). Endpoint zwraca fragment HTML; podczas braku spotkań LIVE zawiera komunikat o nieaktywnym serwisie.
SV.League udostępnia `https://www.svleague.jp/match/detail/{id}/?tab=live`, z historią
akcji i punktów. Oba źródła wymagają testów w trakcie spotkań; importer terminarzy
**nie odświeża punktów w trakcie meczu** i nie udostępnia kursów.

```bash
python -m pip install requests beautifulsoup4
python scripts/update_international.py --league italy
python scripts/update_international.py --league japan
python -m unittest discover -s tests -p 'test_international.py' -v
```

[Pełny raport deep testów](diagnostics/INTERNATIONAL_AUDIT.md) potwierdza zgodność schematu
meczów z TAURON Ligą, komplet 50 wyników rozegranych spotkań i 24 logotypów.
W Japonii nazwy drużyn są w alfabecie łacińskim, a oficjalna tabela pochodzi z SV.League.
Osiem przyszłych japońskich meczów nadal nie ma opublikowanych godzin rozpoczęcia.

[Workflow](.github/workflows/update-international.yml) sprawdza źródła dwa razy dziennie,
weryfikuje parsery i aktualizuje `main` tylko gdy zmieniły się dane.
Błąd HTTP, blokada dostępu, niepełny kalendarz lub przekroczenie limitu pobrań
nie nadpisuje poprawnego pliku. Odczyt publiczny jest bezpłatny, ale dostawcy
**nie gwarantują nieograniczonej liczby żądań**. Źródła są odpytywane centralnie
i oszczędnie; frontend czyta statyczne pliki JSON, nie serwery ligowe.

## Opcjonalny klient kursów Betclic

[`scripts/betclic_odds.py`](scripts/betclic_odds.py) eksportuje JSON z kursami na
zwycięzcę całego meczu, **jeżeli** Betclic oferuje takie spotkanie. Opcje `--country`
obsługują trzy kraje, ale ostatni rzeczywisty test zwrócił mecze **tylko z Polski**;
nie należy traktować tego klienta jako źródła LIVE ani kursów włoskiej i japońskiej ligi. Instalacja i ograniczenia źródła są opisane w
[`docs/betclic.md`](docs/betclic.md). Klient jest niezależny od frontendu i wymaga Pythona 3.10+.

## Diagnostyka scraperów

[`diagnostics/`](diagnostics/) zawiera osobne kopie scraperów II i Pomorskiej III ligi,
test odczytu przez zwykły HTTP i [wyniki porównania źródeł](diagnostics/RESULTS.md).
Sprawdzone zapytania do publicznego endpointu PZPS opisano w
[`diagnostics/PZPS_API.md`](diagnostics/PZPS_API.md).

## Technologia i struktura

**React 19 · Vite 6 · JavaScript · CSS · PWA · GitHub Actions**

| Ścieżka | Zawartość |
| --- | --- |
| [`src/main.jsx`](src/main.jsx) | Główne widoki aplikacji |
| [`src/data.js`](src/data.js) | Pobieranie i normalizacja danych |
| [`src/app.css`](src/app.css) | Układ i style interfejsu |
| [`src/components/`](src/components/) | Nawigacja i elementy UI |
| [`scripts/`](scripts/) | Aktualizowanie danych ligowych |
| [`tests/`](tests/) i [`e2e/`](e2e/) | Testy jednostkowe i przeglądarkowe |
| [`.github/workflows/`](.github/workflows/) | Testy, synchronizacja i publikacja |

W interfejsie wykorzystano element **GlassSurface** z biblioteki React Bits. Informacje o jego pochodzeniu i licencji znajdują się w [pliku atrybucji](src/components/react-bits/LICENSE.md).

## Publikacja

Aplikacja jest publikowana na **GitHub Pages** z gałęzi `main`.

W **Settings → Pages → Build and deployment → Source** musi być wybrane
**GitHub Actions**. Opcja **Deploy from a branch** uruchamia Jekylla, który
publikuje źródłowy `index.html` zamiast buildu Vite i może nadpisać działającą
aplikację, powodując pusty ekran. Nie uruchamiaj obu metod publikacji równocześnie.

Workflow [`deploy-react.yml`](.github/workflows/deploy-react.yml) uruchamia testy, buduje aplikację i publikuje katalog `dist/`. Oddzielne zadania GitHub Actions aktualizują dane poszczególnych rozgrywek.

## Współpraca

Znalazłeś błąd w wynikach, nieaktualny terminarz albo problem z działaniem aplikacji? [Otwórz zgłoszenie](https://github.com/midasracing/kiedysiatka/issues). Pull requesty z poprawkami również są mile widziane.

---

<sub>Kiedy Siatka? jest projektem niezależnym. Dane i materiały pochodzące z zewnętrznych źródeł pozostają własnością ich odpowiednich właścicieli.</sub>

