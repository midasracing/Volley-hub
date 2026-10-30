import React, { lazy, Suspense, useCallback, useEffect, useState } from 'react';

const RiveWordmark = lazy(() => import('./RiveWordmark.jsx'));

function prefersReducedMotion() {
  return typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
}

/**
 * Meaningful static signature first, native Rive enhancement after loading.
 * Animation is never required to read the brand or navigate the app.
 */
export default function BrandSignature() {
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);
  const [ready, setReady] = useState(false);
  const [take, setTake] = useState(0);
  const onReady = useCallback(value => setReady(value), []);

  useEffect(() => {
    const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!preference) return;
    const update = () => { setReducedMotion(preference.matches); setReady(false); };
    preference.addEventListener?.('change', update);
    return () => preference.removeEventListener?.('change', update);
  }, []);

  const replay = () => {
    if (reducedMotion) return;
    setReady(false);
    setTake(value => value + 1);
  };

  return (
    <button
      type="button"
      className={'vh-brand-signature' + (ready && !reducedMotion ? ' is-ready' : '')}
      onClick={replay}
      aria-label={reducedMotion ? 'Volley Hub' : 'Volley Hub — odtwórz animację logo'}
      title={reducedMotion ? 'Volley Hub' : 'Dotknij, aby odtworzyć animację'}
    >
      <span className="vh-wordmark vh-brand-static" aria-hidden="true">
        <span className="vh-wordmark-icon">V</span>
        VOLLEY<span>HUB</span>
      </span>
      {!reducedMotion && (
        <Suspense fallback={null}>
          <RiveWordmark key={take} onReady={onReady} />
        </Suspense>
      )}
    </button>
  );
}
