import { Rive, RuntimeLoader, Layout, Fit, Alignment } from '@rive-app/canvas';
import wasmUrl from '@rive-app/canvas/rive.wasm?url';

// Self-host WASM alongside the app, including under GitHub Pages' base path.
RuntimeLoader.setWasmUrl(wasmUrl);
RuntimeLoader.getInstance(() => {}, () => {});

export function createImpact(canvas, onReady, onDone) {
  const animation = new Rive({
    canvas,
    src: import.meta.env.BASE_URL + 'motion/impact.riv',
    artboard: 'Impact',
    stateMachine: 'Impact',
    autoplay: true,
    layout: new Layout({ fit: Fit.Fill, alignment: Alignment.Center }),
    onLoad: () => { animation.resizeDrawingSurfaceToCanvas(); onReady(); },
    onStop: onDone,
    onLoadError: onDone,
  });
  return animation;
}
