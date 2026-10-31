import { useEffect, useState } from 'react';

// One lazily loaded WebGL component, shared by the floating menu and search.
export default function useFluidGlass() {
  const [Glass, setGlass] = useState(null);
  useEffect(() => {
    const off = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ||
      window.matchMedia?.('(prefers-reduced-transparency: reduce)').matches;
    if (!window.WebGL2RenderingContext || off) return undefined;
    let alive = true;
    import('../FluidGlass.jsx').then(module => {
      if (alive) setGlass(() => module.default);
    }).catch(() => { /* Keep the readable solid fallback if shader compilation fails. */ });
    return () => { alive = false; };
  }, []);
  return Glass;
}
