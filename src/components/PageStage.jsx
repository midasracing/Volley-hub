import './PageStage.css';

// A single live route: rendering the full outgoing match list a second time
// caused expensive layout, WebKit blur repaints and mismatched screens.
// Only the new page animates; the navigation dock remains a separate portal.
export default function PageStage({ page, direction, reducedMotion, children }) {
  return <div className={'vh-route-stage is-' + direction}>
    <main id="main-content" key={page} data-page={page}
      className={'vh-page' + (!reducedMotion ? ' vh-page-enter' : '')}>
      {children}
    </main>
  </div>;
}
