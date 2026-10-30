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
