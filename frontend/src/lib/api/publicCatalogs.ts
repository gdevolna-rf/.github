/**
 * Публичные каталоги: аренда (RENT-01..05), GG Surfer (COM-02/03), клуб (CLB-01..04), мерч (SHOP-02).
 * Формы — backend/apps/{inventory,community,club,shop}/serializers.py.
 */
import { api, newIdempotencyKey } from "./client";
import type { Decimal, IsoDateTime, Media, UUID } from "./types";

export interface RentalOwner {
  type: "account" | "organization";
  id: UUID;
  name: string;
  handle: string | null;
  slug: string | null;
  kind: string | null;
  avatar: Media | null;
}

export interface RentalCard {
  id: UUID;
  title: string;
  kind: string;
  kind_label: string;
  purpose: string;
  size: string;
  condition: string;
  condition_label: string;
  region: { slug: string; name: string } | null;
  spot: { slug: string; name: string } | null;
  pickup_location: string;
  available_hours: string;
  rental_price_per_day: Decimal | null;
  rental_price_per_hour: Decimal | null;
  min_rental_hours: number;
  deposit_note: string;
  currency: string;
  cover: Media | null;
  photos_count: number;
  owner: RentalOwner;
  variant: { sku: string; model_name: string; dimensions_display: string; volume_display: string | null; shaper: { slug: string; name: string } } | null;
  is_own: boolean;
}

export interface RentalDetail extends RentalCard {
  description: string;
  restrictions: string;
  photos: Array<{ id: number; position: number; media: Media }>;
  booked_intervals: Array<{ starts_at: IsoDateTime; ends_at: IsoDateTime }>;
}

export interface SurferCard {
  id: UUID;
  handle: string;
  display_name: string;
  avatar: Media | null;
  region: { slug: string; name: string } | null;
  age: number | null;
  riding_level: string;
  riding_level_label: string;
  surfing_since: number | null;
  experience_years: number | null;
  preferred_board_types: string[];
  favorite_spots: Array<{ slug: string; name: string }>;
  interests: string[];
  bio_excerpt: string;
  fun_facts: string[];
  accepts_messages: boolean;
  can_message: boolean;
  is_me: boolean;
  url: string;
}

export interface SurferDetail extends SurferCard {
  bio: string;
  languages: string[];
  member_since: IsoDateTime;
  instructor_url: string | null;
  diary: { ride_days: number; sessions: number; spots_visited: number; this_year_days: number; longest_streak_days: number } | null;
}

export interface ClubEventCard {
  id: UUID;
  slug: string;
  title: string;
  kind: string;
  kind_label: string;
  status: string;
  status_label: string;
  starts_at: IsoDateTime;
  ends_at: IsoDateTime;
  timezone: string;
  spot: { slug: string; name: string } | null;
  region: { slug: string; name: string } | null;
  location_note: string;
  capacity: number | null;
  registrations_count: number;
  waitlist_count: number;
  free_places: number | null;
  is_full: boolean;
  registration_open: boolean;
  cover: Media | null;
  url: string;
}

export interface ClubRegistration {
  id: UUID;
  status: "registered" | "waitlist" | "cancelled";
  status_label: string;
  waitlist_position: number | null;
}

export interface ClubEventDetail extends ClubEventCard {
  description: string;
  my_registration: ClubRegistration | null;
}

export interface ClubOverview {
  about: {
    kicker: string;
    title: string;
    text: string;
    invite: { eyebrow: string; title: string; text: string } | null;
    highlights_title: string;
    highlights: Array<{ emoji: string; title: string; text: string }>;
    roadmap: Array<{ label: string; text: string }>;
    banner: { title: string; text: string; cta_label: string; cta_url: string } | null;
  };
  stats: { members: number; upcoming_events: number };
  announcements: Array<{ id: UUID; title: string; body: string; is_pinned: boolean; published_at: IsoDateTime | null }>;
  upcoming_events: ClubEventCard[];
}

export interface ProductCard {
  id: UUID;
  slug: string;
  title: string;
  category: string;
  category_label: string;
  status: string;
  status_label: string;
  cover: Media | null;
  price_from: Decimal | null;
  price_to: Decimal | null;
  currency: string;
  in_stock: boolean;
  url: string;
}

export interface ProductDetail extends ProductCard {
  description: string;
  specs: Record<string, string | number>;
  gallery: Media[];
  variants: Array<{ id: UUID; sku: string; name: string; price: Decimal; currency: string; stock: number; in_stock: boolean }>;
  delivery_note: string;
  returns_note: string;
  purchase_available: boolean;
  purchase_note: string;
  my_interest: { id: UUID; created_at: IsoDateTime } | null;
}

export const publicApi = {
  rentalBook: (itemId: UUID, startsAt: string, endsAt: string, key = newIdempotencyKey()) =>
    api.post<{ id: UUID; price_amount: Decimal | null; currency: string }>(
      "bookings",
      { inventory_item_id: itemId, starts_at: startsAt, ends_at: endsAt },
      { idempotencyKey: key },
    ),
  directConversation: (accountId: UUID) => api.post<{ id: UUID }>("direct-conversations", { account_id: accountId }),
  clubEvent: (slug: string) => api.get<ClubEventDetail>(`club/events/${encodeURIComponent(slug)}`),
  clubRegister: (eventId: UUID) => api.post<ClubRegistration>(`club/events/${eventId}/registration`),
  clubCancel: (eventId: UUID) => api.delete(`club/events/${eventId}/registration`),
  product: (slug: string) => api.get<ProductDetail>(`shop/products/${encodeURIComponent(slug)}`),
  productInterest: (productId: UUID) => api.post(`shop/products/${productId}/interest`),
  productInterestRemove: (productId: UUID) => api.delete(`shop/products/${productId}/interest`),
};
