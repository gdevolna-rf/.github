/**
 * «Мои бронирования» / «Бронирования клиентов» (fe-account; 7.3, MSG-02, ATX-27, RENT-06).
 * Shapes: backend/apps/commerce/serializers.py (BookingSerializer, BookingDetailSerializer) and
 * apps/inventory/serializers.py (HandoverSerializer). Keys live under the shared "bookings" head.
 */
import { api } from "./client";
import { qk } from "./keys";
import type { PartyCard, OrgBrief } from "./account-inbox";
import type { Decimal, Media, Paginated, PublicAccount, UUID } from "./types";

export type BookingStatus = "requested" | "confirmed" | "in_progress" | "completed" | "declined" | "cancelled" | "no_show";
export type BookingAction = "confirm" | "decline" | "start" | "complete" | "no_show" | "cancel";
export type BookingBox = "mine" | "provider";
export type BookingKind = "lesson" | "rental";

export interface BookingLessonCard {
  session_id: UUID;
  title: string;
  status: string;
  starts_at: string;
  ends_at: string;
  capacity: number;
  free_seats: number;
  program: { id: UUID; title: string } | null;
  offer: { id: UUID; title: string } | null;
  spot: { id: UUID; name: string; slug: string } | null;
  instructor: PublicAccount | null;
  url: string;
}

export interface BookingRentalCard {
  item_id: UUID;
  title: string;
  kind: string;
  size: string;
  photo: Media | null;
  pickup_location: string;
  rental_price_per_day: Decimal | null;
  rental_price_per_hour: Decimal | null;
  url: string;
}

export interface Booking {
  id: UUID;
  kind: BookingKind;
  kind_label: string;
  status: BookingStatus;
  status_label: string;
  my_role: "customer" | "provider";
  title: string;
  starts_at: string;
  ends_at: string;
  seats: number;
  participant_name: string;
  participant_is_minor: boolean;
  guardian_consent_at: string | null;
  price_amount: Decimal | null;
  currency: string;
  amount_confirmed: boolean;
  customer_note: string;
  group_key: UUID | null;
  is_overdue: boolean;
  damage_reported: boolean;
  decline_reason: string;
  cancel_reason: string;
  cancelled_side: "customer" | "provider" | "system" | "";
  confirmed_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  customer: PublicAccount;
  provider: PartyCard | null;
  provider_organization: OrgBrief | null;
  lesson: BookingLessonCard | null;
  rental: BookingRentalCard | null;
  /** id of the related inquiry (chat), if the booking was made from one */
  inquiry: UUID | null;
  actions: BookingAction[];
}

export interface BookingHistoryEntry {
  from_status: string;
  from_status_label: string;
  to_status: string;
  to_status_label: string;
  actor: PublicAccount | null;
  comment: string;
  created_at: string;
}

export interface BookingDetail extends Booking {
  history: BookingHistoryEntry[];
  group: Array<{ id: UUID; kind: BookingKind; status: BookingStatus; title: string; starts_at: string; ends_at: string }>;
}

export type HandoverKind = "issue" | "return";
export type ItemCondition = "new" | "excellent" | "good" | "fair";

export interface Handover {
  id: UUID;
  booking_id: UUID;
  kind: HandoverKind;
  kind_label: string;
  condition: ItemCondition;
  condition_label: string;
  notes: string;
  damage_reported: boolean;
  damage_description: string;
  photos: Media[];
  recorded_by: PublicAccount;
  created_at: string;
}

export interface HandoverInput {
  kind: HandoverKind;
  condition: ItemCondition;
  notes?: string;
  damage_reported?: boolean;
  damage_description?: string;
  photo_ids?: UUID[];
}

export interface BookingListQuery {
  box: BookingBox;
  status?: string;
  kind?: BookingKind | "";
  from?: string;
  to?: string;
  organization?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export const bookingKeys = {
  list: (q: BookingListQuery) => ["bookings", "list", q] as const,
  detail: (id: string) => qk.booking(id),
  handovers: (id: string) => ["bookings", id, "handovers"] as const,
};

export const bookingsApi = {
  list: (q: BookingListQuery) =>
    api.get<Paginated<Booking>>("bookings", {
      query: {
        box: q.box,
        status: q.status,
        kind: q.kind || undefined,
        from: q.from,
        to: q.to,
        organization: q.organization,
        order: q.order === "asc" ? "asc" : undefined,
        page: q.page,
        page_size: q.page_size ?? 20,
      },
    }),
  detail: (id: UUID) => api.get<BookingDetail>(`bookings/${id}`),
  action: (id: UUID, action: BookingAction, body: { reason?: string; amount_confirmed?: boolean | null } = {}) =>
    api.post<BookingDetail>(`bookings/${id}/${action === "no_show" ? "no-show" : action}`, body),
  handovers: (id: UUID) => api.get<Handover[]>(`bookings/${id}/handovers`),
  handover: (id: UUID, body: HandoverInput) => api.post<Handover>(`bookings/${id}/handover`, body),
};
