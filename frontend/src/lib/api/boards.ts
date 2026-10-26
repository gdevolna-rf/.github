/**
 * boards: public catalogue of board models and shaper workshops (SHP-07…11, BRD-02/03/08/10).
 * Shapes: backend/apps/boards/serializers.py (BoardCardSerializer, BoardDetailSerializer, ShaperCardSerializer,
 * ShaperDetailSerializer). Money and sizes are decimal strings; `*_display` are ready-made strings from the server.
 * Server Components fetch these with `serverFetch` (SSR + ISR); the analytics view beacon is browser-only.
 */
import { api, type Query } from "./client";
import type { Decimal, IsoDateTime, Media, PublicAccount, UUID } from "./types";

export interface BoardsRegion {
  id: number;
  slug: string;
  name: string;
}

export interface BoardTypeRef {
  id: number;
  code: string;
  name: string;
  silhouette: string;
}

export interface BoardType extends BoardTypeRef {
  sku_code: string;
  sort_order: number;
  is_custom: boolean;
}

export interface BoardMaterial {
  id: number;
  name: string;
  is_custom: boolean;
}

export type Availability = "in_stock" | "made_to_order" | "out_of_stock";

export interface VariantShort {
  id: UUID;
  sku: string;
  length_in: Decimal;
  width_in: Decimal;
  thickness_in: Decimal | null;
  volume_l: Decimal | null;
  length_display: string;
  width_display: string;
  thickness_display: string | null;
  dimensions_display: string;
  volume_display: string | null;
  fin_system: string;
  fin_system_label: string;
  price: Decimal | null;
  currency: string;
  availability: Availability;
  availability_label: string;
}

export interface BoardMediaItem {
  id: number;
  position: number;
  is_cover: boolean;
  variant_id: UUID | null;
  media: Media;
}

export interface VariantPublic extends VariantShort {
  version: number;
  material: BoardMaterial | null;
  construction: string;
  fin_setup: string;
  made_to_order_days: number | null;
  items_available_for_sale: number;
  photos: BoardMediaItem[];
}

/** Compact model tile (carousel in a shaper card, shaper profile). */
export interface BoardTile {
  id: UUID;
  name: string;
  slug: string;
  board_type: BoardTypeRef;
  cover: Media | null;
  photos_count: number;
  has_video: boolean;
  price_from: Decimal | null;
  currency: string;
  length_min_in: Decimal | null;
  length_max_in: Decimal | null;
  length_range_display: string | null;
  volume_min_l: Decimal | null;
  volume_max_l: Decimal | null;
  volume_range_display: string | null;
  availability: Availability;
  availability_label: string;
  variants_count: number;
  primary_variant: VariantShort | null;
  public_url: string;
}

export interface ShaperMini {
  id: UUID;
  slug: string;
  name: string;
  logo: Media | null;
  region: BoardsRegion | null;
  city: string;
  does_repair: boolean;
  rating_avg: Decimal;
  rating_count: number;
  public_url: string;
}

export interface ShaperDetailMini extends ShaperMini {
  short_description: string;
  specialization: string;
  lead_time: string;
  services: string[];
}

/** «Все доски» card. `is_own` is computed for the requesting session (always false in SSR). */
export interface BoardCard extends BoardTile {
  shaper: ShaperMini;
  is_own: boolean;
  published_at: IsoDateTime | null;
}

export interface BoardDetail extends Omit<BoardCard, "shaper"> {
  shaper: ShaperDetailMini;
  description: string;
  tags: string[];
  photos: BoardMediaItem[];
  video: Media | null;
  variants: VariantPublic[];
  updated_at: IsoDateTime;
}

/** «По шейперам» card (SHP-08/09) with up to 8 models. */
export interface ShaperCard {
  id: UUID;
  slug: string;
  name: string;
  logo: Media | null;
  region: BoardsRegion | null;
  city: string;
  short_description: string;
  owner: PublicAccount | null;
  specialization: string;
  services: string[];
  lead_time: string;
  does_repair: boolean;
  repair_note: string;
  experience_since: number | null;
  experience_years: number | null;
  promo_video: Media | null;
  rating_avg: Decimal;
  rating_count: number;
  models_count: number;
  models: BoardTile[];
  is_own: boolean;
  public_url: string;
}

export interface ShaperDetail extends ShaperCard {
  description: string;
  cover: Media | null;
  gallery: Media[];
  address: string;
  website: string;
  social_links: Record<string, string>;
  board_types: BoardType[];
  materials: BoardMaterial[];
  published_at: IsoDateTime | null;
}

