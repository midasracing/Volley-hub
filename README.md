# Volley Hub — React 19

Mobilna aplikacja siatkarska PWA oparta na React 19 + Vite 6. Językiem wizualnym całej strony jest zakładka Mecze: duża typografia Barlow, jasne karty wyników, ciemny interfejs i zaokrąglona nawigacja.

## Funkcje

- Główna: mecze dnia, nadchodzące mecze, rozgrywki i ulubione.
- Mecze: kalendarz, filtry lig i grup, status na żywo, wyniki i sety.
- Rozgrywki: terminarz, wyniki, tabela oraz drużyny każdej dostępnej ligi.
- Ulubione: drużyny i ligi zapisywane w localStorage (zgodność z kluczem vh-favs).
- Wyszukiwarka drużyn i lig, czytelne stany ładowania, pustych wyników i błędów.
- PWA: manifest, cache aplikacji i network-first dla danych ligowych.

## Lokalnie

Node 20+:

    npm install
    npm run dev
    npm test
    npm run build
    npm run preview

Przed uruchomieniem Vite i buildem skrypt scripts/sync-data.mjs kopiuje najnowsze dane z data/*.json do public/data/*.json. Istniejące skrypty Python i workflow aktualizują nadal folder data, bez zmiany ich działania.

## Publikacja

Po scaleniu pull requesta do main ustaw w GitHub Settings > Pages > Build and deployment > Source na GitHub Actions. Workflow Deploy React to GitHub Pages buduje dist/ i publikuje gotową aplikację. Samo serwowanie katalogu głównego repo bez buildu nie uruchomi Reacta.

## Źródła

- data/tauron.json — TAURON Liga
- data/tauron1liga.json — TAURON 1. Liga
- data/2liga.json — II Liga Mężczyzn (PZPS)
- data/pomorska3liga.json — Pomorska III Liga (WYŁĄCZNIE VolleyStation)

Nie generujemy fikcyjnych wyników. Aktualność danych zależy od działania scraperów i cyklu synchronizacji.

## Architektura

- src/main.jsx — wspólne drzewo React (nawigacja, Mecze, Główna, Rozgrywki, Ulubione, wyszukiwarka)
- src/data.js — pobieranie, transformacja i normalizacja danych
- src/app.css oraz matches-ios.css — wspólny design system
- public — manifest, service worker, kopiowane dane
- tests — testy logiki danych

Stare app.js, matches-ios.js i fluid-glass-react.js pozostają wyłącznie dla porównania i nie są ładowane przez nowy index.html.
