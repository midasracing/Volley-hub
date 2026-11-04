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
