/**
 * Shared API types (contract: docs/ARCHITECTURE.md). Field names are the backend's snake_case.
 * Domain-specific response types live next to their API functions in src/lib/api/<domain>.ts.
 */

export type UUID = string;
/** ISO 8601 with timezone, e.g. "2026-10-21T09:00:00+03:00". */
export type IsoDateTime = string;
/** "YYYY-MM-DD". */
export type IsoDate = string;
/** Money is a decimal string ("65000.00") + currency (ARCHITECTURE §2). */
export type Decimal = string;

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    fields?: Record<string, string[]>;
    request_id?: string;
  };
}

/** DRF page: `?page=&page_size=` (≤100). */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type MediaKind = "image" | "video" | "document";
export type MediaStatus = "pending" | "processing" | "ready" | "rejected" | "deleted";
export type MediaVisibility = "public" | "private";
export type MediaPurpose =
  | "avatar"
  | "org_logo"
  | "org_cover"
  | "org_gallery"
  | "spot_photo"
  | "spot_evidence"
  | "board_photo"
  | "board_video"
  | "promo_video"
  | "profile_gallery"
  | "item_photo"
  | "certificate"
  | "message_attachment"
  | "repair_photo"
  | "handover_photo"
  | "review_photo"
  | "diary_photo"
  | "event_cover"
  | "product_photo"
  | "data_export";

/** apps.mediafiles.serializers.MediaSerializer — the only media shape in API responses. */
export interface Media {
  id: UUID;
  kind: MediaKind;
  purpose: MediaPurpose;
  visibility: MediaVisibility;
  status: MediaStatus;
  /** null for private files — request GET /media/{id}/url */
  url: string | null;
  thumbnail_url: string | null;
  poster_url: string | null;
  content_type: string;
  size_bytes: number | null;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  alt_text: string;
  original_filename: string;
  /** only in owner views (GET /media/{id}) */
  rejection_reason?: string;
  created_at?: string;
}

/** apps.accounts.serializers_public.PublicAccountSerializer — authors, chat partners, team members. */
export interface PublicAccount {
  id: UUID;
  handle: string | null;
  display_name: string;
  avatar: Media | null;
  is_deleted: boolean;
}

export interface RegionRef {
  id: number | string;
  slug: string;
  name: string;
  timezone?: string;
}

export type SpecialtyCode = "surfer" | "instructor" | "shaper" | "rental";
/** Registration «основной тип» (ACC-01). `school` registers a surfer + `next_step: "create_school"`. */
export type PrimaryType = SpecialtyCode | "school";
export type StaffRole = "moderator" | "admin" | "organizer";
export type OrganizationKind = "school" | "workshop" | "rental";
export type MembershipRole = "owner" | "manager" | "instructor" | "staff";

/** 16-point compass codes used by spots (best_wind_directions / best_swell_directions). */
export type CompassPoint =
  | "N"
  | "NNE"
  | "NE"
  | "ENE"
  | "E"
  | "ESE"
  | "SE"
  | "SSE"
  | "S"
  | "SSW"
  | "SW"
  | "WSW"
  | "W"
  | "WNW"
  | "NW"
  | "NNW";

/** GET /me/counters — the source of truth for header/tab badges (MSG-06/07, ATX-10). */
export interface Counters {
  unread_messages: number;
  unread_notifications: number;
  new_inquiries: number;
  pending_bookings: number;
}

export type FavoriteTargetType = "spot" | "instructor" | "organization" | "board_model" | "inventory_item";

export type Rating = { rating_avg: Decimal | number; rating_count: number };

/** Minimal list item shapes used by the home page teasers; page engineers extend them in their domain files. */
/** Enum value as a plain code or a `{code, label}` object — read with choiceCode()/choiceLabel() from labels.ts. */
export type ChoiceValue<T extends string = string> = T | { code: T; label?: string; [key: string]: unknown };

export interface SpotListItem extends Partial<Rating> {
  id: UUID | number;
  slug: string;
  name: string;
  region?: RegionRef | string | null;
  short_description?: string;
  difficulty?: ChoiceValue;
  break_type?: ChoiceValue;
  bottom_type?: ChoiceValue;
  season?: string;
  cover?: Media | null;
  best_wind_directions?: Array<ChoiceValue<CompassPoint>>;
  best_swell_directions?: Array<ChoiceValue<CompassPoint>>;
}

export interface InstructorListItem extends Partial<Rating> {
  id: UUID | number;
  handle: string;
  display_name?: string;
  account?: PublicAccount;
  headline?: string;
  avatar?: Media | null;
  photo?: Media | null;
  regions?: Array<Partial<RegionRef> & { name: string }>;
  spots?: Array<{ slug: string; name: string }>;
  price_from?: Decimal | null;
  currency?: string;
  certificate_status?: "none" | "uploaded" | "verified";
  board_types?: string[];
  student_levels?: string[];
}
