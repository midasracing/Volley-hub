<p align="right">
  <a href="./README.md">Polski</a> · <strong>English</strong>
</p>

<p align="center">
  <a href="https://midasracing.github.io/kiedysiatka/">
    <img src="public/kiedy-siatka-logo.svg" alt="Kiedy Siatka?" width="310" />
  </a>
</p>

<p align="center">
  Volleyball fixtures, results and standings.<br />
  Without jumping between websites.
</p>

<p align="center">
  <a href="https://midasracing.github.io/kiedysiatka/"><strong>Open the app</strong></a>
  &nbsp;·&nbsp;
  <a href="https://github.com/midasracing/kiedysiatka/issues">Report an issue</a>
</p>

---

## About

**Kiedy Siatka?** is a web app for checking when volleyball matches take place and how they finished. It's designed for phones first, but works on desktop too.

No account needed. You can add it to your phone's home screen as a PWA.

## Features

- **Calendar** — matches by date, with league and group filters.
- **Results** — match scores, set scores and match status.
- **Competitions** — fixtures, standings and teams from selected leagues in Poland, Italy and Japan.
- **Favorites** — save teams and competitions locally in your browser.

## Run locally

Requires **Node.js 20+** and npm.

```bash
git clone https://github.com/midasracing/kiedysiatka.git
cd kiedysiatka
npm install
npm run dev
```

Other commands: `npm test` (tests) and `npm run build` (production build).

One script updates II liga and Pomorska III liga:
[`scripts/update_volleystation.py`](scripts/update_volleystation.py).
[Scraper setup and options (Polish)](docs/volleystation.md).

## Built with

React · Vite · JavaScript · CSS · Rive · PWA · GitHub Pages

---

<sub>An independent project, not affiliated with league organizers. The React Bits component has its own <a href="src/components/react-bits/LICENSE.md">license and attribution</a>.</sub>
