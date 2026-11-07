/* React Bits GlassSurface — David Haz (MIT + Commons Clause).
 * Original: https://github.com/DavidHDev/react-bits
 * License: ./LICENSE.md
 *
 * Only the static material is used by BottomNav. The legacy canvas/WebGL,
 * SVG displacement and resize observers are intentionally not bundled.
 */
import './GlassSurface.css';

export function StaticGlassSurface({ className = '' }) {
  return <div className={'glass-surface glass-surface--static ' + className} />;
}
