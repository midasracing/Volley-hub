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

Dostępność i aktualność danych zależą od zewnętrznych źródeł ligowych. Wyniki nie są generowane ani uzupełniane fikcyjnymi wartościami.

## Skąd pochodzą dane?

Dane zbierają skrypty aktualizujące rozgrywki, uruchamiane przez **GitHub Actions**. W projekcie wykorzystywane są między innymi dane PZPS (II liga) i VolleyStation (Pomorska III liga).

```text
Źródła rozgrywek
        ↓
Skrypty aktualizujące + GitHub Actions
        ↓
     data/*.json
        ↓
 scripts/sync-data.mjs
        ↓
   public/data/*.json
        ↓
    React + Vite
        ↓
  GitHub Pages / PWA
```

Aplikacja regularnie sprawdza dostępność nowych danych, a gdy połączenie się nie powiedzie, zachowuje ostatni pobrany stan. Częstotliwość odświeżania ekranu nie oznacza, że źródło publikuje wyniki z taką samą częstotliwością. Informacje punkt po punkcie wymagają odpowiednio aktualnego zewnętrznego źródła.

## Uruchomienie

Wymagane: **Node.js 20+** i npm.

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

