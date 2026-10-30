import React, { lazy, Suspense, useCallback, useEffect, useState } from 'react';

const TechText = lazy(() => import('./react-bits/TechText.jsx'));

const motionDisabled = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;

/**
 * Single brand signature: actual React Bits TechText, auto-animated once.
 * Solid HTML fallback is readable before lazy canvas/Google font has loaded.
 * The canvas never depends on hover or pointer events to begin animation.
 */
export default function BrandSignature() {
  const [reducedMotion, setReducedMotion] = useState(motionDisabled);
  const [canvasReady, setCanvasReady] = useState(false);
  const onCanvasReady = useCallback(() => setCanvasReady(true), []);

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!media) return undefined;
    const onChange = () => {
      setReducedMotion(media.matches);
      setCanvasReady(false);
    };
    media.addEventListener?.('change', onChange);
    return () => media.removeEventListener?.('change', onChange);
  }, []);

  return (
    <div
      className={'vh-brand-tech' + (canvasReady && !reducedMotion ? ' has-canvas' : '')}
      role="img"
      aria-label="VOLLEY HUB"
    >
      <span className="vh-brand-tech-fallback" aria-hidden="true">
        VOLLEY <span>HUB</span>
      </span>
      {!reducedMotion && (
        <Suspense fallback={null}>
          <TechText
            text="VOLLEY HUB"
            fontFamily="Barlow, sans-serif"
            fontSize={43}
            fontWeight={800}
            letterSpacing={-0.038}
            color="#F5F7FF"
            accentColor="#9EBFFF"
            align="left"
            intro="assemble"
            introDuration={1.55}
            reveal="letter"
            specks={9}
            dashLength={2.8}
            dashGap={2}
            strokeWidth={1.2}
            lineStyle="solid"
            selection={false}
            labels={false}
            guides={false}
            draggable={false}
            clickKick={false}
            sweep={false}
            bounce={0}
            onCanvasReady={onCanvasReady}
            className="vh-brand-tech-canvas"
          />
        </Suspense>
      )}
    </div>
  );
}
