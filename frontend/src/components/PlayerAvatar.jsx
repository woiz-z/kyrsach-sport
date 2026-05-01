import { useState } from 'react';

const PALETTES = [
  { bg: '#1e3a8a', mid: '#3b82f6', skin: '#f5cba7', hair: '#1a1a2e', shirt: '#059669' },
  { bg: '#134e4a', mid: '#0d9488', skin: '#f0c5a0', hair: '#2c3e50', shirt: '#d97706' },
  { bg: '#4c1d95', mid: '#7c3aed', skin: '#f3d5b5', hair: '#374151', shirt: '#dc2626' },
  { bg: '#7c2d12', mid: '#ea580c', skin: '#fde8c8', hair: '#111827', shirt: '#0891b2' },
  { bg: '#14532d', mid: '#16a34a', skin: '#fde5c2', hair: '#3730a3', shirt: '#e11d48' },
];

function nameHash(name) {
  let h = 0;
  for (const c of (name || '')) h = (Math.imul(h, 31) + c.charCodeAt(0)) | 0;
  return Math.abs(h);
}

function AvatarSvg({ name }) {
  const h = nameHash(name);
  const p = PALETTES[h % PALETTES.length];
  const gid = `av${h}`;
  return (
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
      <defs>
        <linearGradient id={gid} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={p.bg} />
          <stop offset="100%" stopColor={p.mid} />
        </linearGradient>
      </defs>
      <rect width="100" height="100" fill={`url(#${gid})`} />
      <path d="M5 100 Q50 65 95 100 Z" fill={p.shirt} opacity="0.95" />
      <circle cx="50" cy="37" r="25" fill={p.hair} />
      <circle cx="50" cy="39" r="22" fill={p.skin} />
      <circle cx="41" cy="37" r="3.8" fill="#111827" />
      <circle cx="42.2" cy="35.8" r="1.2" fill="#fff" opacity="0.6" />
      <circle cx="59" cy="37" r="3.8" fill="#111827" />
      <circle cx="60.2" cy="35.8" r="1.2" fill="#fff" opacity="0.6" />
      <path d="M41 48 Q50 56 59 48" fill="none" stroke="#7f1d1d" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export default function PlayerAvatar({
  name,
  photoUrl,
  playerId,
  sizeClass = 'w-10 h-10',
  textClass = 'text-sm',
  className = '',
}) {
  const [failed, setFailed] = useState(false);

  // If we have a playerId, use the backend proxy which tries ESPN → Wikidata → SVG
  const src = playerId ? `/api/avatars/photo/${playerId}` : photoUrl;

  return (
    <div className={`${sizeClass} rounded-full overflow-hidden flex-shrink-0 ${className}`}>
      {src && !failed ? (
        <img
          src={src}
          alt={name}
          className="w-full h-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <AvatarSvg name={name} />
      )}
    </div>
  );
}
