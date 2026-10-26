/**
 * Pure helpers of the instructors catalogue (INS-09): URL params ⇄ filters ⇄ API query, slot grouping by day in the
 * slot's own time zone, and the instructor's account id (the detail endpoint does not return it directly).
 */
import type { InstructorDetail, LessonSession } from "@/lib/api/learning";
import { DEFAULT_TIME_ZONE, formatDate, isoDateInZone } from "@/lib/format";

export const FILTER_KEYS = [
  "region",
  "spot",
  "level",
  "board_type",
  "format",
  "price_max",
  "certificate",
  "date",
  "rating_min",
  "q",
  "ordering",
] as const;

export type FilterKey = (typeof FILTER_KEYS)[number];
export type InstructorFilters = Partial<Record<FilterKey, string>>;

/** Filters that live in the «Ещё фильтры» row (the first row is region / spot / board / level, as in the prototype). */
export const EXTRA_KEYS: FilterKey[] = ["format", "price_max", "certificate", "date", "rating_min", "q"];

export const PAGE_SIZE = 12;

export const ORDERING_OPTIONS = [
  { value: "", label: "По умолчанию" },
  { value: "rating", label: "По рейтингу" },
  { value: "reviews", label: "По отзывам" },
  { value: "price", label: "Сначала дешевле" },
  { value: "experience", label: "По опыту" },
  { value: "newest", label: "Сначала новые" },
];

export const CERTIFICATE_OPTIONS = [
  { value: "verified", label: "Проверен модератором" },
  { value: "uploaded", label: "Загружен или проверен" },
  { value: "none", label: "Без сертификата" },
];

export const RATING_OPTIONS = [
  { value: "4.5", label: "от 4,5 ★" },
  { value: "4", label: "от 4 ★" },
  { value: "3", label: "от 3 ★" },
];

type ParamsLike = URLSearchParams | Record<string, string | string[] | undefined>;

function read(params: ParamsLike, key: string): string | undefined {
  if (params instanceof URLSearchParams) return params.get(key) ?? undefined;
  const v = params[key];
  return Array.isArray(v) ? v[0] : v;
}

/** URL search params (server `searchParams` or URLSearchParams) → clean filters + page. */
export function parseFilters(params: ParamsLike): { filters: InstructorFilters; page: number } {
  const filters: InstructorFilters = {};
  for (const key of FILTER_KEYS) {
    const raw = read(params, key)?.trim();
    if (!raw) continue;
    if (key === "price_max" || key === "rating_min") {
      const n = Number(raw.replace(",", "."));
      if (!Number.isFinite(n) || n < 0) continue;
      filters[key] = String(n);
      continue;
    }
    if (key === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(raw)) continue;
    filters[key] = raw.slice(0, 120);
  }
  const page = Math.max(1, Math.floor(Number(read(params, "page")) || 1));
  return { filters, page };
}

/** Filters → canonical query string (stable order; empty values dropped; page only when > 1). */
export function filtersToSearch(filters: InstructorFilters, page = 1): string {
  const sp = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const v = filters[key];
    if (v !== undefined && v !== "") sp.set(key, v);
  }
  if (page > 1) sp.set("page", String(page));
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

/** Apply one change: any filter change resets the page to 1. */
export function withFilter(filters: InstructorFilters, key: FilterKey, value: string | undefined): InstructorFilters {
  const next = { ...filters };
  if (value === undefined || value === "") delete next[key];
  else next[key] = value;
  return next;
}

export function activeCount(filters: InstructorFilters, keys: readonly FilterKey[] = FILTER_KEYS): number {
  return keys.filter((k) => k !== "ordering" && filters[k]).length;
}

/** API query for GET /instructors. */
export function filtersToApiQuery(filters: InstructorFilters, page: number): Record<string, string | number> {
  const q: Record<string, string | number> = { page, page_size: PAGE_SIZE };
  for (const [k, v] of Object.entries(filters)) if (v) q[k] = v;
  return q;
}

/* ---------------- slots ---------------- */

export interface SlotDay {
  /** YYYY-MM-DD in the slot's zone */
  key: string;
  /** «пятница, 24 октября» */
  label: string;
  timeZone: string;
  slots: LessonSession[];
}

/** Upcoming free slots grouped by calendar day of each slot's own time zone, sorted by start. */
export function groupSlotsByDay(slots: readonly LessonSession[], fallbackTz = DEFAULT_TIME_ZONE): SlotDay[] {
  const sorted = [...slots].sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at));
  const days: SlotDay[] = [];
  for (const slot of sorted) {
    const tz = slot.timezone || fallbackTz;
    const key = `${isoDateInZone(slot.starts_at, tz)}|${tz}`;
    let day = days.find((d) => `${d.key}|${d.timeZone}` === key);
    if (!day) {
      day = { key: isoDateInZone(slot.starts_at, tz), label: formatDate(slot.starts_at, { timeZone: tz, style: "weekday" }), timeZone: tz, slots: [] };
      days.push(day);
    }
    day.slots.push(slot);
  }
  return days;
}

/** Instructor's account id: the detail endpoint omits it, but their own slots carry `instructor.id`. */
export function instructorAccountId(detail: Pick<InstructorDetail, "handle" | "upcoming_slots">): string | null {
  const own = detail.upcoming_slots.find((s) => s.instructor && s.instructor.handle === detail.handle);
  return own?.instructor?.id ?? null;
}

/** Years since `since` (surfing_since / teaching_since). */
export function yearsSince(since: number | null | undefined, now = new Date()): number | null {
  if (!since || since < 1950) return null;
  return Math.max(0, now.getFullYear() - since);
}
