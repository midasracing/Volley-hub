<div align="center">

  <br />

  **Mecze, wyniki i rozgrywki. Cała siatkówka w jednym miejscu.**

  Mobilne centrum polskiej siatkówki — od terminarza po ostatni set.

  <br />

  <a href="https://midasracing.github.io/Volley-hub/">
    <img src="https://img.shields.io/badge/OTWÓRZ_APLIKACJĘ-8BABFF?style=for-the-badge&amp;logo=githubpages&amp;logoColor=0E1118" alt="Otwórz Volley Hub" />
  </a>
  <a href="https://github.com/midasracing/Volley-hub/actions/workflows/deploy-react.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/midasracing/Volley-hub/deploy-react.yml?branch=main&amp;style=for-the-badge&amp;label=GitHub%20Pages&amp;logo=githubactions" alt="Status wdrożenia GitHub Pages" />
  </a>

  <br />
  <br />

  <a href="#funkcje">Funkcje</a> ·
  <a href="#rozgrywki">Rozgrywki</a> ·
  <a href="#szybki-start">Szybki start</a> ·
  <a href="#jak-to-działa">Jak to działa</a> ·
  <a href="#publikacja">Publikacja</a>
</div>

---

## 🏐 Siatkówka ma swoje miejsce

**Volley Hub** to aplikacja webowa stworzona z myślą o szybkim sprawdzaniu tego, co dzieje się na polskich parkietach. Bez przeskakiwania między stronami: wybierasz ligę, sprawdzasz mecz i wracasz do gry.

Projekt powstał w podejściu **mobile-first**. Działa w przeglądarce i jako **PWA**, które można dodać do ekranu głównego telefonu.

## ✨ Funkcje

| | |
| :--- | :--- |
| **🏟️ Mecze i wyniki**<br />Mecze dnia, nadchodzące spotkania, wyniki, sety i status rozgrywanego meczu. | **📅 Terminarze i tabele**<br />Kalendarz meczów, filtry lig i grup oraz widoki rozgrywek i drużyn. |
| **⭐ Ulubione pod ręką**<br />Zapisuj wybrane drużyny i ligi — pozostają w pamięci przeglądarki dzięki `localStorage`. | **🔎 Szybkie wyszukiwanie**<br />Szukaj drużyn i lig bez przekopywania się przez kolejne zestawienia. |
| **📱 PWA i mobilny interfejs**<br />Aplikacja z manifestem i service workerem, dostosowana do wygodnej obsługi na telefonie. | **🎨 Dopieszczone detale**<br />Ciemny interfejs, karty wyników, animowane logo TechText i nawigacja FluidGlass. |

> [!NOTE]
> Dostępność wyników i ich aktualność zależą od danych pobieranych ze źródeł ligowych. Nie generujemy fikcyjnych wyników.

## 🏆 Rozgrywki

| Liga | Dane |
| :--- | :--- |
| **TAURON Liga** | [`data/tauron.json`](data/tauron.json) |
| **TAURON 1. Liga** | [`data/tauron1liga.json`](data/tauron1liga.json) |
| **II Liga Mężczyzn** | [`data/2liga.json`](data/2liga.json) |
| **Pomorska III Liga Mężczyzn** | [`data/pomorska3liga.json`](data/pomorska3liga.json) |

Dane są aktualizowane przez istniejące skrypty i zadania **GitHub Actions**. Dla II ligi wykorzystywane są dane PZPS, a dla Pomorskiej III ligi — VolleyStation.

## 🚀 Szybki start

Potrzebujesz **Node.js 20+** i **npm**.

```bash
git clone https://github.com/midasracing/Volley-hub.git
cd Volley-hub
npm install
npm run dev
```

Następnie otwórz lokalny adres wskazany przez Vite.

| Komenda | Działanie |
| :--- | :--- |
| `npm run dev` | Start serwera developerskiego |
| `npm test` | Testy logiki (Node Test Runner) |
| `npm run test:e2e` | Testy przeglądarkowe (Playwright; wymaga przygotowanego środowiska) |
| `npm run build` | Produkcyjny build do `dist/` |
| `npm run preview` | Podgląd lokalnego buildu |

