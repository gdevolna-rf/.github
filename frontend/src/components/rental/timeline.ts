/**
 * Availability period and timeline math (RENT-03/04). Pure functions → unit-tested.
 * Periods are sent to the API as calendar dates (YYYY-MM-DD, `to` inclusive) — the server turns them into
 * [start of `from`, start of the day after `to`) in the project time zone and returns the exact moments,
 * which the timeline then uses as its 0…100 % scale.
 */
import { DEFAULT_TIME_ZONE, isoDateInZone } from "@/lib/format";

export type PeriodPreset = "today" | "3d" | "week" | "month" | "custom";

export const PERIOD_PRESETS: Array<{ value: Exclude<PeriodPreset, "custom">; label: string; days: number }> = [
  { value: "today", label: "Сегодня", days: 1 },
  { value: "3d", label: "3 дня", days: 3 },
  { value: "week", label: "Неделя", days: 7 },
  { value: "month", label: "Месяц", days: 30 },
];

/** "2026-10-21" + 2 → "2026-10-23" (pure calendar arithmetic, no time zone involved). */
export function addDays(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + days));
  return t.toISOString().slice(0, 10);
}

/** Inclusive date range for a preset, starting today in `timeZone`. */
export function presetRange(
  preset: Exclude<PeriodPreset, "custom">,
  now: Date = new Date(),
  timeZone = DEFAULT_TIME_ZONE,
): { from: string; to: string } {
  const days = PERIOD_PRESETS.find((p) => p.value === preset)?.days ?? 1;
  const from = isoDateInZone(now, timeZone);
  return { from, to: addDays(from, days - 1) };
}

/** Validation of a custom range (server limit: ≤ 366 days, `to` ≥ `from`). Returns a Russian message or null. */
export function rangeError(from: string, to: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(from) || !/^\d{4}-\d{2}-\d{2}$/.test(to)) return "Укажите обе даты периода.";
  if (to < from) return "Дата окончания не может быть раньше начала.";
  const days = (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000 + 1;
  if (days > 366) return "Период — не длиннее года.";
  return null;
}

export interface Interval {
  starts_at: string;
  ends_at: string;
}

export interface Segment<T extends Interval = Interval> {
  interval: T;
  /** left offset, % of the period */
  left: number;
  /** width, % of the period (≥ minWidth so a 1-hour booking in a month is still visible) */
  width: number;
  /** the booking started before / ends after the period */
  clippedStart: boolean;
  clippedEnd: boolean;
}

const round = (n: number) => Math.round(n * 100) / 100;

/**
 * Position booked intervals on a period bar. Intervals outside the period are dropped, overlapping edges are
 * clipped to 0…100 %. `minWidth` keeps very short bookings visible; the segment is shifted left if needed
 * so it never overflows the bar.
 */
export function timelineSegments<T extends Interval>(
  periodStart: string | Date,
  periodEnd: string | Date,
  intervals: T[],
  minWidth = 1.5,
): Segment<T>[] {
  const start = new Date(periodStart).getTime();
  const end = new Date(periodEnd).getTime();
  const span = end - start;
  if (!Number.isFinite(span) || span <= 0) return [];
  const out: Segment<T>[] = [];
  for (const interval of intervals) {
    const s = new Date(interval.starts_at).getTime();
    const e = new Date(interval.ends_at).getTime();
    if (!Number.isFinite(s) || !Number.isFinite(e) || e <= start || s >= end || e <= s) continue;
    const from = Math.max(s, start);
    const to = Math.min(e, end);
    let left = ((from - start) / span) * 100;
    let width = ((to - from) / span) * 100;
    if (width < minWidth) {
      width = minWidth;
      if (left + width > 100) left = 100 - width;
    }
    out.push({ interval, left: round(left), width: round(width), clippedStart: s < start, clippedEnd: e > end });
  }
  return out.sort((a, b) => a.left - b.left);
}

/** Share of the period that is booked (overlaps merged), 0…100. */
export function bookedShare(periodStart: string | Date, periodEnd: string | Date, intervals: Interval[]): number {
  const start = new Date(periodStart).getTime();
  const end = new Date(periodEnd).getTime();
  const span = end - start;
  if (!Number.isFinite(span) || span <= 0) return 0;
  const parts = intervals
    .map((i) => [Math.max(new Date(i.starts_at).getTime(), start), Math.min(new Date(i.ends_at).getTime(), end)] as const)
    .filter(([s, e]) => e > s)
    .sort((a, b) => a[0] - b[0]);
  let total = 0;
  let curS = -Infinity;
  let curE = -Infinity;
  for (const [s, e] of parts) {
    if (s > curE) {
      if (curE > curS) total += curE - curS;
      curS = s;
      curE = e;
    } else curE = Math.max(curE, e);
  }
  if (curE > curS) total += curE - curS;
  return Math.round((total / span) * 1000) / 10;
}
