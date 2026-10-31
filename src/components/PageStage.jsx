import './PageStage.css';

// Only screen content gets a subtle transition; menu is mounted outside this subtree.
export default function PageStage({ page, direction, reducedMotion, children }) {
  return <div className={'vh-route-stage is-' + direction}>
    <main id="main-content" key={page} className={'vh-page' + (!reducedMotion ? ' vh-page-enter' : '')}>
      {children}
    </main>
  </div>;
}
