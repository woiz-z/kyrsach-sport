import { resolveSportMeta } from '../constants/sports';

export default function SportBadge({ sportName, icon, className = '' }) {
  const meta = resolveSportMeta(sportName);
  const resolvedIcon = icon || meta.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold shrink-0 ${className}`}
      style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)', color: '#93C5FD' }}
    >
      <span>{resolvedIcon}</span>
      <span>{sportName || meta.name}</span>
    </span>
  );
}

