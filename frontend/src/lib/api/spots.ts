/**
 * Spots domain (SPT-01…12, GEO-04): regions, catalogue, map markers, detail, forecast, dictionaries, proposals.
 * Shapes: backend/apps/spots/serializers.py. Enum values arrive as `{code, label}` — read via choiceCode/choiceLabel.
 */
import { api } from "./client";
import type { CompassPoint, Decimal, IsoDateTime, Media, PublicAccount, UUID } from "./types";
import type { OwnReview } from "./publicReviews";
import { formatDate } from "../format";

// type aliases (not interfaces) so they stay assignable to labels.ts `Choice` (index signature)
export type Choice<T extends string | number = string> = {
  code: T;
  label: string;
};

export type CompassChoice = Choice<CompassPoint> & {
  short: string;
  degrees: number | null;
};

/** GET /regions (not paginated). */
export interface Region {
  id: number;
  slug: string;
  name: string;
  timezone: string;
  center_lat: number | null;
  center_lng: number | null;
  map_zoom: number | null;
  spots_count: number;
}

export interface RegionShort {
  id: number;
  slug: string;
  name: string;
}

/** GET /spots — catalogue card. */
export interface SpotCard {
  id: UUID;
  slug: string;
  name: string;
  region: RegionShort | null;
  status: Choice | null;
  lat: number | null;
  lng: number | null;
  /** false → coordinates are rounded / region only (SPT-12) */
  precise: boolean;
  location_precision: Choice | null;
  short_description: string;
  difficulty: Choice | null;
  bottom_type: Choice | null;
  break_type: Choice | null;
  season: string;
  best_wind_directions: CompassChoice[];
  best_swell_directions: CompassChoice[];
  hazards: Choice[];
  seasonal_warning: string;
  closed_until: string | null;
  is_closed: boolean;
  cover: Media | null;
  rating_avg: Decimal;
  rating_count: number;
  has_webcam: boolean;
}

/** GET /spots/map → {count, markers} (cached, not paginated). */
export interface MapMarker {
  id: UUID;
  slug: string;
  name: string;
  region_slug: string;
  region_name: string;
  lat: number;
  lng: number;
  precise: boolean;
  difficulty: string;
  difficulty_label: string;
  status: string;
  is_closed: boolean;
  rating_avg: Decimal;
  rating_count: number;
  thumbnail_url: string | null;
}

export interface MapResponse {
  count: number;
  markers: MapMarker[];
}

export interface InfrastructureItem {
  type: string;
  type_label: string;
  name: string;
  distance_m: number | null;
}

export interface SpotPhoto {
  id: number | UUID;
  media: Media;
  caption: string;
  position: number;
  author: PublicAccount | null;
  created_at: IsoDateTime;
}

export interface SpotSource {
  id: number;
  source: string;
  url: string;
  note: string;
  confirmed_at: IsoDateTime | null;
}

export interface SpotOrganization {
  id: UUID;
  slug: string;
  name: string;
  kind: Choice;
  short_description: string;
  city: string;
  logo: Media | null;
  rating_avg: Decimal;
  rating_count: number;
  is_verified: boolean;
}

export interface SpotInstructor {
  id: UUID;
  account: PublicAccount;
  headline: string;
  rating_avg: Decimal;
  rating_count: number;
  price_from: Decimal | null;
  currency: string;
  certificate_verified: boolean;
}

export interface PendingProposalShort {
  id: UUID;
  status: Choice;
  changed_fields: string[];
  moderator_comment: string;
  created_at: IsoDateTime;
}

