/**
 * boards (shaper cabinet) + analytics (scope=shaper): the workshop, custom board types and materials, models,
 * variants (server-generated SKU, F10 versions), model media, bulk table (BRD-12) and dashboard metrics (MET-03).
 * Shapes mirror backend/apps/boards/serializers.py and apps/analytics/services/metrics.py.
 *
 * Query keys live here (domain-first) instead of the shared keys.ts so parallel page work does not collide:
 * invalidating ["shaper"] refreshes every shaper cabinet query.
 */
import { api, type Query } from "./client";
import type { Decimal, IsoDateTime, Media, Paginated, RegionRef, UUID } from "./types";

/* ---------------- query keys ---------------- */

export const shaperKeys = {
  all: ["shaper"] as const,
  workshop: (organization?: string | null) => ["shaper", "workshop", organization ?? "default"] as const,
  boardTypes: (workshopId: string) => ["shaper", "board-types", workshopId] as const,
  materials: (workshopId: string) => ["shaper", "materials", workshopId] as const,
  models: (workshopId: string, filter: Query = {}) => ["shaper", "models", workshopId, filter] as const,
  modelsAll: (workshopId: string) => ["shaper", "models", workshopId] as const,
  model: (modelId: string) => ["shaper", "model", modelId] as const,
  variants: (workshopId: string) => ["shaper", "variants", workshopId] as const,
  metrics: (organization: string | null | undefined, from?: string, to?: string) =>
    ["shaper", "metrics", organization ?? "all", from ?? "", to ?? ""] as const,
  /** first element "inquiries" so realtime `inquiry.updated` / `message.new` refresh the panel preview */
  inquiriesPreview: (organization?: string | null) => ["inquiries", "shaper-panel", organization ?? "all"] as const,
  regions: ["regions"] as const,
};

/* ---------------- reference data ---------------- */

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

export interface Material {
  id: number;
  name: string;
  is_custom: boolean;
}

export interface Region extends RegionRef {
  id: number;
  timezone?: string;
}

export interface PublishRequirement {
  code: string;
  label: string;
  ok: boolean;
}

/** Board silhouettes the server knows (apps.boards.services.types.SILHOUETTES). */
export const SILHOUETTES = [
  "shortboard",
  "fish",
  "funboard",
  "midlength",
  "longboard",
  "gun",
  "hybrid",
  "egg",
  "softtop",
  "sup",
  "custom",
] as const;

export const SILHOUETTE_LABELS: Record<string, string> = {
  shortboard: "Шортборд",
  fish: "Фиш",
  funboard: "Фанборд",
  midlength: "Мидлленг",
  longboard: "Лонгборд",
  gun: "Ган",
  hybrid: "Гибрид",
  egg: "Эгг",
  softtop: "Софттоп",
  sup: "SUP",
  custom: "Другая форма",
};

/** Fin systems (BoardVariant.FinSystem). */
export const FIN_SYSTEM_LABELS: Record<string, string> = {
  fcs2: "FCS II",
  fcs: "FCS",
  futures: "Futures",
  single_box: "Single box",
  glass_on: "Вклеенные (glass-on)",
  none: "Без плавников",
};

/* ---------------- workshop ---------------- */

export interface Workshop {
  id: UUID;
  slug: string;
  name: string;
  status: string;
  status_label: string;
  verification_status: string;
  short_description: string;
  description: string;
  region: Region | null;
  city: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  social_links: Record<string, string>;
  logo: Media | null;
  cover: Media | null;
  shaper_code: string;
  specialization: string;
  services: string[];
  lead_time: string;
  does_repair: boolean;
  repair_note: string;
  experience_since: number | null;
  promo_video: Media | null;
  rating_avg: Decimal;
  rating_count: number;
  published_at: IsoDateTime | null;
  my_role: string | null;
  can_manage: boolean;
  is_public: boolean;
  public_url: string;
  models_count: number;
  publish_requirements: PublishRequirement[];
  /** true only in the PUT response that created the workshop (SHP-01) */
  created: boolean;
}

