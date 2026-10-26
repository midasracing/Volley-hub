/* React integration: official React Bits FluidGlass powers the active nav item and selected calendar date. */
import React, { useEffect, useState } from "https://esm.sh/react@19.1.0";
import { createRoot } from "https://esm.sh/react-dom@19.1.0/client";

const REACT_URL = "https://esm.sh/react@19.1.0";
const $ = (selector, root = document) => root.querySelector(selector);
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

  useEffect(() => {
    const root = $(".vh-react-bottom");
    if (!root) return;
    const update = () => {
      const selected = $(".vh-react-nav-items .nav.active", root);
      if (!selected) return;
      const rr = root.getBoundingClientRect();
      const sr = selected.getBoundingClientRect();
      if (rr.width && rr.height) {
        setPosition([
          Math.min(.98, Math.max(.02, (sr.left + sr.width / 2 - rr.left) / rr.width)),
          Math.min(.98, Math.max(.02, (sr.top + sr.height / 2 - rr.top) / rr.height))
        ]);
      }
    };
    const observer = new MutationObserver(() => {
      const next = getActive();
      setActive(current => current === next ? current : next);
      requestAnimationFrame(update);
    });
    observer.observe(root, { subtree: true, attributes: true, attributeFilter: ["class"] });
    const resize = new ResizeObserver(update);
    resize.observe(root);
    window.addEventListener("resize", update, { passive: true });
    requestAnimationFrame(update);
    return () => {
      observer.disconnect();
      resize.disconnect();
      window.removeEventListener("resize", update);
    };
  }, []);

  return h(FluidGlass, {
    className: "vh-fluid-nav-glass",
    style: { width: "100%", height: "100%" },
    text: "",
    shape: "pill",
    shapes: ["pill"],
    size: 33,
    position,
    interaction: "static",
    morphOnClick: false,
    idle: false,
    spin: 0,
    wobble: 0.08,
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
          requestAnimationFrame(() => {
            const root = $(".vh-react-bottom");
            const selected = $(".vh-react-nav-items .nav.active", root);
            if (!root || !selected) return;
            const rr = root.getBoundingClientRect(), sr = selected.getBoundingClientRect();
            setPosition([(sr.left + sr.width / 2 - rr.left) / rr.width, (sr.top + sr.height / 2 - rr.top) / rr.height]);
          });
        }
      }))
    )
  });
}

function CalendarGlass({ FluidGlass }) {
  const [position, setPosition] = useState([0.5, 0.5]);

  useEffect(() => {
    const wrap = $("#ios-matches .im-strip-wrap");
    if (!wrap) return;
    const update = () => {
      const selected = $(".im-strip button.is-sel", wrap) || $(".im-strip button[aria-selected='true']", wrap);
      if (!selected) return;
      const wr = wrap.getBoundingClientRect(), sr = selected.getBoundingClientRect();
      if (wr.width && wr.height) {
        setPosition([
          Math.min(.98, Math.max(.02, (sr.left + sr.width / 2 - wr.left) / wr.width)),
          Math.min(.98, Math.max(.02, (sr.top + sr.height / 2 - wr.top) / wr.height))
        ]);
      }
    };
    const observer = new MutationObserver(update);
    observer.observe(wrap, { subtree: true, childList: true, attributes: true, attributeFilter: ["class", "aria-selected"] });
    const resize = new ResizeObserver(update);
    resize.observe(wrap);
    window.addEventListener("resize", update, { passive: true });
    requestAnimationFrame(update);
    return () => {
      observer.disconnect();
      resize.disconnect();
      window.removeEventListener("resize", update);
    };
  }, []);

  return h(FluidGlass, {
    className: "vh-calendar-fluid",
    style: { width: "100%", height: "100%" },
    text: "",
    shape: "cube",
    shapes: ["cube"],
    size: 34,
    position,
    interaction: "static",
    morphOnClick: false,
    idle: false,
    spin: 0,
    wobble: 0,
    refraction: 1.1,
    dispersion: 0.18,
    reflection: 1,
    tint: 0.1,
    shadow: 0.24,
    color: "#ffffff"
  });
}

async function start() {
  try {
    const FluidGlass = await loadFluidGlass();
    const oldNav = $(".bottom");
    if (oldNav && !oldNav.classList.contains("vh-react-bottom")) {
      const root = document.createElement("nav");
      root.className = "bottom vh-react-bottom";
      root.setAttribute("aria-label", "Główna nawigacja");
      oldNav.replaceWith(root);
      createRoot(root).render(h(BottomNavigation, { FluidGlass }));
    }
    const installCalendar = () => {
      const wrap = $("#ios-matches .im-strip-wrap");
      if (!wrap || $("#vh-calendar-glass-root", wrap)) return;
      const root = document.createElement("div");
      root.id = "vh-calendar-glass-root";
      root.setAttribute("aria-hidden", "true");
      wrap.insertBefore(root, wrap.firstChild);
      createRoot(root).render(h(CalendarGlass, { FluidGlass }));
    };
    installCalendar();
    const page = $("#matches") || document.body;
    const pageObserver = new MutationObserver(installCalendar);
    pageObserver.observe(page, { childList: true, subtree: true });
    window.__vhReactFluidGlass = { React, FluidGlass };
  } catch (error) {
    console.error("Volley Hub React / Fluid Glass:", error);
    document.documentElement.classList.add("react-fluid-glass-failed");
  }
}
start();
