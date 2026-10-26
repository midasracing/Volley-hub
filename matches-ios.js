/* =========================================================
   VOLLEY HUB — nowy widok „Mecze” (styl iOS)
   Wczytaj ten plik PO app.js. Nie wymaga zmian w app.js.
   Korzysta z danych i funkcji, które app.js już ma
   (loadTauronData, uniqueMatches, isMatchLive, teamLogoMarkup...).
   ========================================================= */
(function () {
  "use strict";
  if (window.__vhMatchesIos) return;

  const page = document.getElementById("matches");
  if (
    !page ||
    typeof go !== "function" ||
    typeof renderOfficialView !== "function" ||
    typeof loadTauronData !== "function"
  ) {
    console.warn("Volley Hub: nowy widok Mecze nie wystartował (czy app.js jest wczytany wcześniej?).");
    return;
  }
  window.__vhMatchesIos = true;

  /* ---------- Ustawienia: jakie ligi pokazujemy ---------- */
  // key = nazwa kanału danych w app.js (leagueFeeds). Nowe ligi dopisujesz tutaj.
  const LEAGUES = [
    { key: "men", name: "Tauron Liga Mężczyzn", flag: "🇵🇱" },
    { key: "first", name: "Tauron 1. Liga Mężczyzn", flag: "🇵🇱" },
    { key: "second", name: "II Liga Mężczyzn", flag: "🇵🇱" },
    { key: "pomorska", name: "Pomorska III Liga Męska", flag: "🇵🇱" },
  ];
  const DAY_NAMES = ["NIEDZ.", "PON.", "WT.", "ŚR.", "CZW.", "PT.", "SOB."];
  const STRIP_DAYS = 46; // ile dni ma pasek (7 wstecz + reszta do przodu)

  /* ---------- Ikony ---------- */
  const svg = (inner, size) =>
    '<svg viewBox="0 0 24 24" width="' + size + '" height="' + size +
    '" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    inner + "</svg>";
  const ICONS = {
    home: '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v9.5h13V10"/><path d="M10 19.5v-5h4v5"/>',
    matches: '<rect x="3.5" y="5" width="17" height="15.5" rx="3"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    competitions: '<path d="M8 4h8v5a4 4 0 0 1-8 0V4z"/><path d="M8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4"/><path d="M12 13v4M8.5 20h7M10 17h4"/>',
    favorites: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  };

  /* ---------- Pomocnicze ---------- */
  const byId = (id) => document.getElementById(id);
  const pad = (n) => String(n).padStart(2, "0");
  const keyOf = (d) => d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const noon = (d) => { const x = new Date(d); x.setHours(12, 0, 0, 0); return x; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDate = (d) => new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "short", year: "numeric" }).format(d);
  function matchDate(m) {
    const p = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(m.date || "");
    return p ? new Date(+p[3], +p[2] - 1, +p[1], 12) : selected;
  }
  function logo(name) {
    if (typeof teamLogoMarkup === "function") return teamLogoMarkup(name);
    return '<span class="team-mark">' + esc((name || "?").trim().slice(0, 2).toUpperCase()) + "</span>";
  }

  /* ---------- Stan ---------- */
  let selected = noon(new Date());
  let stripStart = addDays(selected, -7);
  let liveOnly = false;
  let onlyLeague = null; // ustawiane po wejściu z zakładki Rozgrywki → „Terminarz”
  let loading = false;
  let errors = [];
  let lastHtml = "";
  let inGo = false;
  const store = {}; // kopia pobranych danych: store[key] = dane ligi

  /* ---------- Budowa ekranu ---------- */
  const root = document.createElement("div");
  root.id = "ios-matches";
  root.innerHTML =
    '<div class="im-top">' +
      '<div class="im-actions">' +
        '<button class="im-round" id="im-cal" type="button" aria-label="Wybierz datę">' + svg(ICONS.matches, 22) + "</button>" +
        '<button class="im-round" id="im-live" type="button" aria-label="Pokaż tylko mecze na żywo" aria-pressed="false"><i class="im-dot"></i></button>' +
      "</div>" +
      "<h1>Mecze</h1>" +
    "</div>" +
    '<div class="im-strip" id="im-strip" role="tablist" aria-label="Wybór dnia"></div>' +
    '<div id="im-list" aria-live="polite"></div>' +
    '<input type="date" id="im-date" class="im-date" tabindex="-1" aria-hidden="true">';
  page.prepend(root);

  const strip = byId("im-strip");
  const list = byId("im-list");
  const liveBtn = byId("im-live");

  /* ---------- Pasek dni ---------- */
  function renderStrip() {
    const today = keyOf(new Date());
    let html = "";
    for (let i = 0; i < STRIP_DAYS; i++) {
      const d = addDays(stripStart, i);
      const k = keyOf(d);
      html +=
        '<button type="button" role="tab" class="im-day' + (k === today ? " is-today" : "") +
        '" data-key="' + k + '" aria-selected="false"><b>' + d.getDate() + "</b><span>" + DAY_NAMES[d.getDay()] + "</span></button>";
    }
    strip.innerHTML = html;
    markSel();
  }
  function markSel() {
    const k = keyOf(selected);
    strip.querySelectorAll(".im-day").forEach((b) => {
      const on = b.dataset.key === k;
      b.classList.toggle("is-sel", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
  }
  function centerSel(smooth) {
    const b = strip.querySelector(".is-sel");
    if (!b || !strip.clientWidth) return;
    strip.scrollTo({ left: b.offsetLeft - (strip.clientWidth - b.offsetWidth) / 2, behavior: smooth ? "smooth" : "auto" });
  }
  function ensureInStrip() {
    const first = stripStart.getTime();
    const last = addDays(stripStart, STRIP_DAYS).getTime();
    if (selected.getTime() < first || selected.getTime() >= last) {
      stripStart = addDays(selected, -7);
      renderStrip();
    }
  }
  function setDate(d, smooth) {
    selected = noon(d);
    liveOnly = false;
    syncLive();
    ensureInStrip();
    markSel();
    centerSel(smooth);
    draw();
  }
  function syncLive() {
    liveBtn.setAttribute("aria-pressed", liveOnly ? "true" : "false");
    strip.classList.toggle("dim", liveOnly);
  }

  // Poziomy pasek działa jak natywny picker iOS: bezwładność + zatrzymanie na dniu.
  let stripSettleTimer = null;
  let stripWasDragged = false;
  let stripStartX = 0;
  strip.addEventListener("touchstart", (e) => {
    stripWasDragged = false;
    stripStartX = e.touches[0] ? e.touches[0].clientX : 0;
  }, { passive: true });
  strip.addEventListener("touchmove", (e) => {
    if (e.touches[0] && Math.abs(e.touches[0].clientX - stripStartX) > 7) stripWasDragged = true;
  }, { passive: true });

  function settleStripSelection() {
    stripSettleTimer = null;
    const days = Array.from(strip.querySelectorAll(".im-day"));
    if (!days.length || !strip.clientWidth) return;
    const center = strip.getBoundingClientRect().left + strip.clientWidth / 2;
    let nearest = days[0];
    let distance = Infinity;
    days.forEach((b) => {
      const r = b.getBoundingClientRect();
      const d = Math.abs((r.left + r.width / 2) - center);
      if (d < distance) { distance = d; nearest = b; }
    });
    if (nearest.dataset.key !== keyOf(selected)) {
      selected = noon(new Date(nearest.dataset.key + "T12:00:00"));
      liveOnly = false;
      syncLive();
      markSel();
      draw();
    }
  }
  // Na iOS oddajemy fizykę przewijania przeglądarce. Datę zatwierdzamy
  // dopiero po zakończeniu bezwładności i animacji snap — nie w trakcie flingu.
  function scheduleStripSettle() {
    if ("onscrollend" in strip) return;
    if (stripSettleTimer) clearTimeout(stripSettleTimer);
    stripSettleTimer = setTimeout(settleStripSelection, 260);
  }
  strip.addEventListener("scroll", scheduleStripSettle, { passive: true });
  if ("onscrollend" in strip) {
    strip.addEventListener("scrollend", settleStripSelection, { passive: true });
  }

  strip.addEventListener("click", (e) => {
    if (stripWasDragged) {
      e.preventDefault();
      e.stopPropagation();
      stripWasDragged = false;
      return;
    }
    const b = e.target.closest(".im-day");
    if (b) setDate(new Date(b.dataset.key + "T12:00:00"), true);
  });
  liveBtn.addEventListener("click", () => {
    liveOnly = !liveOnly;
    syncLive();
    draw();
  });
  byId("im-cal").addEventListener("click", () => {
    const p = byId("im-date");
    p.value = keyOf(selected);
    if (p.showPicker) { try { p.showPicker(); return; } catch (err) { /* spróbuj click */ } }
    p.click();
  });
  byId("im-date").addEventListener("change", (e) => {
    if (e.target.value) setDate(new Date(e.target.value + "T12:00:00"), true);
  });
  list.addEventListener("click", (e) => {
    const a = e.target.closest("[data-act]");
    if (!a) return;
    if (a.dataset.act === "retry") load(true);
    if (a.dataset.act === "clear-league") { onlyLeague = null; draw(); }
  });

  /* ---------- Dane ---------- */
  function snapshot() {
    if (typeof tauronCache === "undefined") return;
    LEAGUES.forEach((L) => { if (tauronCache[L.key] && !tauronCache[L.key].error) store[L.key] = tauronCache[L.key]; });
  }
  function load(force, silent) {
    if (!silent) { loading = true; draw(); }
    return Promise.all(
      LEAGUES.map((L) => loadTauronData(!!force, L.key).then((d) => ({ key: L.key, d })))
    )
      .then((rs) => {
        errors = [];
        rs.forEach((r) => { if (r.d && !r.d.error) store[r.key] = r.d; else errors.push(r.key); });
      })
      .catch(() => { errors = LEAGUES.map((L) => L.key); })
      .then(() => { loading = false; draw(); });
  }

  /* ---------- Rysowanie listy ---------- */
  function card(m, L) {
    const live = isMatchLive(m);
    const fin = m.status === "finished";
    const scored = live || fin;
    const hs = Number(m.home_sets), as = Number(m.away_sets);
    const hWin = fin && hs > as, aWin = fin && as > hs;
    const label = m.group || m.competition || L.name;

    let right;
    if (live) right = '<span class="im-live">NA ŻYWO</span>';
    else if (fin) right = "<span>Zakończony · " + esc(fmtDate(matchDate(m))) + "</span>";
    else right = "<span>" + esc(fmtDate(matchDate(m))) + "</span>";

    const row = (name, pts, win, lose) =>
      '<div class="im-row"><span class="im-logo">' + logo(name) + '</span><span class="im-name' + (win ? " win" : "") + '">' + esc(name) + "</span>" +
      (scored ? '<b class="im-pts' + (lose ? " lose" : "") + '">' + esc(pts == null ? "–" : pts) + "</b>" : "") +
      "</div>";

    return (
      '<article class="im-card">' +
        '<div class="im-meta"><span>' + esc(label) + "</span>" + right + "</div>" +
        '<div class="im-body' + (scored ? " has-score" : "") + '">' +
          row(m.home, m.home_sets, hWin, aWin) +
          '<div class="im-sep"></div>' +
          row(m.away, m.away_sets, aWin, hWin) +
          (scored ? "" : '<div class="im-time">' + esc(m.time || "–:–") + "</div>") +
        "</div>" +
        (m.current_points ? '<div class="im-foot live">Aktualny set: ' + esc(m.current_points) + "</div>" : "") +
        (m.set_scores && m.set_scores.length ? '<div class="im-foot">Sety: ' + m.set_scores.map(esc).join(" · ") + "</div>" : "") +
      "</article>"
    );
  }

  function draw() {
    snapshot();
    const have = LEAGUES.filter((L) => store[L.key]);
    let html = "";

    if (!have.length) {
      if (loading) {
        html = '<div class="im-skel"></div><div class="im-skel"></div>';
      } else {
        html =
          '<div class="im-state"><b>Brak danych</b><p>Nie udało się pobrać meczów. Sprawdź połączenie i spróbuj ponownie.</p>' +
          '<button type="button" class="im-btn" data-act="retry">Spróbuj ponownie</button></div>';
      }
      push(html);
      liveBtn.classList.remove("has-live");
      return;
    }

    // czy gdziekolwiek trwa mecz (kropka na przycisku pulsuje)
    liveBtn.classList.toggle("has-live", have.some((L) => uniqueMatches(store[L.key].matches).some(isMatchLive)));

    const key = keyOf(selected);
    const groups = [];
    have.filter((L) => !onlyLeague || L.key === onlyLeague).forEach((L) => {
      let ms = uniqueMatches(store[L.key].matches);
      ms = liveOnly ? ms.filter(isMatchLive) : ms.filter((m) => dateKeyFromFeed(m.date) === key);
      ms.sort((a, b) => (a.time || "99:99").localeCompare(b.time || "99:99"));
      if (ms.length) groups.push({ L, ms });
    });

    if (onlyLeague) {
      const L = LEAGUES.find((x) => x.key === onlyLeague);
      html += '<div class="im-chip"><span>' + esc(L ? L.name : onlyLeague) + '</span><button type="button" data-act="clear-league" aria-label="Pokaż wszystkie ligi">✕</button></div>';
    }

    if (groups.length) {
      html += groups.map((g) =>
        '<section class="im-group"><h2 class="im-league"><span class="im-flag" aria-hidden="true">' + g.L.flag + "</span>" + esc(g.L.name) + "</h2>" +
        g.ms.map((m) => card(m, g.L)).join("") + "</section>"
      ).join("");
    } else {
      html += liveOnly
        ? '<div class="im-state"><b>Brak meczów na żywo</b><p>Gdy tylko jakiś mecz się zacznie, pojawi się tutaj.</p></div>'
        : '<div class="im-state"><b>Brak meczów tego dnia</b><p>Wybierz inny dzień na pasku u góry.</p></div>';
    }

    const upd = have.map((L) => store[L.key].updated_at).filter(Boolean).sort().pop();
    let note = upd ? "Dane oficjalne · aktualizacja: " + new Date(upd).toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" }) : "";
    if (errors.length) {
      const names = errors.map((k) => (LEAGUES.find((L) => L.key === k) || {}).name || k).join(", ");
      note += (note ? " · " : "") + "Nie udało się pobrać: " + names;
    }
    if (note) html += '<p class="im-note">' + esc(note) + "</p>";

    push(html);
  }
  function push(html) {
    if (html === lastHtml) return; // bez migania, gdy nic się nie zmieniło
    list.innerHTML = html;
    lastHtml = html;
  }

  /* ---------- Przełączanie: nowy widok <-> stary widok ---------- */
  const meta = document.querySelector('meta[name="theme-color"]');
  const metaOrig = meta ? meta.getAttribute("content") : null;
  function enterNew() {
    page.classList.add("ios-on");
    document.body.classList.add("ios-matches");
    if (meta) meta.setAttribute("content", "#fafafb");
  }
  function leaveNew() {
    page.classList.remove("ios-on");
    document.body.classList.remove("ios-matches");
    if (meta && metaOrig) meta.setAttribute("content", metaOrig);
  }
  function showNew() {
    enterNew();
    ensureInStrip();
    markSel();
    requestAnimationFrame(() => centerSel(false));
    snapshot();
    if (Object.keys(store).length) { draw(); load(true, true); } else { load(false); }
  }

  /* Przechwytujemy 3 funkcje z app.js (oryginały dalej działają) */
  const origGo = window.go;
  window.go = function (target) {
    if (target === "matches") {
      const oc = byId("official-content");
      if (oc) delete oc.dataset.currentOfficialView; // zawsze zaczynamy od terminarza
      onlyLeague = null;
    }
    inGo = true;
    try { origGo.apply(this, arguments); } finally { inGo = false; }
    if (target === "matches") showNew(); else leaveNew();
  };

  const origView = window.renderOfficialView;
  window.renderOfficialView = function (view, league) {
    if (view === "matches") {
      enterNew();
      if (!inGo) { // np. Rozgrywki → konkretna liga → „Terminarz”
        if (league && LEAGUES.some((L) => L.key === league)) onlyLeague = league;
        draw();
      }
      return;
    }
    // Wyniki / Tabela / Drużyny: pokazujemy stary widok, tak jak dotąd
    leaveNew();
    return origView.apply(this, arguments);
  };

  const origHome = window.renderHomeToday;
  window.renderHomeToday = function () {
    try { if (typeof origHome === "function") origHome.apply(this, arguments); } catch (err) { console.warn(err); }
    if (page.classList.contains("active") && page.classList.contains("ios-on")) draw(); // odświeżanie co 15 s z app.js
  };

  /* ---------- Dolna nawigacja: ikony + przycisk szukania ---------- */
  document.querySelectorAll(".nav[data-go]").forEach((b) => {
    const i = b.querySelector("i");
    const ico = ICONS[b.dataset.go];
    if (i && ico) i.innerHTML = svg(ico, 26);
  });
  const sb = document.createElement("button");
  sb.type = "button";
  sb.className = "im-search";
  sb.setAttribute("aria-label", "Szukaj");
  sb.innerHTML = svg(ICONS.search, 28);
  sb.addEventListener("click", () => {
    const open = byId("search-open");
    if (open) open.click();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  document.body.appendChild(sb);

  /* ---------- Start ---------- */
  renderStrip();
  if (page.classList.contains("active")) showNew();
})();