export interface WorkshopInput {
  name?: string;
  short_description?: string;
  description?: string;
  region_id?: number | null;
  city?: string;
  address?: string;
  phone?: string;
  email?: string;
  website?: string;
  social_links?: Record<string, string>;
  logo_id?: string | null;
  cover_id?: string | null;
  shaper_code?: string;
  specialization?: string;
  services?: string[];
  lead_time?: string;
  does_repair?: boolean;
  repair_note?: string;
  promo_video_id?: string | null;
  experience_since?: number | null;
}

/* ---------------- variants ---------------- */

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
  availability: string;
  availability_label: string;
}

export interface BoardMediaItem {
  id: number;
  position: number;
  is_cover: boolean;
  variant_id: UUID | null;
  media: Media;
}

export interface Variant extends VariantShort {
  version: number;
  material: Material | null;
  construction: string;
  fin_setup: string;
  made_to_order_days: number | null;
  items_available_for_sale: number;
  photos?: BoardMediaItem[];
  model_id: UUID;
  sku_suffix: string;
  is_active: boolean;
  previous_version_id: UUID | null;
  /** orders/bookings/sales exist → changing size/material/construction creates a new version (F10) */
  has_orders: boolean;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface VariantResult extends Variant {
  /** true — a new version (new id, new SKU) was created, the old one deactivated */
  versioned: boolean;
}

export interface VariantTableRow extends Variant {
  model: { id: UUID; name: string; status: string; board_type: BoardTypeRef };
}

/**
 * Variant input. Sizes may be sent as text («5'10"», «20 1/2», «52 см») — the server parses them
 * (length/width/thickness) — or as inches (length_in…).
 */
export interface VariantInput {
  length?: string;
  width?: string;
  thickness?: string;
  length_in?: string | number;
  width_in?: string | number;
  thickness_in?: string | number | null;
  volume_l?: string | number | null;
  material_id?: number | null;
  construction?: string;
  fin_system?: string;
  fin_setup?: string;
  price?: string | number | null;
  currency?: string;
  made_to_order_days?: number | null;
  sku_suffix?: string;
  is_active?: boolean;
  in_stock_quantity?: number;
}

export interface BulkRowInput {
  id: UUID;
  price?: string | number | null;
  currency?: string;
  made_to_order_days?: number | null;
  is_active?: boolean;
  in_stock_quantity?: number;
}

/* ---------------- models ---------------- */

export interface BoardModelCard {
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
  availability: string;
  availability_label: string;
  variants_count: number;
  primary_variant: VariantShort | null;
  public_url: string;
  status: string;
  status_label: string;
  is_public: boolean;
  serial: number | null;
  published_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface BoardModelDetail extends BoardModelCard {
  workshop: { id: UUID; slug: string; name: string };
  description: string;
  tags: string[];
  photos: BoardMediaItem[];
  video: Media | null;
  variants: Variant[];
  publish_requirements: PublishRequirement[];
}

export interface BoardModelInput {
  name?: string;
  slug?: string;
  board_type_id?: number;
  description?: string;
  tags?: string[];
  /** only on create */
  variants?: VariantInput[];
}

export interface ModelMediaPayload {
  photos: BoardMediaItem[];
  variants: Array<{ variant_id: UUID; photos: BoardMediaItem[] }>;
  video: Media | null;
}

export type ModelsFilter = {
  status?: string;
  availability?: string;
  board_type?: string;
  q?: string;
  page?: number;
  page_size?: number;
};

/* ---------------- metrics (MET-03) ---------------- */

export type MetricUnit = "count" | "percent" | "money" | "rating" | "days" | "minutes";

export interface DashboardMetric {
  key: string;
  label: string;
  /** int | float | decimal string (money) | null (no data for the formula) */
  value: number | string | null;
  unit: MetricUnit;
  formula: string;
  currency: string | null;
}

export interface ShaperBreakdowns {
  interest_by_board_type: Array<{ board_type: string; name: string; views: number; inquiries: number }>;
  views_by_subject: { board_model: number; board_variant: number };
  inquiries_by_status: Record<string, number>;
  revenue_by_currency: Array<{ currency: string; amount: Decimal; deals: number; average: Decimal | null }>;
  deals_unconfirmed: number;
}

export interface MetricsResponse<B = ShaperBreakdowns> {
  scope: string;
  period: { from: string; to: string; timezone: string; starts_at: IsoDateTime; ends_at: IsoDateTime };
  rule_version: number;
  generated_at: IsoDateTime;
  subject: { organizations?: Array<{ id: UUID; slug: string; name: string; kind: string }> };
  metrics: DashboardMetric[];
  breakdowns: B;
}

export function metricByKey(data: Pick<MetricsResponse<unknown>, "metrics"> | undefined, key: string): DashboardMetric | undefined {
  return data?.metrics.find((m) => m.key === key);
}

/* ---------------- inquiries preview (panel, SHO-01) ---------------- */

export interface InquiryParty {
  type: "account" | "organization";
  id: UUID;
  name: string;
  avatar: Media | null;
  logo: Media | null;
  handle: string | null;
  slug: string | null;
  kind: string | null;
  url: string | null;
}

export interface InquiryPreview {
  id: UUID;
  kind: string;
  kind_label: string;
  status: string;
  status_label: string;
  subject: string;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  my_role: "customer" | "provider";
  counterpart: InquiryParty | null;
  context: { type: string; id: string; title: string; subtitle: string; image: string | null; url: string | null } | null;
  last_message: { id: UUID; kind: string; body: string; created_at: IsoDateTime; sender_name: string | null; is_mine: boolean } | null;
  unread_count: number;
  conversation_id: UUID | null;
  agreed_amount: Decimal | null;
  currency: string;
  amount_confirmed: boolean;
}

/* ---------------- API ---------------- */

const qs = (organization?: string | null): Query | undefined => (organization ? { organization } : undefined);

export const shaperApi = {
  /** GET me/workshop — 404 `no_workshop` when the user has no workshop yet. */
  workshop: (organization?: string | null) => api.get<Workshop>("me/workshop", { query: qs(organization) }),
  /** PUT me/workshop — creates (201, created=true) or partially updates the workshop. */
  saveWorkshop: (body: WorkshopInput, organization?: string | null) => api.put<Workshop>("me/workshop", body, { query: qs(organization) }),
  publishWorkshop: (id: string) => api.post<Workshop>(`workshops/${id}/publish`),
  unpublishWorkshop: (id: string) => api.post<Workshop>(`workshops/${id}/unpublish`),

  boardTypes: (workshopId: string) => api.get<BoardType[]>(`workshops/${workshopId}/board-types`),
  createBoardType: (workshopId: string, body: { name: string; silhouette?: string }) =>
    api.post<BoardType>(`workshops/${workshopId}/board-types`, body),
  updateBoardType: (workshopId: string, typeId: number, body: { name?: string; silhouette?: string }) =>
    api.patch<BoardType>(`workshops/${workshopId}/board-types/${typeId}`, body),
  deleteBoardType: (workshopId: string, typeId: number) => api.delete(`workshops/${workshopId}/board-types/${typeId}`),

  materials: (workshopId: string) => api.get<Material[]>(`workshops/${workshopId}/materials`),
  createMaterial: (workshopId: string, name: string) => api.post<Material>(`workshops/${workshopId}/materials`, { name }),
  updateMaterial: (workshopId: string, materialId: number, name: string) =>
    api.patch<Material>(`workshops/${workshopId}/materials/${materialId}`, { name }),
  deleteMaterial: (workshopId: string, materialId: number) => api.delete(`workshops/${workshopId}/materials/${materialId}`),

  models: (workshopId: string, filter: ModelsFilter = {}) =>
    api.get<Paginated<BoardModelCard>>(`workshops/${workshopId}/models`, { query: { page_size: 100, ...filter } }),
  createModel: (workshopId: string, body: BoardModelInput) => api.post<BoardModelDetail>(`workshops/${workshopId}/models`, body),
  model: (modelId: string) => api.get<BoardModelDetail>(`models/${modelId}`),
  updateModel: (modelId: string, body: BoardModelInput) => api.patch<BoardModelDetail>(`models/${modelId}`, body),
  /** «deleted» or «archived» (a model with inquiries/items is archived, history kept) */
  deleteModel: (modelId: string) => api.delete<{ result: "deleted" | "archived" }>(`models/${modelId}`),
  publishModel: (modelId: string) => api.post<BoardModelDetail>(`models/${modelId}/publish`),
  unpublishModel: (modelId: string) => api.post<BoardModelDetail>(`models/${modelId}/unpublish`),

  modelMedia: (modelId: string) => api.get<ModelMediaPayload>(`models/${modelId}/media`),
  addModelPhotos: (modelId: string, mediaIds: string[]) => api.post<ModelMediaPayload>(`models/${modelId}/media`, { media_ids: mediaIds }),
  orderModelPhotos: (modelId: string, ids: number[]) => api.put<ModelMediaPayload>(`models/${modelId}/media/order`, { ids }),
  deleteModelPhoto: (modelId: string, itemId: number) => api.delete<ModelMediaPayload>(`models/${modelId}/media/${itemId}`),
  setModelVideo: (modelId: string, mediaId: string) => api.put<ModelMediaPayload>(`models/${modelId}/video`, { media_id: mediaId }),
  deleteModelVideo: (modelId: string) => api.delete<ModelMediaPayload>(`models/${modelId}/video`),

  createVariant: (modelId: string, body: VariantInput) => api.post<VariantResult>(`models/${modelId}/variants`, body),
  updateVariant: (modelId: string, variantId: string, body: VariantInput) =>
    api.patch<VariantResult>(`models/${modelId}/variants/${variantId}`, body),
  /** «deleted» or «deactivated» (variant with history/items) */
  deleteVariant: (modelId: string, variantId: string) =>
    api.delete<{ result: "deleted" | "deactivated" }>(`models/${modelId}/variants/${variantId}`),

  /** All active variants of the workshop for the bulk table (BRD-12). */
  variants: (workshopId: string) => api.get<VariantTableRow[]>(`workshops/${workshopId}/variants`),
  /** All-or-nothing; validation errors come keyed `items.N.field`. */
  bulkVariants: (workshopId: string, items: BulkRowInput[]) =>
    api.patch<{ updated: number; items: VariantTableRow[] }>(`workshops/${workshopId}/variants/bulk`, { items }),

  metrics: (q: { organization_id?: string | null; from?: string; to?: string; tz?: string } = {}) =>
    api.get<MetricsResponse>("me/metrics", {
      query: { scope: "shaper", organization_id: q.organization_id ?? undefined, from: q.from, to: q.to, tz: q.tz },
    }),

  inquiries: (q: { organization?: string | null; page_size?: number } = {}) =>
    api.get<Paginated<InquiryPreview>>("inquiries", {
      query: { box: "incoming", role: "shaper", organization: q.organization ?? undefined, page_size: q.page_size ?? 3 },
    }),

  regions: () => api.get<Region[] | Paginated<Region>>("regions").then((d) => (Array.isArray(d) ? d : d.results)),
};

/* ---------------- helpers ---------------- */

/** Board silhouette image under /public/ui/boards (7 drawn shapes; the rest map to the closest one). */
export function silhouetteSrc(silhouette: string | null | undefined): string {
  const map: Record<string, string> = {
    shortboard: "shortboard",
    fish: "fish",
    funboard: "funboard",
    midlength: "funboard",
    egg: "funboard",
    longboard: "longboard",
    softtop: "longboard",
    gun: "gun",
    hybrid: "shortboard",
    sup: "sup",
  };
  return `/ui/boards/${map[silhouette ?? ""] ?? "custom"}.svg`;
}
