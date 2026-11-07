import { useEffect, useState } from 'react';

export default function TeamLogo({ name, logo, className = '' }) {
  const [broken, setBroken] = useState(false);
  const initials = String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join('').toUpperCase();
  useEffect(() => setBroken(false), [logo, name]);
  return <span className={'vh-team-logo ' + className}>
    {logo && !broken ? <img src={logo} alt="" loading="lazy" onError={() => setBroken(true)} /> : <span className="team-mark" aria-hidden="true">{initials || '?'}</span>}
  </span>;
}
