/* React island for the Fluid Glass controls.
   React is loaded as an ES module so the existing static PWA can keep its current structure.
   The original app remains vanilla JS; this is the first React integration point. */
import React, { useEffect } from "https://esm.sh/react@19.1.0";
import { createRoot } from "https://esm.sh/react-dom@19.1.0/client";

const h = React.createElement;

function FluidGlassReactBridge() {
  useEffect(() => {
    // Keep the glass treatment attached to the live controls as the legacy UI re-renders.
    const sync = () => {
      document.querySelectorAll(".bottom .nav").forEach((item) => {
        item.toggleAttribute("data-react-glass-target", item.classList.contains("active"));
      });
      const selectedDay = document.querySelector("#ios-matches .im-strip button.selected");
      document.querySelectorAll("#ios-matches .im-strip button").forEach((item) => {
        item.toggleAttribute("data-react-glass-target", item === selectedDay);
      });
    };
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);
  return null;
}

const mount = document.createElement("div");
mount.id = "fluid-glass-react-root";
mount.hidden = true;
document.body.appendChild(mount);
createRoot(mount).render(h(FluidGlassReactBridge));
