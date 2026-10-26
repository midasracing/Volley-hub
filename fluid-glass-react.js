/* React integration for React Bits FluidGlass: one measured pill for the active nav tab and one for the selected date. */
import React, { useEffect, useState } from "https://esm.sh/react@19.1.0";
import { createRoot } from "https://esm.sh/react-dom@19.1.0/client";

const REACT_URL = "https://esm.sh/react@19.1.0";
const $ = (selector, root = document) => root.querySelector(selector);
const queryAll = (selector, root = document) => Array.from(root.querySelectorAll(selector));
const h = React.createElement;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (window.Babel) return resolve();
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error("Nie udało się załadować kompilatora JSX."));
    document.head.appendChild(script);
  });
}

async function loadFluidGlass() {
  await loadScript("https://unpkg.com/@babel/standalone@7.28.4/babel.min.js");
  const response = await fetch("./fluid-glass-component.jsx", { cache: "no-store" });
  if (!response.ok) throw new Error("Nie udało się pobrać komponentu Fluid Glass.");
  let source = await response.text();
  source = source
    .replace(/^'use client';\s*/m, "")
    .replace(/^import ['"]\.\/FluidGlass\.css['"];?\s*/m, "")
    .replace(/import \{ useEffect, useRef, useState \} from ['"]react['"];?/, "import React, { useEffect, useRef, useState } from '" + REACT_URL + "';");
  const compiled = window.Babel.transform(source, {
    presets: [["react", { runtime: "classic" }]],
    sourceType: "module",
    filename: "FluidGlass.jsx"
  }).code;
  const url = URL.createObjectURL(new Blob([compiled], { type: "text/javascript" }));
  try {
    return (await import(url)).default;
  } finally {
    URL.revokeObjectURL(url);
  }
}

const navItems = [
  { id: "home", label: "Główna", icon: '<path d="M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1z"/>' },
  { id: "matches", label: "Mecze", icon: '<path d="M4 6h16v14H4zM4 10h16M8 3v4M16 3v4"/>' },
  { id: "competitions", label: "Rozgrywki", icon: '<path d="M12 3l9 5-9 5-9-5zM3 13l9 5 9-5"/>' },
  { id: "favorites", label: "Ulubione", icon: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.9z"/>' }
];

function NavButton({ item, active, onNavigate }) {
  return h("button", {
    className: "nav" + (active ? " active" : ""),
    "data-go": item.id,
    "aria-label": item.label,
    "aria-current": active ? "page" : undefined,
    onClick: () => onNavigate(item.id)
  },
    h("i", { dangerouslySetInnerHTML: { __html: '<svg viewBox="0 0 24 24" aria-hidden="true">' + item.icon + "</svg>" } }),
    h("span", { className: "lbl" }, item.label)
  );
}

function BottomNavigation({ FluidGlass }) {
  const getActive = () => $(".bottom .nav.active")?.dataset.go || "home";
  const [active, setActive] = useState(getActive);
  const [position, setPosition] = useState([0.125, 0.5]);
  const [glassSize, setGlassSize] = useState(140);

  useEffect(() => {
    const root = $(".vh-react-bottom");
    if (!root) return;
    const update = () => {
      const selected = $(".vh-react-nav-items .nav.active", root);
      if (!selected) return;
      const rr = root.getBoundingClientRect();
      const sr = selected.getBoundingClientRect();
      if (!rr.width || !rr.height || !sr.width || !sr.height) return;
      const nextPosition = [
        Math.min(.999, Math.max(.001, (sr.left + sr.width / 2 - rr.left) / rr.width)),
        Math.min(.999, Math.max(.001, (sr.top + sr.height / 2 - rr.top) / rr.height))
      ];
      setPosition(prev => Math.abs(prev[0] - nextPosition[0]) < .002 && Math.abs(prev[1] - nextPosition[1]) < .002 ? prev : nextPosition);
      setGlassSize(prev => Math.abs(prev - sr.width) < .5 ? prev : sr.width);
    };
    const observer = new MutationObserver(() => {
      const next = getActive();
      setActive(current => current === next ? current : next);
      requestAnimationFrame(update);
    });
    observer.observe(root, { subtree: true, attributes: true, attributeFilter: ["class"] });
    const resize = new ResizeObserver(update);
    resize.observe(root);
    queryAll(".vh-react-nav-items .nav", root).forEach(item => resize.observe(item));
    root.addEventListener("transitionend", update);
    window.addEventListener("resize", update, { passive: true });
    requestAnimationFrame(update);
    return () => {
      observer.disconnect();
      resize.disconnect();
      root.removeEventListener("transitionend", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  return h(FluidGlass, {
    className: "vh-fluid-nav-glass",
    style: {
      width: "100%",
      height: "100%",
    },
    text: "",
    shape: "pill",
    shapes: ["pill"],
    size: glassSize,
    position,
    interaction: "static",
    morphOnClick: false,
    idle: false,
    spin: 0,
    wobble: 0.04,
    refraction: 1.15,
    dispersion: 0.2,
    reflection: 1.1,
    tint: 0.12,
    shadow: 0.28,
    color: "#ffffff",
    children: h("div", { className: "vh-react-nav-items" },
      ...navItems.map(item => h(NavButton, {
        key: item.id,
        item,
        active: item.id === active,
        onNavigate: id => {
          if (typeof window.go === "function") window.go(id);
          setActive(id);
          requestAnimationFrame(updatePositionAfterNavigation);
        }
      }))
    )
  });

  function updatePositionAfterNavigation() {
    const root = $(".vh-react-bottom");
    const selected = root && $(".vh-react-nav-items .nav.active", root);
    if (!root || !selected) return;
    const rr = root.getBoundingClientRect(), sr = selected.getBoundingClientRect();
    if (!rr.width || !rr.height || !sr.width || !sr.height) return;
    setPosition([(sr.left + sr.width / 2 - rr.left) / rr.width, (sr.top + sr.height / 2 - rr.top) / rr.height]);
    setGlassSize(sr.width);
  }
}

function CalendarGlass({ FluidGlass }) {
  return h(FluidGlass, {
    className: "vh-calendar-fluid",
    style: { width: "100%", height: "100%" },
    text: "",
    shape: "pill",
    shapes: ["pill"],
    size: 132,
    position: [0.5, 0.5],
    rotation: 90,
    interaction: "static",
    morphOnClick: false,
    idle: false,
    spin: 0,
    wobble: 0,
    refraction: 1.0,
    dispersion: 0.08,
    reflection: 0.72,
    tint: 0.08,
    shadow: 0.2,
    color: "#ffffff"
  });
}
async function start() {
  // Replace legacy navigation before downloading React/Babel, preventing its old active rectangle from flashing.
  let navRoot = $(".vh-react-bottom");
  const oldNav = $(".bottom");
  if (!navRoot && oldNav) {
    navRoot = document.createElement("nav");
    navRoot.className = "bottom vh-react-bottom";
    navRoot.setAttribute("aria-label", "Główna nawigacja");
    navRoot.innerHTML = '<div class="vh-react-nav-items">' + oldNav.innerHTML + "</div>";
    oldNav.replaceWith(navRoot);
  }
  try {
    const FluidGlass = await loadFluidGlass();
    if (navRoot) createRoot(navRoot).render(h(BottomNavigation, { FluidGlass }));
    const installCalendar = () => {
      const wrap = $("#ios-matches .im-strip-wrap");
      if (!wrap) return;
      const selected = $(".im-day.is-sel", wrap) || $(".im-day[aria-selected='true']", wrap);
      if (!selected) return;
      let root = $("#vh-calendar-glass-root", wrap);
      if (!root) {
        root = document.createElement("div");
        root.id = "vh-calendar-glass-root";
        root.setAttribute("aria-hidden", "true");
        createRoot(root).render(h(CalendarGlass, { FluidGlass }));
      }
      // Anchor the glass to the selected date itself instead of the scrolling strip viewport.
      if (root.parentElement !== selected) selected.appendChild(root);
    };
    installCalendar();
    const page = $("#matches") || document.body;
    const pageObserver = new MutationObserver(installCalendar);
    pageObserver.observe(page, { childList: true, subtree: true, attributes: true, attributeFilter: ["class", "aria-selected"] });
    window.__vhReactFluidGlass = { React, FluidGlass };
  } catch (error) {
    console.error("Volley Hub React / Fluid Glass:", error);
    document.documentElement.classList.add("react-fluid-glass-failed");
  }
}
start();
