import { resolveSportMeta } from '../constants/sports';

export default function SportBadge({ sportName, icon, className = '' }) {
  const meta = resolveSportMeta(sportName);
  const resolvedIcon = icon || meta.icon;

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-700 ${className}`}>
      <span>{resolvedIcon}</span>
      <span>{sportName || meta.name}</span>
    </span>
  );
}
