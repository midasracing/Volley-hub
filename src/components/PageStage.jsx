import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import './PageStage.css';

const EXIT_DURATION = 320;

// The dock lives outside this stage, so only the actual page content moves.
// Keep the outgoing view for a short, non-interactive crossfade while the new
// view arrives. Rapid tab changes replace the previous exit immediately.
export default function PageStage({ page, direction, reducedMotion, children }) {
  const previousRef = useRef({ page, children });
  const timeoutRef = useRef(null);
  const [outgoing, setOutgoing] = useState(null);

  useLayoutEffect(() => {
    const previous = previousRef.current;
    if (previous.page !== page) {
      clearTimeout(timeoutRef.current);
      if (reducedMotion) {
        setOutgoing(null);
      } else {
        setOutgoing({ page: previous.page, children: previous.children, direction });
        timeoutRef.current = setTimeout(() => {
          timeoutRef.current = null;
          setOutgoing(null);
        }, EXIT_DURATION);
      }
    } else if (reducedMotion && outgoing) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
      setOutgoing(null);
    }
    previousRef.current = { page, children };
  }, [page, direction, children, reducedMotion, outgoing]);

  useEffect(() => () => {
    clearTimeout(timeoutRef.current);
  }, []);

  return <div className={'vh-route-stage is-' + direction}>
    {outgoing && !reducedMotion &&
      <div key={'exit-' + outgoing.page} className={'vh-page vh-page-exit is-' + outgoing.direction}
        inert aria-hidden="true">
        {outgoing.children}
      </div>}
    <main id="main-content" key={page} data-page={page}
      className={'vh-page' + (!reducedMotion ? ' vh-page-enter' : '')}>
      {children}
    </main>
  </div>;
}