## ⚙️ Jak to działa

```text
Źródła ligowe
      │
      ▼
GitHub Actions + skrypty aktualizujące dane
      │
      ▼
   data/*.json
      │
      │  scripts/sync-data.mjs
      ▼
 public/data/*.json
      │
      ▼
  React + Vite  →  GitHub Pages  →  Przeglądarka / PWA
```

Przed `npm run dev` i `npm run build` skrypt `scripts/sync-data.mjs` kopiuje bieżące dane z `data/` do `public/data/`. Interfejs następnie pobiera i normalizuje dane na potrzeby widoków meczowych.

### Stack

![React](https://img.shields.io/badge/React-19-149ECA?style=flat-square&logo=react&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-6-646CFF?style=flat-square&logo=vite&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES_Modules-F7DF1E?style=flat-square&logo=javascript&logoColor=111111)
![PWA](https://img.shields.io/badge/PWA-Mobile_First-7D8DA8?style=flat-square&logo=pwa&logoColor=white)
![GitHub Pages](https://img.shields.io/badge/Hosting-GitHub_Pages-222222?style=flat-square&logo=github&logoColor=white)

**Frontend:** React 19, Vite 6, JavaScript, CSS  
**Doświadczenie:** mobile-first, PWA, `localStorage`, service worker  
**Testy i automatyzacja:** Node Test Runner, Playwright, GitHub Actions  
**Interfejs:** React Bits TechText, GlassSurface (liquid glass)

<details>
<summary><strong>📂 Struktura projektu</strong></summary>

```text
Volley-hub/
├── .github/workflows/   # testy, aktualizacje danych i deploy
├── data/                # źródłowe pliki JSON rozgrywek
├── public/              # manifest, service worker, dane dla aplikacji
├── scripts/             # synchronizacja i skrypty danych
├── src/                 # aplikacja React, widoki i komponenty
├── tests/               # testy logiki
├── e2e/                 # testy przeglądarkowe
├── vite.config.js       # konfiguracja buildu
└── package.json
```

Główne miejsca do poznania kodu:
- [`src/main.jsx`](src/main.jsx) — główne widoki i nawigacja.
- [`src/data.js`](src/data.js) — pobieranie i normalizacja danych.
- [`src/app.css`](src/app.css) — design system i style aplikacji.
- [`src/components/react-bits/GlassSurface.jsx`](src/components/react-bits/GlassSurface.jsx) — refrakcyjne szkło dolnej nawigacji i wyszukiwarki.

</details>

## 🌐 Publikacja

**Hosting: GitHub Pages.** Aplikacja publikowana jest z gałęzi `main` przez workflow [**Deploy React to GitHub Pages**](.github/workflows/deploy-react.yml).

1. GitHub Actions weryfikuje, czy należy wykonać nowy build.
2. Instalowane są zależności, uruchamiane testy i wykonywany jest `npm run build`.
3. Zawartość `dist/` jest publikowana na GitHub Pages.

W ustawieniach repozytorium w **Settings → Pages → Build and deployment** jako **Source** powinno być wybrane **GitHub Actions**.

<p align="center">
  <a href="https://midasracing.github.io/Volley-hub/"><strong>↗ Otwórz Volley Hub</strong></a>
  &nbsp;·&nbsp;
  <a href="https://github.com/midasracing/Volley-hub/actions"><strong>Zobacz automatyzacje</strong></a>
  &nbsp;·&nbsp;
  <a href="https://github.com/midasracing/Volley-hub/issues"><strong>Zgłoś problem</strong></a>
</p>

---

<div align="center">

**Made for the love of volleyball. 🏐**

<sub>Volley Hub jest niezależnym projektem. Materiały i dane zewnętrzne należą do ich właścicieli.</sub>

<sub>Komponenty TechText i GlassSurface pochodzą z React Bits — [informacje licencyjne i atrybucja](src/components/react-bits/LICENSE.md).</sub>

</div>
