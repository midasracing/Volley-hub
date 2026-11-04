# Match and league motion

`impact/scene.rml` is the editable Rive source for the blood-red, three-panel
one-shot sweep. There are no scripts, fonts or external assets in the file.
`public/motion/impact.riv` is its 607-byte runtime export.

With Rive CLI 1.8.0:

```sh
rive motion/impact --verify
rive inspect motion/impact --summary
rive motion/impact --once
cp motion/impact/build/impact.riv public/motion/impact.riv
```

The runtime and WASM are bundled and served from the application's own base URL.
The runtime warms during idle time when motion is enabled. Each canvas plays once
and is disposed; delayed loads are skipped rather than flashing after an interaction.
The real heading and scores remain DOM text. Score rolling and title masking use
CSS so arbitrary live values stay selectable, accessible and visible if Rive fails.
Reduced-motion preferences disable the effects. No entrance plays on an initial
score load or on unchanged polling data; retained hidden panels do not animate.

## Startup entrance

`entrance/scene.rml` exports the 501-byte `public/motion/entrance.riv` background:
two broad red planes, without scripts or external assets. Build and inspect it
with the same commands above, replacing `impact` with `entrance`.

The unchanged logo SVG enters at the center, then travels to the measured bounds
of the real header logo. The header copy remains transparent during that flight
and is restored on landing, skipping, navigation or interruption. There is no
line, progress bar or caption. A short backdrop fade reveals the current page and
on-screen cards. Rive is optional and its canvas is capped to CSS pixel resolution;
the logo handoff also works offline. Only transforms and opacity are animated.
The entrance respects reduced motion and never replays on ordinary navigation.

## Calendar and set results

`ScheduleMotion.jsx` keeps date selection immediate, briefly leaves the old cards
on screen for their exit, then commits the latest requested day's results. Rapid
requests cancel earlier timers. Live feed polling never restarts this motion.
Set cells enter in sequence and leave in reverse order within the existing grid
expansion. These use DOM animations for arbitrary result counts and remain
interruptible; reduced motion removes the delay and stagger.

The date strip keeps its range stable during nearby selections. A single red
indicator slides between the retained day nodes while native smooth scrolling
centers the selected date. Resize callbacks do not interrupt selection scrolling;
the range extends near its edges after the scroll settles.
