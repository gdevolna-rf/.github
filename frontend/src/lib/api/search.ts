/**
 * Global search (NAV-04) and the rule-based assistant (AIX-01…03).
 * Shapes: backend/apps/search/serializers.py (SearchResponseSerializer, BoardSize*, Recommend*).
 * The search page fetches on the server (serverFetch); the assistant forms post from the browser.
 */
import { api } from "./client";
import type { Decimal, IsoDate, IsoDateTime, Media, UUID } from "./types";

/* ---------------- search ---------------- */

export type SearchType = "spots" | "instructors" | "schools" | "shapers" | "boards" | "equipment" | "surfers";

/** Group order and fallback labels (the server sends `label` too). */
export const SEARCH_TYPES: Array<{ type: SearchType; label: string }> = [
  { type: "spots", label: "Споты" },
  { type: "instructors", label: "Инструкторы" },
  { type: "schools", label: "Сёрф-школы" },
  { type: "shapers", label: "Шейперы" },
  { type: "boards", label: "Доски" },
  { type: "equipment", label: "Оборудование" },
  { type: "surfers", label: "Участники GG Surfer" },
];

export const SEARCH_MIN_QUERY = 2;
export const SEARCH_MAX_QUERY = 100;
/** Results per group on the «all types» page and on a single-type page. */
export const SEARCH_LIMIT_ALL = 5;
export const SEARCH_LIMIT_ONE = 20;

export function isSearchType(value: unknown): value is SearchType {
  return typeof value === "string" && SEARCH_TYPES.some((t) => t.type === value);
}

export interface SearchResult {
  type: SearchType;
  id: string;
  title: string;
  subtitle: string;
  image: Media | null;
  /** Frontend route (ARCHITECTURE §9). */
  url: string;
}

export interface SearchGroup {
  type: SearchType;
  label: string;
  total: number;
  results: SearchResult[];
  /** Section catalogue with the same query, e.g. /spots?q=… */
  more_url: string;
}

export interface SearchResponse {
  query: string;
  groups: SearchGroup[];
}

/* ---------------- assistant ---------------- */

export type AssistantLevel = "beginner" | "intermediate" | "advanced" | "pro";
export type AssistantWave = "small" | "medium" | "big";

/** apps.search.services.assistant.LEVELS / WAVES */
export const ASSISTANT_LEVELS: Array<{ value: AssistantLevel; label: string }> = [
  { value: "beginner", label: "Новичок" },
  { value: "intermediate", label: "Средний" },
  { value: "advanced", label: "Продвинутый" },
  { value: "pro", label: "Профи" },
];

export const ASSISTANT_WAVES: Array<{ value: AssistantWave; label: string }> = [
  { value: "small", label: "Небольшая волна (до 1 м)" },
  { value: "medium", label: "Средняя волна (1–1,8 м)" },
  { value: "big", label: "Большая волна (от 1,8 м)" },
];

export interface VolumeRange {
  min: Decimal;
  max: Decimal;
}

export interface AssistantBoardType {
  code: string;
  name: string;
}

export interface MatchingBoard {
  variant_id: UUID;
  model_id: UUID;
  sku: string;
  title: string;
  subtitle: string;
  board_type: AssistantBoardType;
  length_in: Decimal;
  length_label: string;
  width_in: Decimal;
  thickness_in: Decimal | null;
  volume_l: Decimal;
  price: Decimal | null;
  currency: string;
  availability: string;
  availability_label: string;
  /** The board type is among the recommended ones. */
  type_match: boolean;
  image: Media | null;
  url: string;
  source: string;
}

export interface BoardSizeInput {
  weight_kg: number;
  level: AssistantLevel;
  wave: AssistantWave;
}

export interface BoardSizeResponse {
  input: { weight_kg: Decimal; level: AssistantLevel; wave: AssistantWave };
  volume_l: VolumeRange;
  formula: { guild_factor: VolumeRange; wave_factor: Decimal; rule_version: number };
  board_types: AssistantBoardType[];
  explanation: string;
  warnings: string[];
  matching_boards: MatchingBoard[];
  disclaimer: string;
}

export interface RecommendInput {
  region: string;
  level: AssistantLevel;
  date?: IsoDate | null;
}

export interface AssistantForecast {
  provider: string;
  issued_at: IsoDateTime;
  valid_from: IsoDateTime;
  valid_to: IsoDateTime;
  wave_height_m: string | null;
  wave_period_s: string | null;
  wave_direction: string;
  wind_speed_ms: string | null;
  wind_direction: string;
  water_temp_c: string | null;
  source: string;
}

interface RecommendedItem {
  id: UUID;
  title: string;
  subtitle: string;
  image: Media | null;
  url: string;
  /** «Каталог ГДеволна, данные обновлены ДД.ММ.ГГГГ» */
  source: string;
}

export interface RecommendedSpot extends RecommendedItem {
  type: "spot";
  slug: string;
  difficulty: string;
  difficulty_label: string;
  typical_conditions: string;
  season: string;
  season_match: boolean | null;
  hazards: string[];
  hazard_notes: string;
  seasonal_warning: string;
  rating_avg: Decimal;
  rating_count: number;
  forecast: AssistantForecast | null;
}

export interface RecommendedInstructor extends RecommendedItem {
  type: "instructor";
  handle: string;
  rating_avg: Decimal;
  rating_count: number;
  price_from: Decimal | null;
  currency: string;
  certificate_verified: boolean;
}

export interface RecommendedRental extends RecommendedItem {
  type: "rental";
  kind: string;
  kind_label: string;
  price_per_day: Decimal | null;
  price_per_hour: Decimal | null;
  currency: string;
  owner_name: string | null;
  free_on_date: boolean | null;
}

export interface RecommendResponse {
  region: { id: number | string; slug: string; name: string; timezone?: string };
  level: AssistantLevel;
  level_label: string;
  date: IsoDate;
  spots: RecommendedSpot[];
  instructors: RecommendedInstructor[];
  rentals: RecommendedRental[];
  notes: string[];
  disclaimer: string;
  rule_version: number;
  generated_at: IsoDateTime;
}

export const assistantApi = {
  boardSize: (body: BoardSizeInput) => api.post<BoardSizeResponse>("assistant/board-size", body),
  recommend: (body: RecommendInput) => api.post<RecommendResponse>("assistant/recommend", body),
};

export const searchKeys = {
  regions: ["search", "regions"] as const,
};
