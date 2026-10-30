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

Publikacja odbywa się z gałęzi main. W GitHub Settings > Pages > Build and deployment > Source należy wybrać GitHub Actions. Workflow Deploy React to GitHub Pages buduje dist/ i publikuje gotową aplikację. Samo serwowanie katalogu głównego repo bez buildu nie uruchomi Reacta.

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

Stary interfejs vanilla JS oraz nieaktualne kopie komponentu szkła zostały usunięte. W repo pozostaje tylko działająca aplikacja React.

## Logo & floating header (React Bits TechText)
The header uses [React Bits / TechText](https://reactbits.dev/text-animations/tech-text)
by David Haz (MIT + Commons Clause; included attribution at
`src/components/react-bits/LICENSE.md`). It is an **actual local component**,
not an imitation and not the previous Rive wordmark. `intro="assemble"`
starts automatically on page load; sweeping, drag, click and hover interactions
are disabled to keep phone navigation light. After its 1.55-second reveal the
canvas rests. `prefers-reduced-motion`, slow JS loading and missing canvas
show an immediately readable HTML wordmark.

The old top bar is removed: `vh-floating-head` positions the signature top-left
and a separate accessible glass search bubble top-right. This is a visual change
only; search, match data, favorites and the bottom navigation keep their behavior.

Rive is intentionally **not used for the logo**. It may still be used later
for useful interaction-driven animations elsewhere in the PWA.

## Repository cleanup (2026-10-30)
The deployed site is **Vite + React only**. The previous root-level plain-JS app, legacy CSS, duplicate fluid-glass implementation, and old root-level service worker/manifest were removed. The only source-of-truth files for the web app are `src/`, `matches-ios.css`, `fluid-glass-component.css`, `public/`, and the active data/scraper workflows.

The bottom navigation uses the **original React FluidGlass component** at `src/FluidGlass.jsx`. Active-tab highlighting no longer uses an overlapping CSS gradient capsule. The search bubble uses the same React glass component with a lightweight, opaque fallback if WebGL or accessibility settings prevent the shader. Any app-critical text and actions remain regular accessible HTML.
