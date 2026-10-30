# VOLLEY HUB / SIGNAL — motion design art direction

## Design brief, not an effect shopping list

Make the app feel like a sports broadcast product conceived by a distinctive design studio.
It must look like a brand even when the animation is paused.

**Visual references:**
- [Podium / San Rita](https://www.awwwards.com/sites/podium) — sport-specific identity, one recognizable hero gesture, intentional cropping; *use the idea of bespoke graphic language, not its shapes*.
- [Lando Norris](https://www.awwwards.com/sites/lando-norris) — disciplined racing energy and editorial typography; *translate intensity into brief movement, not into a cluttered dashboard*.
- [Jeton / Bürocratik](https://www.burocratik.com/work/jeton) — material character and motion are derived from the letterforms and the brand symbol, never randomly applied.
- [save.design Rive collection](https://save.design/tech/rive) — reference index for mobile-first motion systems and authored interaction.
- [Awwwards websites](https://www.awwwards.com/websites/) — the broad benchmark for visual craft, NOT permission to copy other studios.

The exact gallery pages may change; this file records design *principles* rather than asserting any one pixel-perfect reference.

## Signature concept: SERVE / IMPACT / SETTLE

A literal volleyball graphic would compete with nine tightly packed uppercase glyphs.
Instead, the letter O doubles as the **ball**: its outline travels upward from the monogram, arcs, takes shape and clicks into its permanent slot. The rest of the custom-drawn geometric wordmark arrives in controlled phases. A one-time kinetic line slices across the finished phrase and disappears. The logo then holds still indefinitely.

### Deliberate timing
- 0–100ms: the monogram powers on; the O begins as a small compressed form
- 100–380ms: serve motion; O arcs up, snaps into wordmark; remaining letters lock by small groups
- 380–715ms: HUB arrives after VOLLEY, not as chaotic random characters
- 715–1000ms: a single crisp streak and pinpoint impact
- 1000–1333ms: settle into a static signature, no ambient animation

The animated artboard is 234×48px — the *small size* is a deliberate constraint. The shape must read at the original pixel size on a phone. Not an overdecorated desktop animation shrunk down.

## Crafted type / palette
- All glyphs are **original paths** in RML, not a downloaded typeface, font effect, screenshot, or a big text preset.
- Stroke discipline follows ≈2.65 units with a few optical corrections.
- VOLLEY uses high-chroma neutral white, HUB is tinted ice-blue; electric cyan appears only for the motion.
- This is not a liquid-chrome shader and should never be marketed as one. The sharp geometry is the brand.

## Production contract
- Editable source: \`rive/volley-hub-signature/scene.rml\`.
- Compiled native Rive animation: \`public/brand/volley-hub.riv\`.
- One-shot animation from the native state machine \`Wordmark\`, no scripts or shader dependency.
- Lazy-loaded React Rive Canvas only where the wordmark appears.
- Static accessible text is always present. Reduced-motion preference disables the animation entirely.
- A tap replays the animation without a cursor. Hidden tabs pause it; returning to a tab must not restart an already finished animation.
- Re-run \`rive --verify\`, inspect snapshots at frames 1/35/52/80, mobile Playwright, and touch interactions.
- Keep source attribution inside our own inspiration notes. Do not redistribute Awwwards images/assets as part of our application.
