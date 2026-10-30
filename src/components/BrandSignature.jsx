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

  const fallback = (
    <>
      <span className="vh-brand-static" aria-hidden="true">
        <img src={import.meta.env.BASE_URL + 'brand/volley-hub-static.svg'} width="234" height="48" alt="" />
      </span>
      <span className="vh-brand-sr">VOLLEY HUB</span>
    </>
  );

  if (reducedMotion) {
    return <span className="vh-brand-signature" role="img" aria-label="VOLLEY HUB">{fallback}</span>;
  }

  return (
    <button
      type="button"
      className={'vh-brand-signature' + (ready ? ' is-ready' : '')}
      onClick={replay}
      aria-label="Volley Hub — odtwórz animację logo"
      title="Dotknij, aby odtworzyć animację"
    >
      {fallback}
      <Suspense fallback={null}>
        <RiveWordmark key={take} onReady={onReady} />
      </Suspense>
    </button>
  );
}
