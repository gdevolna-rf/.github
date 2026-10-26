/**
 * inventory (rental cabinet, RENT-01…05): own items (personal — rental specialty; organization — any active
 * member, `?organization=`), photos (purpose item_photo, ≤10), manual status, availability overview with
 * «Свободных бордов» / «Забронировано» (RENT-04). Shapes mirror backend/apps/inventory/serializers.py.
 * Query keys are domain-first: invalidating ["inventory"] refreshes every inventory query.
 */
import { api, type Query } from "./client";
import type { Decimal, IsoDateTime, Media, Paginated, UUID } from "./types";
import type { BoardTypeRef, VariantTableRow, Workshop } from "./shaper";

export const inventoryKeys = {
  all: ["inventory"] as const,
  list: (organization: string | null, filter: Query = {}) => ["inventory", "list", organization ?? "personal", filter] as const,
  item: (id: string) => ["inventory", "item", id] as const,
  availability: (organization: string | null, from: string, to: string, kind?: string) =>
    ["inventory", "availability", organization ?? "personal", from, to, kind ?? ""] as const,
  spots: (region: string | number | null | undefined) => ["inventory", "spots", region ?? "all"] as const,
  myVariants: ["inventory", "my-workshop-variants"] as const,
};

export const INVENTORY_KINDS = ["board", "wetsuit", "sup", "fins", "accessory", "other"] as const;
export const INVENTORY_PURPOSES = ["rental", "sale", "both"] as const;
export const INVENTORY_CONDITIONS = ["new", "excellent", "good", "fair"] as const;
/** Statuses the owner sets by hand (reserved is set by sales). */
export const MANUAL_STATUSES = ["available", "maintenance", "retired", "sold"] as const;

export const PURPOSE_LABELS: Record<string, string> = {
  rental: "Аренда",
  sale: "Продажа",
  both: "Продажа и аренда",
};

export interface ItemPhoto {
  id: number;
  position: number;
  media: Media;
}

export interface ListingOwner {
  type: "account" | "organization";
  id: UUID;
  name: string;
  handle: string | null;
  slug: string | null;
  kind: string | null;
  avatar: Media | null;
}

export interface ItemVariantInfo {
  id: UUID;
  sku: string;
  model_id: UUID;
  model_name: string;
  board_type: BoardTypeRef;
  dimensions_display: string;
  volume_l: Decimal | null;
  volume_display: string | null;
  shaper: { slug: string; name: string };
}

export interface InventoryItem {
  id: UUID;
  title: string;
  kind: string;
  kind_label: string;
  purpose: string;
  size: string;
  condition: string;
  condition_label: string;
  region: { id: number; slug: string; name: string } | null;
  spot: { id: UUID; slug: string; name: string } | null;
  pickup_location: string;
  available_hours: string;
  rental_price_per_day: Decimal | null;
  rental_price_per_hour: Decimal | null;
  min_rental_hours: number;
  deposit_note: string;
  sale_price: Decimal | null;
  currency: string;
  cover: Media | null;
  photos_count: number;
  owner: ListingOwner;
  variant: ItemVariantInfo | null;
  is_own: boolean;
  public_url: string;
  description: string;
  restrictions: string;
  photos: ItemPhoto[];
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  status: string;
  status_label: string;
  is_published: boolean;
  serial_number: string;
  organization_id: UUID | null;
}

export interface InventoryInput {
  /** only on create: organization-owned item; omit for a personal one */
  organization_id?: string | null;
  variant_id?: string | null;
  kind?: string;
  purpose?: string;
  status?: string;
  title?: string;
  description?: string;
  size?: string;
  condition?: string;
  region_id?: number | null;
  spot_id?: string | null;
  pickup_location?: string;
  available_hours?: string;
  rental_price_per_day?: string | number | null;
  rental_price_per_hour?: string | number | null;
  sale_price?: string | number | null;
  deposit_note?: string;
  currency?: string;
  min_rental_hours?: number;
  restrictions?: string;
  serial_number?: string;
  is_published?: boolean;
  /** only on create; later — me/inventory/{id}/photos */
  photo_ids?: string[];
}

