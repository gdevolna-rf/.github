/**
 * Formatting helpers (ru-RU). Dates are always rendered in an explicit IANA time zone — the spot's /
 * instructor's region (RegionRef.timezone) for schedules, Europe/Moscow by default — never the browser's
 * implicit zone (avoids the prototype's "today in UTC" bug).
 */

export const LOCALE = "ru-RU";
export const DEFAULT_TIME_ZONE = "Europe/Moscow";

type DateInput = Date | string | number;

export function toDate(value: DateInput): Date {
  return value instanceof Date ? value : new Date(value);
}

const cache = new Map<string, Intl.DateTimeFormat>();
function dtf(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = JSON.stringify(options);
  let f = cache.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat(LOCALE, options);
    cache.set(key, f);
  }
  return f;
}

/** Calendar date parts of `value` in `timeZone` (for "same day?" checks and calendars). */
export function datePartsInZone(value: DateInput, timeZone = DEFAULT_TIME_ZONE) {
  const parts = dtf({ timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(toDate(value));
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  return { year: get("year"), month: get("month"), day: get("day") };
}

/** "YYYY-MM-DD" of `value` in `timeZone`. */
export function isoDateInZone(value: DateInput, timeZone = DEFAULT_TIME_ZONE): string {
  const { year, month, day } = datePartsInZone(value, timeZone);
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export type DateStyle = "long" | "medium" | "short" | "numeric" | "dayMonth" | "weekday";

/**
 * - long:     21 октября 2026 г.
 * - medium:   21 окт. 2026 г.
 * - dayMonth: 21 октября
 * - weekday:  среда, 21 октября
 * - numeric:  21.10.2026
 */
export function formatDate(value: DateInput, opts: { timeZone?: string; style?: DateStyle } = {}): string {
  const timeZone = opts.timeZone ?? DEFAULT_TIME_ZONE;
  const d = toDate(value);
  if (Number.isNaN(d.getTime())) return "";
  switch (opts.style ?? "long") {
    case "medium":
      return dtf({ timeZone, day: "numeric", month: "short", year: "numeric" }).format(d);
    case "dayMonth":
      return dtf({ timeZone, day: "numeric", month: "long" }).format(d);
    case "weekday":
      return dtf({ timeZone, weekday: "long", day: "numeric", month: "long" }).format(d);
    case "numeric":
    case "short":
      return dtf({ timeZone, day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
    default:
      return dtf({ timeZone, day: "numeric", month: "long", year: "numeric" }).format(d);
  }
}

/** 09:00 */
export function formatTime(value: DateInput, timeZone = DEFAULT_TIME_ZONE): string {
  const d = toDate(value);
  if (Number.isNaN(d.getTime())) return "";
  return dtf({ timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(d);
}

/** 21 октября, 09:00 (year added when it differs from the current one) */
export function formatDateTime(value: DateInput, opts: { timeZone?: string; now?: Date } = {}): string {
  const timeZone = opts.timeZone ?? DEFAULT_TIME_ZONE;
  const d = toDate(value);
  if (Number.isNaN(d.getTime())) return "";
  const sameYear = datePartsInZone(d, timeZone).year === datePartsInZone(opts.now ?? new Date(), timeZone).year;
  const date = sameYear ? formatDate(d, { timeZone, style: "dayMonth" }) : formatDate(d, { timeZone, style: "long" });
  return `${date}, ${formatTime(d, timeZone)}`;
}

/** 21 октября, 09:00–11:00 · or · 21 октября, 09:00 — 22 октября, 18:00 */
export function formatDateRange(start: DateInput, end: DateInput, opts: { timeZone?: string; now?: Date } = {}): string {
  const timeZone = opts.timeZone ?? DEFAULT_TIME_ZONE;
  if (isoDateInZone(start, timeZone) === isoDateInZone(end, timeZone)) {
    return `${formatDateTime(start, opts)}–${formatTime(end, timeZone)}`;
  }
  return `${formatDateTime(start, opts)} — ${formatDateTime(end, opts)}`;
}

/** "UTC+12" for a zone at a given moment. */
export function formatUtcOffset(timeZone: string, at: DateInput = new Date()): string {
  const name = dtf({ timeZone, timeZoneName: "shortOffset" })
    .formatToParts(toDate(at))
    .find((p) => p.type === "timeZoneName")?.value;
  return (name || "GMT").replace("GMT", "UTC").replace(/^UTC$/, "UTC+0");
}

const rtf = typeof Intl !== "undefined" ? new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" }) : null;

/** только что · 5 минут назад · через 2 часа · вчера · завтра · 3 дня назад · then a plain date. */
export function formatRelative(value: DateInput, opts: { now?: Date; timeZone?: string } = {}): string {
  const now = opts.now ?? new Date();
  const d = toDate(value);
  if (Number.isNaN(d.getTime())) return "";
  const diffSec = Math.round((d.getTime() - now.getTime()) / 1000);
  const abs = Math.abs(diffSec);
  if (abs < 45) return "только что";
  if (!rtf) return formatDateTime(d, opts);
  if (abs < 45 * 60) return rtf.format(Math.round(diffSec / 60), "minute");
  if (abs < 20 * 3600) return rtf.format(Math.round(diffSec / 3600), "hour");
  const tz = opts.timeZone ?? DEFAULT_TIME_ZONE;
  const dayDiff = Math.round(
    (Date.parse(isoDateInZone(d, tz)) - Date.parse(isoDateInZone(now, tz))) / 86_400_000,
  );
  if (Math.abs(dayDiff) <= 6) return rtf.format(dayDiff, "day");
  return formatDate(d, { timeZone: tz, style: datePartsInZone(d, tz).year === datePartsInZone(now, tz).year ? "dayMonth" : "long" });
}

/* ---------------- numbers, plurals, money ---------------- */

/** Russian plural form: plural(5, ["отзыв", "отзыва", "отзывов"]) → "отзывов". */
export function plural(n: number, forms: readonly [one: string, few: string, many: string]): string {
  const abs = Math.abs(n);
  if (!Number.isInteger(abs)) return forms[1]; // 1,5 отзыва
  const mod10 = abs % 10;
  const mod100 = abs % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1];
  return forms[2];
}

/** "5 отзывов", "1 модель", "22 окна" */
export function pluralize(n: number, forms: readonly [string, string, string]): string {
  return `${formatNumber(n)} ${plural(n, forms)}`;
}

/** Common word forms — reuse instead of re-typing them in pages. */
export const WORDS = {
  review: ["отзыв", "отзыва", "отзывов"],
  model: ["модель", "модели", "моделей"],
  board: ["доска", "доски", "досок"],
  photo: ["фото", "фото", "фото"],
  spot: ["спот", "спота", "спотов"],
  instructor: ["инструктор", "инструктора", "инструкторов"],
  message: ["сообщение", "сообщения", "сообщений"],
  newMessage: ["новое сообщение", "новых сообщения", "новых сообщений"],
  inquiry: ["обращение", "обращения", "обращений"],
  booking: ["бронирование", "бронирования", "бронирований"],
  slot: ["окно", "окна", "окон"],
  seat: ["место", "места", "мест"],
  day: ["день", "дня", "дней"],
  year: ["год", "года", "лет"],
  hour: ["час", "часа", "часов"],
  minute: ["минута", "минуты", "минут"],
  student: ["ученик", "ученика", "учеников"],
  result: ["результат", "результата", "результатов"],
  offer: ["предложение", "предложения", "предложений"],
} as const satisfies Record<string, readonly [string, string, string]>;

export function formatNumber(n: number, maximumFractionDigits = 1): string {
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits }).format(n);
}

/**
 * Money: decimal strings from the API ("65000.00") + ISO currency → "65 000 ₽", "1 499,50 ₽", "120 $".
 * Returns "" for empty values so callers can decide what to show («Цена по договорённости»).
 */
export function formatMoney(amount: string | number | null | undefined, currency = "RUB"): string {
  if (amount === null || amount === undefined || amount === "") return "";
  const value = typeof amount === "number" ? amount : Number(amount);
  if (!Number.isFinite(value)) return "";
  const integer = Number.isInteger(value);
  try {
    return new Intl.NumberFormat(LOCALE, {
      style: "currency",
      currency,
      currencyDisplay: "narrowSymbol",
      minimumFractionDigits: integer ? 0 : 2,
      maximumFractionDigits: integer ? 0 : 2,
    }).format(value);
  } catch {
    return `${formatNumber(value, 2)} ${currency}`;
  }
}

/** «от 3 800 ₽» or «Цена по договорённости». */
export function formatPriceFrom(amount: string | number | null | undefined, currency = "RUB"): string {
  const money = formatMoney(amount, currency);
  return money ? `от ${money}` : "Цена по договорённости";
}

/** Rating "4,9" (one decimal, ru). */
export function formatRating(value: string | number | null | undefined): string {
  const n = Number(value ?? 0);
  return new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number.isFinite(n) ? n : 0);
}

/* ---------------- board dimensions (inches → feet/inches) ---------------- */

const FRACTIONS: Record<number, string> = { 1: "⅛", 2: "¼", 3: "⅜", 4: "½", 5: "⅝", 6: "¾", 7: "⅞" };

/** 20.5 → "20 ½″", 2.625 → "2 ⅝″", 19 → "19″" (rounded to 1/8″). */
export function formatInches(inches: number | string | null | undefined): string {
  const n = Number(inches);
  if (inches === null || inches === undefined || inches === "" || !Number.isFinite(n)) return "";
  let whole = Math.floor(n);
  let eighths = Math.round((n - whole) * 8);
  if (eighths === 8) {
    whole += 1;
    eighths = 0;
  }
  const frac = eighths ? FRACTIONS[eighths] : "";
  if (!whole) return `${frac || "0"}″`;
  return frac ? `${whole} ${frac}″` : `${whole}″`;
}

/** Board length 76 → "6′4″", 108 → "9′0″", 70.5 → "5′10 ½″". */
export function formatFeetInches(totalInches: number | string | null | undefined): string {
  const n = Number(totalInches);
  if (totalInches === null || totalInches === undefined || totalInches === "" || !Number.isFinite(n)) return "";
  const eighthsTotal = Math.round(n * 8);
  const feet = Math.floor(eighthsTotal / 96);
  const rest = (eighthsTotal - feet * 96) / 8;
  return `${feet}′${formatInches(rest) || "0″"}`;
}

/** "6′4″ × 20 ½″ × 2 ⅝″ · 35,2 л" — width/thickness/volume are optional. */
export function formatBoardDimensions(d: {
  length_in?: number | string | null;
  width_in?: number | string | null;
  thickness_in?: number | string | null;
  volume_l?: number | string | null;
}): string {
  const sizes = [formatFeetInches(d.length_in), formatInches(d.width_in), formatInches(d.thickness_in)].filter(Boolean);
  const volume = d.volume_l !== null && d.volume_l !== undefined && d.volume_l !== "" ? `${formatNumber(Number(d.volume_l))} л` : "";
  return [sizes.join(" × "), volume].filter(Boolean).join(" · ");
}

/* ---------------- misc ---------------- */

/** 90 → "1 ч 30 мин" */
export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return [h ? `${h} ч` : "", m ? `${m} мин` : ""].filter(Boolean).join(" ") || "0 мин";
}

/** 65 → "1:05" (video tiles) */
export function formatClock(seconds: number | null | undefined): string {
  if (!seconds || seconds < 0) return "0:00";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

/** "Алексей Морозов" → "АМ"; "surfer_123" → "S" */
export function initials(name: string | null | undefined): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
}

/** Trim long text at a word boundary (cards). Prefer CSS line-clamp for display; use this for meta/OG. */
export function truncate(text: string, max = 160): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), max - 20)).trimEnd()}…`;
}
