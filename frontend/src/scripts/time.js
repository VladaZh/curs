export const WEEKDAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'];
const pad = (n) => String(n).padStart(2, '0');
const LOCAL_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

const zoneParts = (date, timeZone) =>
  Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone,
      hourCycle: 'h23',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
      .formatToParts(date)
      .map((p) => [p.type, p.value]),
  );

const zoneOffsetMs = (date, timeZone) => {
  const p = zoneParts(date, timeZone);
  const asUtc = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
  return asUtc - Math.floor(date.getTime() / 1000) * 1000;
};

const parseLocal = (local) => {
  const m = LOCAL_RE.exec(local ?? '');
  if (!m) return null;
  const [y, mo, d, h, mi] = m.slice(1).map(Number);
  return { y, mo, d, h, mi };
};

const formatLocal = (date) =>
  `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}` +
  `T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;

export function zonedLocalToUtcIso(local, timeZone) {
  const p = parseLocal(local);
  if (!p) return null;
  const guess = Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi);
  let utc = guess - zoneOffsetMs(new Date(guess), timeZone);
  utc = guess - zoneOffsetMs(new Date(utc), timeZone);
  return new Date(utc).toISOString();
}

export function nowInZoneLocal(timeZone, now = new Date()) {
  const p = zoneParts(now, timeZone);
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

export function addMinutesLocal(local, minutes) {
  const p = parseLocal(local);
  return formatLocal(new Date(Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi + minutes)));
}

export function roundUpLocal(local, stepMinutes = 15) {
  const p = parseLocal(local);
  const rest = p.mi % stepMinutes;
  return rest === 0 ? local : addMinutesLocal(local, stepMinutes - rest);
}

export const formatInZone = (iso, timeZone) =>
  new Intl.DateTimeFormat('ru-RU', {
    timeZone,
    weekday: 'short',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso));

export const timeInZone = (iso, timeZone) =>
  new Intl.DateTimeFormat('ru-RU', { timeZone, hour: '2-digit', minute: '2-digit' }).format(new Date(iso));

export function weekdayOfLocal(local) {
  const p = parseLocal(local);
  return (new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay() + 6) % 7;
}

const toMinutes = (hhmm) => {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
};

export const shortTime = (hhmmss) => hhmmss.slice(0, 5);

export function checkOpeningHours(local, hours, slotMinutes) {
  if (!hours?.length) return { ok: true };
  const day = hours.find((h) => h.weekday === weekdayOfLocal(local));
  if (!day) return { ok: false, message: 'В этот день ресторан не работает' };

  const p = parseLocal(local);
  const start = p.h * 60 + p.mi;
  const opens = toMinutes(day.opens);
  const closes = toMinutes(day.closes);
  if (start < opens || start + slotMinutes > closes) {
    return {
      ok: false,
      message: `Бронь на ${slotMinutes} мин должна уместиться в часы работы: ${shortTime(day.opens)}–${shortTime(day.closes)}`,
    };
  }
  return { ok: true };
}