export interface AvailabilityBooking {
  booking_id: UUID;
  starts_at: IsoDateTime;
  ends_at: IsoDateTime;
  status: string;
}

export interface AvailabilityItem {
  id: UUID;
  title: string;
  kind: string;
  status: string;
  size: string;
  is_published: boolean;
  is_booked_now: boolean;
  is_free_in_range: boolean;
  booked: AvailabilityBooking[];
}

export interface AvailabilityOverview {
  from: IsoDateTime;
  to: IsoDateTime;
  summary: {
    /** rental items except retired/sold */
    total: number;
    /** «Свободных бордов» now */
    free_now: number;
    /** «Забронировано» now (confirmed or issued) */
    booked_now: number;
    maintenance: number;
    free_in_range: number;
    booked_in_range: number;
  };
  items: AvailabilityItem[];
}

export interface SpotRef {
  id: UUID;
  slug: string;
  name: string;
  region?: unknown;
}

export type InventoryFilter = { status?: string; kind?: string; purpose?: string; q?: string; page?: number; page_size?: number };

const org = (organization: string | null | undefined): Query => (organization ? { organization } : {});

export const inventoryApi = {
  list: (organization: string | null, filter: InventoryFilter = {}) =>
    api.get<Paginated<InventoryItem>>("me/inventory", { query: { page_size: 100, ...org(organization), ...filter } }),
  item: (id: string) => api.get<InventoryItem>(`me/inventory/${id}`),
  create: (body: InventoryInput) => api.post<InventoryItem>("me/inventory", body),
  update: (id: string, body: InventoryInput) => api.patch<InventoryItem>(`me/inventory/${id}`, body),
  /** «deleted», or «retired» when the item has bookings/inquiries (history kept) */
  remove: (id: string) => api.delete<{ result: "deleted" | "retired" }>(`me/inventory/${id}`),
  setStatus: (id: string, status: string) => api.post<InventoryItem>(`me/inventory/${id}/status`, { status }),

  addPhotos: (id: string, mediaIds: string[]) => api.post<{ photos: ItemPhoto[] }>(`me/inventory/${id}/photos`, { media_ids: mediaIds }),
  orderPhotos: (id: string, ids: number[]) => api.put<{ photos: ItemPhoto[] }>(`me/inventory/${id}/photos/order`, { ids }),
  deletePhoto: (id: string, photoId: number) => api.delete<{ photos: ItemPhoto[] }>(`me/inventory/${id}/photos/${photoId}`),

  /** «Свободных бордов» / «Забронировано» + per-item booked intervals in [from, to) (defaults: now … +24 h). */
  availability: (q: { organization?: string | null; from?: string; to?: string; kind?: string }) =>
    api.get<AvailabilityOverview>("me/inventory/availability", {
      query: { ...org(q.organization), from: q.from, to: q.to, kind: q.kind },
    }),

  spots: (region: string | number | null | undefined) =>
    api.get<Paginated<SpotRef>>("spots", { query: { region: region ?? undefined, page_size: 100 } }).then((d) => d.results),

  /**
   * Active variants of my workshop for «Связать с моделью моей мастерской» (BRD-13). Resolves [] when the user
   * has no workshop (404 no_workshop) — the field is then hidden.
   */
  myWorkshopVariants: async (): Promise<VariantTableRow[]> => {
    try {
      const workshop = await api.get<Workshop>("me/workshop");
      return await api.get<VariantTableRow[]>(`workshops/${workshop.id}/variants`);
    } catch (err) {
      const e = err as { status?: number; code?: string };
      if (e?.status === 404 || e?.code === "no_workshop" || e?.status === 403) return [];
      throw err;
    }
  },
};
