const TZ = 'Europe/Kyiv';

/**
 * Parse a backend timestamp string as UTC.
 * Backend returns strings like "2026-04-29T19:00:00" without timezone marker.
 * Without 'Z', browsers may interpret them as local time — this ensures UTC.
 */
export function parseAsUTC(str) {
  if (!str) return null;
  const s = String(str);
  if (s.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
  return new Date(s + 'Z');
}

/** Returns 'YYYY-MM-DD' for a Date object in Kyiv timezone */
export function ukrDateKey(d) {
  if (!d || isNaN(d.getTime())) return null;
  return d.toLocaleDateString('sv-SE', { timeZone: TZ });
}

/** Returns 'YYYY-MM-DD' in Kyiv timezone for today */
export function todayUkrKey() {
  return new Date().toLocaleDateString('sv-SE', { timeZone: TZ });
}

/** Format time as HH:MM in Kyiv timezone */
export function formatUkrTime(str) {
  const d = parseAsUTC(str);
  if (!d || isNaN(d.getTime())) return 'Час невідомий';
  return d.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit', timeZone: TZ });
}

/** Format date as DD.MM.YYYY in Kyiv timezone */
export function formatUkrDate(str) {
  const d = parseAsUTC(str);
  if (!d || isNaN(d.getTime())) return 'Невідома дата';
  return d.toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: TZ });
}

/** Format full date with weekday and month name in Kyiv timezone */
export function formatUkrDateFull(str) {
  const d = parseAsUTC(str);
  if (!d || isNaN(d.getTime())) return 'Невідома дата';
  return d.toLocaleDateString('uk-UA', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: TZ });
}

/** Format short date (day + short month) in Kyiv timezone */
export function formatUkrDateShort(str) {
  const d = parseAsUTC(str);
  if (!d || isNaN(d.getTime())) return '';
  return d.toLocaleDateString('uk-UA', { day: 'numeric', month: 'short', timeZone: TZ });
}

/** Format datetime (date + time) in Kyiv timezone */
export function formatUkrDateTime(str) {
  const d = parseAsUTC(str);
  if (!d || isNaN(d.getTime())) return '';
  return d.toLocaleString('uk-UA', { timeZone: TZ });
}
