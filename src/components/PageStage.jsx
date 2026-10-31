import './PageStage.css';

// One visible route, with prepared panels retained inside it. The main element
// and each panel keep their DOM identity when the active tab changes.
export default function PageStage({ page, direction, reducedMotion, children }) {
  return <div className={'vh-route-stage is-' + direction}>
    <main id="main-content" data-page={page}
      className={'vh-page' + (!reducedMotion ? ' vh-page-enter' : '')}>
      {children}
    </main>
  </div>;
}