/** GET /spots/{slug} (SPT-02…12). `my_review` / `my_pending_proposals` only with the session cookie. */
export interface SpotDetail extends SpotCard {
  description: string;
  wave_character: string;
  wave_power: string;
  best_months: Array<Choice<number>>;
  best_tide: string;
  typical_conditions: string;
  water_temp_note: string;
  hazard_notes: string;
  entry_exit: string;
  access: string;
  infrastructure: InfrastructureItem[];
  photos: SpotPhoto[];
  webcam_url: string | null;
  webcam_is_premium: boolean;
  data_source: string;
  last_confirmed_at: IsoDateTime | null;
  sources: SpotSource[];
  organizations: SpotOrganization[];
  instructors: SpotInstructor[];
  my_review: OwnReview | null;
  my_pending_proposals: PendingProposalShort[];
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface ForecastItem {
  valid_from: IsoDateTime;
  valid_to: IsoDateTime | null;
  wave_height_m: Decimal | number | null;
  wave_period_s: Decimal | number | null;
  wave_direction: string | null;
  wind_speed_ms: Decimal | number | null;
  wind_direction: string | null;
  water_temp_c: Decimal | number | null;
  tide_note: string;
}

/** GET /spots/{slug}/forecast — `provider: null` when no provider is connected (GEO-04). */
export interface ForecastResponse {
  provider: string | null;
  provider_title: string | null;
  issued_at: IsoDateTime | null;
  items: ForecastItem[];
  message: string;
}

export type EditableFieldKind = "text" | "choice" | "compass" | "months" | "hazards" | "infrastructure";

export interface EditableField {
  field: EditableSpotField;
  label: string;
  kind: EditableFieldKind;
  max_length: number | null;
}

export type EditableSpotField =
  | "short_description"
  | "description"
  | "difficulty"
  | "bottom_type"
  | "break_type"
  | "wave_character"
  | "wave_power"
  | "season"
  | "best_months"
  | "best_wind_directions"
  | "best_swell_directions"
  | "best_tide"
  | "typical_conditions"
  | "hazards"
  | "hazard_notes"
  | "entry_exit"
  | "access"
  | "infrastructure"
  | "water_temp_note"
  | "seasonal_warning";

/** GET /spots/dictionaries */
export interface SpotDictionaries {
  difficulty: Choice[];
  bottom_type: Choice[];
  break_type: Choice[];
  location_precision: Choice[];
  compass_points: CompassChoice[];
  months: Array<Choice<number>>;
  hazards: Choice[];
  infrastructure_types: Choice[];
  editable_fields: EditableField[];
}

/** Infrastructure value as sent in a proposal. */
export interface InfrastructureInput {
  type: string;
  name: string;
  distance_m: number | null;
}

export type ProposalValue = string | string[] | number[] | InfrastructureInput[] | null;

export interface ProposalCreateInput {
  changes: Partial<Record<EditableSpotField, ProposalValue>>;
  comment?: string;
  source?: string;
  evidence_ids?: UUID[];
}

export interface ProposalChange {
  field: EditableSpotField;
  label: string;
  kind: EditableFieldKind;
  old: unknown;
  new: unknown;
  old_display: string;
  new_display: string;
}

/** POST /spots/{id}/proposals → 201 */
export interface Proposal {
  id: UUID;
  spot: { id: UUID; slug: string; name: string };
  status: Choice;
  changes: ProposalChange[];
  comment: string;
  source: string;
  evidence: Media[];
  moderator_comment: string;
  decided_at: IsoDateTime | null;
  is_reverted: boolean;
  reverted_at: IsoDateTime | null;
  can_edit: boolean;
  can_withdraw: boolean;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

/** Catalogue filters (URL params of /spots and query params of GET /spots). */
export interface SpotFilters {
  region?: string;
  difficulty?: string;
  bottom?: string;
  break?: string;
  q?: string;
  sort?: string;
  page?: number;
}

export const SPOT_FILTER_KEYS = ["region", "difficulty", "bottom", "break", "q", "sort"] as const;

export const spotsApi = {
  detail: (slug: string) => api.get<SpotDetail>(`spots/${encodeURIComponent(slug)}`),
  forecast: (slug: string) => api.get<ForecastResponse>(`spots/${encodeURIComponent(slug)}/forecast`),
  dictionaries: () => api.get<SpotDictionaries>("spots/dictionaries"),
  propose: (spotId: string, body: ProposalCreateInput) =>
    api.post<Proposal>(`spots/${encodeURIComponent(spotId)}/proposals`, body),
};

export const spotKeys = {
  all: ["spots"] as const,
  detail: (slug: string) => ["spots", "detail", slug] as const,
  forecast: (slug: string) => ["spots", "forecast", slug] as const,
  dictionaries: ["spots", "dictionaries"] as const,
};

/** «1,2 км» / «350 м» for infrastructure distances (SPT-06). */
export function formatDistance(meters: number | null | undefined): string {
  if (meters === null || meters === undefined || !Number.isFinite(meters)) return "";
  if (meters < 1000) return `${Math.round(meters)} м`;
  const km = meters / 1000;
  return `${km.toLocaleString("ru-RU", { maximumFractionDigits: km < 10 ? 1 : 0 })} км`;
}

/** Coordinates as «53.0590, 158.8220» (fixed 4 decimals). */
export function formatCoords(lat: number | null | undefined, lng: number | null | undefined): string {
  if (lat === null || lat === undefined || lng === null || lng === undefined) return "";
  return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
}

/** Date-only value ("2026-11-01") → «1 ноября 2026 г.» without time-zone drift. */
export function formatDay(value: string | null | undefined): string {
  if (!value) return "";
  return formatDate(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00Z` : value, { timeZone: "UTC", style: "long" });
}
