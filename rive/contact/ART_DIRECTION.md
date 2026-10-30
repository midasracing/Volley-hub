# CONTACT / Brand identity — 2026-10-30

**Volley Hub is a sports information product, not an esports/crypto company.**

## Hero decision
The brand owns one typographic gesture: a split, open **o** with an off-axis contact point. It is the volleyball and the beginning of the rally. This gesture survives in monochrome, mobile size, favicon and motion. The descender of the **y** releases a precise horizontal court line under `hub` — not a random decorative underline.

## Type system
Inter Display Black Italic (SIL Open Font License) was used as a **starting point** for optical letterforms. The o, contact point, spacing, line geometry, palette and motion are bespoke modifications. We do not falsely claim the entire alphabet was hand-drawn or imply a completed trademark search.

## Motion / Rive
Native Rive 70-frame 60fps one-shot (1.17s), 234×48 transparent artboard. V is legible immediately; contact O travels a short physical arc; letters land in two controlled beats; the y-line travels under hub. No persistent effects, neon fog, particle cloud, spin or hover dependency. Touch replay only when motion is allowed.

## Production checks
- At 234×48 and 200×41, brand must read without animation.
- Check one-colour reproduction using `public/brand/volley-hub-mono.svg`.
- Rive and SVG use the same geometric master coordinates (except the Rive court line is a native animatable rectangle).
- Static SVG and Rive binaries must come from the same review commit.
- Reduce motion renders immediate non-interactive static image; test 320px viewport collisions and mobile tap.
- Review actual Rive frames 1, 12, 23, 39, 54 and 70 before approving.

## Why this is a brand, not an effect
The movement happens **inside the sign**. No generic rounded V badge, fake liquid chrome, endless RGB glitch, decorative particles or random stagger. The static typographic identity is the product. Motion has one job: explain why the O is distinct.

## References (ideas only, no copied mark)
- [Wolff Olins — Decathlon](https://www.wolffolins.com/work/decathlon): symbol, type and behavior form one system.
- [COLLINS — Muse Group](https://wearecollins.com/case-studies/musegroup/): motion logic derived from forms.
- [Rive CLI](https://github.com/rive-app/rive-docs/blob/main/cli/overview.mdx): native editable markup and runtime export.
- [save.design Rive](https://save.design/tech/rive) and [Awwwards](https://www.awwwards.com/websites/): design craft benchmark, not assets to clone.

## Review notes — motion refinement
The first ball path overlapped the V in frame 12, creating a visual error. The O now approaches from **above/right** and resolves into its designed position by frame 30, avoiding the V and the arriving Ls. The mark uses the standalone contact glyph as an SVG favicon, not a generic square V.

## Installable icon system
The standalone split-O symbol is the sole icon source. A light/dark adaptive SVG is used for browser tabs. A neutral midnight container is allowed **only for OS home-screen icon tiles**; it is not part of the wordmark. The same SVG is deterministically rasterized to 192 and 512px PNG for reliable Android/iOS PWA support. The current header itself stays unboxed.

## Verified browser and rendering proof
- GitHub Actions contact renders six actual native Rive frames (1 / 12 / 23 / 39 / 54 / 70).
- React Playwright checks mobile viewports at 320 and 390 CSS px, tests native Rive load, touch replay and reduced-motion fallback, and uploads actual header screenshots as an artifact.
- CI compares the native Rive resting frame to the static SVG at exactly 234×48. Channel-wise mean absolute color deviation must stay under 7/255, accounting for two different anti-aliasing engines. This guards against accidentally editing only one version of the logo.
- Design review still requires a real physical device session before a production merge.
