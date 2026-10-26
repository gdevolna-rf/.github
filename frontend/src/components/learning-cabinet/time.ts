/**
 * Time helpers for schedules (MET-08, «время по месту»): sessions are shown and entered in the IANA zone of
 * the spot / school region (the API returns `timezone` per session), never in the browser zone.
 * Calendar days are plain "YYYY-MM-DD" strings with UTC arithmetic, so the device zone never shifts them.
 */
import { DEFAULT_TIME_ZONE, formatDate, formatTime, formatUtcOffset, isoDateInZone } from "@/lib/format";

/** Offset of `timeZone` from UTC at the instant `utcMs`, in minutes (Kamchatka → 720). */
export function tzOffsetMinutes(utcMs: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(utcMs));
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value ?? 0);
  const asUtc = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour") % 24, get("minute"), get("second"));
  return Math.round((asUtc - utcMs) / 60000);
}

/** Wall-clock date + time in `timeZone` → ISO instant (UTC, "…Z") for the API. */
export function zonedToUtcIso(date: string, time: string, timeZone: string): string {
  const [y, m, d] = date.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  const guess = Date.UTC(y, (m || 1) - 1, d || 1, hh || 0, mm || 0);
  const first = tzOffsetMinutes(guess, timeZone);
  let utc = guess - first * 60000;
  const second = tzOffsetMinutes(utc, timeZone);
  if (second !== first) utc = guess - second * 60000;
  return new Date(utc).toISOString();
}

/** ISO instant → { date: "YYYY-MM-DD", time: "HH:MM" } in `timeZone` (form defaults). */
export function zonedParts(iso: string, timeZone: string): { date: string; time: string } {
  return { date: isoDateInZone(iso, timeZone), time: formatTime(iso, timeZone) };
}

const DAY_MS = 86_400_000;

function parseDay(date: string): number {
  const [y, m, d] = date.split("-").map(Number);
  return Date.UTC(y, (m || 1) - 1, d || 1);
}

function printDay(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

export function addDays(date: string, n: number): string {
  return printDay(parseDay(date) + n * DAY_MS);
}

/** Monday of the week that contains `date`. */
export function startOfWeek(date: string): string {
  const weekday = (new Date(parseDay(date)).getUTCDay() + 6) % 7; // Mon=0 … Sun=6
  return addDays(date, -weekday);
}

export function daysBetween(from: string, to: string): number {
  return Math.round((parseDay(to) - parseDay(from)) / DAY_MS);
}

export function dayRange(from: string, count: number): string[] {
  return Array.from({ length: count }, (_, i) => addDays(from, i));
}

/** Today in `timeZone`. */
export function todayIn(timeZone: string = DEFAULT_TIME_ZONE, now: Date = new Date()): string {
  return isoDateInZone(now, timeZone);
}

/** Pure calendar date → Russian text (no zone shift): long «22 октября 2026 г.», weekday «четверг, 22 октября»… */
export function formatDay(date: string, style: "long" | "dayMonth" | "weekday" | "medium" = "dayMonth"): string {
  return formatDate(new Date(parseDay(date) + 12 * 3_600_000), { timeZone: "UTC", style });
}

const WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

export function weekdayShort(date: string): string {
  return WEEKDAYS_SHORT[(new Date(parseDay(date)).getUTCDay() + 6) % 7];
}

export function dayOfMonth(date: string): number {
  return new Date(parseDay(date)).getUTCDate();
}

/** «21–27 октября 2026» / «28 октября – 3 ноября 2026». */
export function formatDayRange(from: string, to: string): string {
  const a = new Date(parseDay(from));
  const b = new Date(parseDay(to));
  const year = b.getUTCFullYear();
  if (a.getUTCMonth() === b.getUTCMonth() && a.getUTCFullYear() === b.getUTCFullYear()) {
    return `${a.getUTCDate()}–${formatDay(to, "dayMonth")} ${year}`;
  }
  const left = a.getUTCFullYear() === year ? formatDay(from, "dayMonth") : formatDay(from, "long");
  return `${left} – ${formatDay(to, "dayMonth")} ${year}`;
}

/** Short Russian names of the zones used in Russia (fallback: the IANA id). */
export const TZ_LABELS: Record<string, string> = {
  "Europe/Kaliningrad": "Калининград",
  "Europe/Moscow": "Москва",
  "Europe/Simferopol": "Крым",
  "Europe/Samara": "Самара",
  "Asia/Yekaterinburg": "Екатеринбург",
  "Asia/Omsk": "Омск",
  "Asia/Novosibirsk": "Новосибирск",
  "Asia/Krasnoyarsk": "Красноярск",
  "Asia/Irkutsk": "Иркутск",
  "Asia/Yakutsk": "Якутск",
  "Asia/Vladivostok": "Владивосток",
  "Asia/Sakhalin": "Сахалин",
  "Asia/Magadan": "Магадан",
  "Asia/Kamchatka": "Камчатка",
};

/** «Камчатка · UTC+12» — shown next to every session time. */
export function tzLabel(timeZone: string | null | undefined, at: string | Date = new Date()): string {
  const tz = timeZone || DEFAULT_TIME_ZONE;
  let offset = "";
  try {
    offset = formatUtcOffset(tz, at);
  } catch {
    offset = "";
  }
  const name = TZ_LABELS[tz] ?? tz;
  return offset ? `${name} · ${offset}` : name;
}

/** «10:00–11:30» in the session's own zone. */
export function timeRange(startsAt: string, endsAt: string, timeZone: string): string {
  return `${formatTime(startsAt, timeZone)}–${formatTime(endsAt, timeZone)}`;
}

/** Minutes between two ISO instants. */
export function durationMinutes(startsAt: string, endsAt: string): number {
  return Math.max(0, Math.round((new Date(endsAt).getTime() - new Date(startsAt).getTime()) / 60000));
}

/** Is a valid IANA zone (Intl throws on unknown ones). */
export function isTimeZone(value: string | null | undefined): value is string {
  if (!value) return false;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: value });
    return true;
  } catch {
    return false;
  }
}
