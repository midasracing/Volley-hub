import { useEffect } from 'react';
import { useRive } from '@rive-app/react-canvas';

/**
 * Native vector Rive scene, authored in rive/volley-hub-signature/scene.rml.
 * No raster, fonts, remote CDN assets, JS animation loops, or runtime scripts.
 */
export default function RiveWordmark({ onReady }) {
  const { rive, RiveComponent } = useRive({
    src: import.meta.env.BASE_URL + 'brand/volley-hub.riv',
    stateMachines: 'Wordmark',
    autoplay: true,
    onLoad: () => onReady(true),
    onLoadError: () => onReady(false)
  });

  useEffect(() => {
    if (!rive) return;
    const sync = () => {
      if (document.visibilityState === 'hidden') rive.pause();
      else if (rive.isPlaying === false) rive.play();
    };
    document.addEventListener('visibilitychange', sync);
    if (document.visibilityState === 'hidden') rive.pause();
    return () => document.removeEventListener('visibilitychange', sync);
  }, [rive]);

  return <RiveComponent className="vh-rive-layer" aria-hidden="true" />;
}
