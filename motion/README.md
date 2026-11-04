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

`entrance/scene.rml` exports the 307-byte `public/motion/entrance.riv` red curtain.
Build and inspect it with the same commands above, replacing `impact` with
`entrance`. The full-screen app entrance uses the unchanged logo asset, without
a caption below the line. Its logo reveal and card stagger match the approved
preview. Rive is prepared during the logo reveal and played at 1.02 seconds;
a matching CSS curtain takes over when the runtime is unavailable or late.
The entrance always finishes independently of feed, font and Rive requests.
It can be skipped, respects reduced motion, and is not replayed by navigation.

## Calendar and set results

`ScheduleMotion.jsx` keeps date selection immediate, briefly leaves the old cards
on screen for their exit, then commits the latest requested day's results. Rapid
requests cancel earlier timers. Live feed polling never restarts this motion.
Set cells enter in sequence and leave in reverse order within the existing grid
expansion. These use DOM animations for arbitrary result counts and remain
interruptible; reduced motion removes the delay and stagger.
