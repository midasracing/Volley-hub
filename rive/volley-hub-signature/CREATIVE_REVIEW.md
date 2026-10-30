# Creative Review 02 — Volley Hub / SIDEOUT

## Research (30 October 2026)

The design goal is NOT to look like another AI-generated site. The goal is an ownable sports-product identity that works **before** motion begins, works at 24px, and makes the Match screen feel like it belongs to the same brand.

**Direct research and designers:**
- Paul Rand, [Logos, Flags and Escutcheons](https://www.paulrand.design/writing/articles/1991-logos-flags-and-escutcheons.html): a logo identifies; it must be durable, recognizable, reproducible at tiny size and in one color.
- Sagi Haviv, [The 3 Rules](https://thefutur.com/content/the-3-rules-of-good-logo-design): appropriateness, distinctiveness and simplicity. No amount of polish compensates for a forgettable identifier.
- Chermayeff, Geismar, Haviv, [PRINT magazine interview](https://www.printmag.com/branding-identity-design/marks-men-an-interview-with-ivan-chermayeff-tom-geismar-and-sagi-haviv-of-chermayeff-geisma/): the challenge is simple form + enough uniqueness to be remembered.
- Wolff Olins, [Decathlon identity case study](https://wolffolins.com/work/decathlon): symbol, wordmark, typography and motion all derive from the same premise; a coherent visual system, not independent effects.
- Wieden+Kennedy, [Formula 1 rebrand](https://www.wk.com/work/formula-1-rebrand/): research and sport-specific form lead the symbol, typography and behaviors together.
- Rob Clarke, [Brand New wordmark](https://robclarke.com/work/brandnew/): meticulous ligatures, kerning, optical rhythm and a different small-size version. High craft, no gratuitous effects.
- COLLINS, [Muse Group case](https://wearecollins.com/case-studies/musegroup/): motion notation becomes a coherent graphic vocabulary.
- [Google Material timing/easing](https://m1.material.io/motion/duration-easing.html): movement should communicate changes immediately and settle without creating waiting.
- [W3C WCAG 2.2.2](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide): avoid continuous auto-motion that distracts from the actual content.

**AI slop symptoms:** generic rounded tile + V, neon accents, indiscriminate blue gradients, excessive glass, every letter bouncing in a stagger with no physical logic, interchangeable esports/tech font. The previous preview had too many of these.

## Diagnosis of previous Rive prototype

1. A small rounded navy tile made the 'V' look like an ordinary app icon, rather than a bespoke logo.
2. Box-shaped O looked like another gaming typeface; a tiny volleyball metaphor was not readable.
3. Every glyph had the same scale/slide treatment, resulting in a generic 'template reveal'.
4. Animated dot/sweep looked like random decoration because it did not derive from the typography.
5. Spaced-out wordmark seemed balanced at 234px, but it lacked a clear silhouette and strong ink/empty-space rhythm.
6. The initial frames looked like broken dark typography, violating the premium brand impression.

**Verdict:** technically functional, not yet worthy of being called Awwwards-level. Do not merge on that basis.

## SIDEOUT — new direction in Rive

- Remove the boxed V entirely; **the signature is the wordmark**. At small scales an independent monogram should be developed separately, not mechanically shrunk from the lockup.
- Make the **O** the only expressive construction in the letterforms. Circular counter (the ball) amid engineered straight-sided type; this is a decision a spectator can remember.
- Entrances are **three coherent physical beats**, not nine random staggered letters. VOLLEY locks, O hits a short serve arc, HUB enters as one group.
- Single restraint: white text + ice blue HUB; one short pale impact line, not endless electricity.
- The resting state has no animation. The mark must work with the Rive engine disabled.
- All outlines authored directly in RML; no typeface or binary font assets required.

## Approval gates (must pass before merging PR #2)

[ ] Monochrome version reads at 24px and 32px; compact monogram is separately designed.
[ ] At 234×48 and 200×41, read 'VOLLEY HUB' without additional context.
[ ] The logo does not resemble an esports team, crypto brand, or generic AI startup.
[ ] Animated O is clearly purposeful rather than a random particle.
[ ] 0/10/20/35/52/64 frame visual proof. Look for jumps/collisions/spacing.
[ ] Contrast on near-black Matches background, and pure black and white.
[ ] Real iPhone Safari and Android Chrome playback, tap replay, tab hide/return.
[ ] Reduced-motion system mode displays immediate static type and never requests a Rive canvas.
[ ] Branding decision made for reusability in favicon, home-screen icon, loading state and match broadcast graphics.

## Brand name / product note

Volley Hub is an app for **fixtures, scores and people who care about volleyball**. The identity should be competitive and intelligent, not aggressive gamer sci-fi. Three contacts / one rally is the motion metaphor. This should inform future score-reveal transitions and not just the animated wordmark.

## Ownership and claims

References are for design thinking, not copying. No third-party logo shapes or images are used in the Rive source. The wordmark is a designed exploration, not a legally clearance-tested trademark. A separate trademark similarity search and domain/brand check are required before widespread launch.
