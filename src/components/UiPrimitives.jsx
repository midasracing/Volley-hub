import { ArrowRight, CalendarDays, RotateCw, WifiOff } from 'lucide-react';

export function SectionTitle({ eyebrow, title, action, onAction }) {
  return <div className="vh-section-heading">
    <div>{eyebrow && <span className="vh-eyebrow">{eyebrow}</span>}<h2>{title}</h2></div>
    {action && <button className="vh-text-action" type="button" onClick={onAction}>{action}<ArrowRight size={17} /></button>}
  </div>;
}

export function EmptyState({ icon: Icon = CalendarDays, title, message, action, onAction }) {
  return <div className="vh-empty" role="status">
    <div className="vh-empty-icon"><Icon size={25} strokeWidth={1.8} /></div>
    <h3>{title}</h3><p>{message}</p>
    {action && <button type="button" className="vh-button vh-button-soft" onClick={onAction}>{action}</button>}
  </div>;
}
export function FeedWarning({ errors, refresh }) {
  const count = Object.keys(errors).length;
  if (!count) return null;
  return <div className="vh-warning" role="alert">
    <WifiOff size={18} /><span>Nie udało się odświeżyć {count === 1 ? 'jednej ligi' : count + ' lig'}. Pokazujemy ostatnio dostępne dane, jeśli zostały wczytane.</span>
    <button type="button" aria-label="Spróbuj ponownie" onClick={refresh}><RotateCw size={17} /></button>
  </div>;
}
export function LoadingCards() {
  return <div aria-label="Ładowanie meczów" role="status"><div className="im-skel" /><div className="im-skel" /><div className="im-skel" /></div>;
}
export function PageHeader({ title, subtitle, actions }) {
  return <div className="vh-page-head im-top"><div className="vh-header-actions">{actions}</div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>;
}
export function IconButton({ Icon, label, onClick, active = false }) {
  return <button type="button" className={'im-round vh-icon-button ' + (active ? 'is-active' : '')} aria-label={label} title={label} onClick={onClick}><Icon size={21} strokeWidth={1.9} /></button>;
}
