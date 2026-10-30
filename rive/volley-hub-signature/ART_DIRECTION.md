# VOLLEY HUB — SIGNAL / Rive motion identity

## Design intent

Original custom-drawn geometric display lettering, not a font effect. 9 uppercase glyphs have identical optical height, 2.65-unit stroke discipline, chamfered round counters and rigid horizontal terminals. Thin cyan is reserved for the monogram's left edge and the one-time impulse.

The animation is a **serve / impact / resolve** sequence:
1. Monogram anchors the eye; electric inner edge charges.
2. VOLLEY snaps in left-to-right with alternating directional tension (6–11 frame arrivals).
3. HUB lands as one measured group, not a 'random glitch'.
4. An electric signal crosses the finished wordmark and disappears.
5. The resting mark is completely still. Touch replays the intro.

This isn't a perpetually blinking logo. At 234×48, every pixel has work to do, especially on a phone.

## Source and export

- `scene.rml` is editable Rive Markup Language; no fonts, raster artwork, sound or scripts.
- `rive . --verify` compiles; `rive . --once` exports a script-free, unsigned `.riv`.
- Rive CLI 1.8.0 is used to verify and render snapshots.
- The signed runtime restriction concerns Rive scripts; this scene intentionally uses keyframed native shapes, no scripts.
- The GitHub Actions authoring job builds and compares frame captures; it may commit the checked binary asset to the feature branch.
- App implementation uses the Rive React Canvas runtime and shows semantic HTML wordmark as an accessible static fallback.

## Movement / constraints

- Artboard: 234×48 CSS pixels.
- Full 80 frames at 60fps ≈ 1.33s.
- Ambient idle: **zero** animation.
- Motion preference: show a static wordmark when `prefers-reduced-motion` is set.
- Browser visibility: pause while hidden.
- Branding: optimized for dark navy. New color variants require their own artboard and palette.
- This isn't the final product until visual review of actual screenshots at 0, 0.6 and 1.33 seconds, plus mobile browser playback.
