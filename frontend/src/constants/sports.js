export const SPORT_META = {
  football: { name: 'Футбол', icon: '⚽' },
  basketball: { name: 'Баскетбол', icon: '🏀' },
  tennis: { name: 'Теніс', icon: '🎾' },
  hockey: { name: 'Хокей', icon: '🏒' },
  volleyball: { name: 'Волейбол', icon: '🏐' },
  esports: { name: 'Кіберспорт', icon: '🎮' },
};

const aliases = {
  'футбол': 'football',
  football: 'football',
  'баскетбол': 'basketball',
  basketball: 'basketball',
  'теніс': 'tennis',
  tennis: 'tennis',
  'хокей': 'hockey',
  hockey: 'hockey',
  'волейбол': 'volleyball',
  volleyball: 'volleyball',
  'кіберспорт': 'esports',
  esports: 'esports',
};

export function resolveSportMeta(sport) {
  if (!sport) return SPORT_META.football;
  const key = aliases[String(sport).toLowerCase()] || 'football';
  return SPORT_META[key] || SPORT_META.football;
}