/* ---------------- catalogue filters (URL ⇄ API query) ---------------- */

export type CatalogTab = "boards" | "shapers";

/** URL keys of the «Все доски» filters — the same names as the API (`GET boards?…`). */
export const BOARD_FILTER_KEYS = [
  "q",
  "type",
  "region",
  "shaper",
  "length_min",
  "length_max",
  "volume_min",
  "volume_max",
  "price_max",
  "availability",
  "material",
  "repair",
  "ordering",
] as const;

/** URL keys of the «По шейперам» filters (`GET shapers?…`). */
export const SHAPER_FILTER_KEYS = ["q", "type", "region", "repair", "ordering"] as const;

export type BoardFilterKey = (typeof BOARD_FILTER_KEYS)[number];
export type ShaperFilterKey = (typeof SHAPER_FILTER_KEYS)[number];

export type SearchParamsRecord = Record<string, string | string[] | undefined>;

export function firstParam(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

export function catalogTab(params: SearchParamsRecord): CatalogTab {
  return firstParam(params.tab) === "shapers" ? "shapers" : "boards";
}

export function pageParam(params: SearchParamsRecord): number {
  const n = Number(firstParam(params.page));
  return Number.isInteger(n) && n > 1 ? n : 1;
}

/** Only known, non-empty filter values are forwarded to the API (garbage in the URL never reaches Django). */
export function pickFilters<K extends string>(params: SearchParamsRecord, keys: readonly K[]): Partial<Record<K, string>> {
  const out: Partial<Record<K, string>> = {};
  for (const key of keys) {
    const value = firstParam(params[key]).trim();
    if (value) out[key] = value.slice(0, 120);
  }
  return out;
}

export const CATALOG_PAGE_SIZE = 24;

export function boardsQuery(params: SearchParamsRecord): Query {
  return { ...pickFilters(params, BOARD_FILTER_KEYS), page: pageParam(params), page_size: CATALOG_PAGE_SIZE };
}

export function shapersQuery(params: SearchParamsRecord): Query {
  return { ...pickFilters(params, SHAPER_FILTER_KEYS), page: pageParam(params), page_size: 12 };
}

/* ---------------- presentation helpers ---------------- */

const SILHOUETTE_FILES: Record<string, string> = {
  longboard: "longboard",
  shortboard: "shortboard",
  funboard: "funboard",
  fish: "fish",
  gun: "gun",
  sup: "sup",
  custom: "custom",
  // types without an own drawing use the closest real outline (SHP-06)
  midlength: "funboard",
  egg: "funboard",
  hybrid: "shortboard",
  softtop: "longboard",
  minimal: "funboard",
};

/** Board-type silhouette (public/ui/boards/*.svg) — the picture of every model without a photo. */
export function silhouetteSrc(type: Pick<BoardTypeRef, "silhouette" | "code"> | null | undefined): string {
  const key = type?.silhouette || type?.code || "custom";
  return `/ui/boards/${SILHOUETTE_FILES[key] ?? "custom"}.svg`;
}

/** «Лонгборд · 9'2"» (type · length range) */
export function boardTypeLine(board: Pick<BoardTile, "board_type" | "length_range_display">): string {
  return [board.board_type?.name, board.length_range_display].filter(Boolean).join(" · ");
}

/** Region · city */
export function placeLine(region: BoardsRegion | null | undefined, city?: string | null): string {
  return [region?.name, city].filter(Boolean).join(" · ");
}

/** Prototype board-photo rendering: transparent silhouettes/renders are contained, real photos too. */
export function boardImage(board: Pick<BoardTile, "cover" | "board_type">, prefer: "thumb" | "full" = "thumb"): string {
  const media = board.cover;
  const url = media ? (prefer === "thumb" ? media.thumbnail_url || media.url : media.url || media.thumbnail_url) : null;
  return url || silhouetteSrc(board.board_type);
}

/* ---------------- analytics (qualified views, MET-08) ---------------- */

export type ViewSubjectType = "instructor" | "surfer" | "board_model" | "board_variant" | "spot" | "organization" | "inventory_item";

/** POST /analytics/views — the server deduplicates (bots, self-views, repeat viewer within 24 h). */
export function trackView(subjectType: ViewSubjectType, subjectId: string) {
  return api.post<{ counted: boolean }>("analytics/views", { subject_type: subjectType, subject_id: subjectId }, { retries: 0, timeoutMs: 8000 });
}
