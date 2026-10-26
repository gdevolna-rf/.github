/**
 * Pure rules of the assistant forms (AIX-01…03): validation that mirrors the server serializers
 * (backend/apps/search/serializers.py) and the URL parameters that make a result shareable.
 * The server re-validates everything; these checks only save a round trip.
 */
import {
  ASSISTANT_LEVELS,
  ASSISTANT_WAVES,
  type AssistantLevel,
  type AssistantWave,
  type BoardSizeInput,
  type RecommendInput,
} from "@/lib/api/search";

export const WEIGHT_MIN = 25;
export const WEIGHT_MAX = 200;

export interface BoardValues {
  weight: string;
  level: AssistantLevel | "";
  wave: AssistantWave | "";
}

export interface RecommendValues {
  region: string;
  level: AssistantLevel | "";
  date: string;
}

export type Errors<K extends string> = Partial<Record<K | "_form", string>>;

const isLevel = (v: unknown): v is AssistantLevel => ASSISTANT_LEVELS.some((l) => l.value === v);
const isWave = (v: unknown): v is AssistantWave => ASSISTANT_WAVES.some((w) => w.value === v);

/** "72,5" → 72.5; empty/invalid → NaN */
export function parseWeight(raw: string): number {
  const cleaned = raw.trim().replace(",", ".").replace(/\s/g, "");
  if (!cleaned) return Number.NaN;
  return /^\d+(\.\d+)?$/.test(cleaned) ? Number(cleaned) : Number.NaN;
}

export function validateBoard(values: BoardValues): { data: BoardSizeInput | null; errors: Errors<"weight_kg" | "level" | "wave"> } {
  const errors: Errors<"weight_kg" | "level" | "wave"> = {};
  const weight = parseWeight(values.weight);
  if (!values.weight.trim()) errors.weight_kg = "Укажите вес.";
  else if (!Number.isFinite(weight)) errors.weight_kg = "Вес — число в килограммах, например 72,5.";
  else if (weight < WEIGHT_MIN || weight > WEIGHT_MAX) errors.weight_kg = `Вес от ${WEIGHT_MIN} до ${WEIGHT_MAX} кг.`;
  if (!isLevel(values.level)) errors.level = "Выберите уровень катания.";
  if (!isWave(values.wave)) errors.wave = "Выберите волну.";
  if (Object.keys(errors).length || !isLevel(values.level) || !isWave(values.wave)) return { data: null, errors };
  return { data: { weight_kg: Math.round(weight * 10) / 10, level: values.level, wave: values.wave }, errors };
}

/** YYYY-MM-DD of a Date in the browser's local zone. */
export function localIsoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function dateBounds(today = new Date()): { min: string; max: string } {
  const max = new Date(today);
  max.setDate(max.getDate() + 365);
  return { min: localIsoDate(today), max: localIsoDate(max) };
}

export function validateRecommend(
  values: RecommendValues,
  today = new Date(),
): { data: RecommendInput | null; errors: Errors<"region" | "level" | "date"> } {
  const errors: Errors<"region" | "level" | "date"> = {};
  if (!values.region) errors.region = "Выберите регион.";
  if (!isLevel(values.level)) errors.level = "Выберите уровень катания.";
  if (values.date) {
    const { min, max } = dateBounds(today);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(values.date)) errors.date = "Дата в формате ДД.ММ.ГГГГ.";
    else if (values.date < min || values.date > max) errors.date = "Выберите дату в пределах ближайшего года.";
  }
  if (Object.keys(errors).length || !isLevel(values.level)) return { data: null, errors };
  return { data: { region: values.region, level: values.level, ...(values.date ? { date: values.date } : {}) }, errors };
}

/* ---------------- URL state (shareable results) ---------------- */

export const BOARD_PARAMS = { weight: "weight", level: "board_level", wave: "wave" } as const;
export const RECOMMEND_PARAMS = { region: "region", level: "level", date: "date" } as const;

type Params = Record<string, string | string[] | undefined>;
const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";

export function boardFromParams(params: Params): BoardValues {
  const level = first(params[BOARD_PARAMS.level]);
  const wave = first(params[BOARD_PARAMS.wave]);
  return {
    weight: first(params[BOARD_PARAMS.weight]).slice(0, 6),
    level: isLevel(level) ? level : "",
    wave: isWave(wave) ? wave : "",
  };
}

export function recommendFromParams(params: Params): RecommendValues {
  const level = first(params[RECOMMEND_PARAMS.level]);
  const date = first(params[RECOMMEND_PARAMS.date]);
  return {
    region: first(params[RECOMMEND_PARAMS.region]).slice(0, 60),
    level: isLevel(level) ? level : "",
    date: /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : "",
  };
}

/** Merge `patch` into the current query string (empty values are removed). */
export function mergeQuery(search: string, patch: Record<string, string | null | undefined>): string {
  const params = new URLSearchParams(search);
  for (const [key, value] of Object.entries(patch)) {
    if (value) params.set(key, value);
    else params.delete(key);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

/** Replace the URL without a navigation (Next keeps useSearchParams in sync with history.replaceState). */
export function replaceQuery(patch: Record<string, string | null | undefined>): void {
  if (typeof window === "undefined") return;
  const next = `${window.location.pathname}${mergeQuery(window.location.search, patch)}${window.location.hash}`;
  window.history.replaceState(window.history.state, "", next);
}

/** "70.1" → "70,1" */
export function formatLiters(value: string | number): string {
  const n = Number(value);
  return Number.isFinite(n) ? new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(n) : String(value);
}
