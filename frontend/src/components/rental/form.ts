/**
 * Inventory form model: values ↔ API payload, client checks that mirror the server (the server stays the
 * authority, 9.1) and the photo diff used after PATCH. Pure functions → unit-tested.
 */
import type { InventoryInput, InventoryItem, ItemPhoto } from "@/lib/api/inventory";
import type { Media } from "@/lib/api/types";
import type { FormErrors } from "@/lib/forms";

export interface InventoryFormValues {
  kind: string;
  purpose: string;
  title: string;
  description: string;
  size: string;
  condition: string;
  region_id: string;
  spot_id: string;
  pickup_location: string;
  available_hours: string;
  rental_price_per_hour: string;
  rental_price_per_day: string;
  deposit_note: string;
  min_rental_hours: string;
  restrictions: string;
  sale_price: string;
  serial_number: string;
  is_published: boolean;
  variant_id: string;
}

export type InventoryField = keyof InventoryFormValues | "photos";

export const RENTAL_PURPOSES = new Set(["rental", "both"]);
export const SALE_PURPOSES = new Set(["sale", "both"]);

const money = (v: string | null | undefined) => {
  if (v === null || v === undefined || v === "") return "";
  const n = Number(v);
  return Number.isFinite(n) ? String(n) : String(v);
};

export function emptyValues(defaults: { region_id?: string } = {}): InventoryFormValues {
  return {
    kind: "board",
    purpose: "rental",
    title: "",
    description: "",
    size: "",
    condition: "good",
    region_id: defaults.region_id ?? "",
    spot_id: "",
    pickup_location: "",
    available_hours: "",
    rental_price_per_hour: "",
    rental_price_per_day: "",
    deposit_note: "",
    min_rental_hours: "1",
    restrictions: "",
    sale_price: "",
    serial_number: "",
    is_published: true,
    variant_id: "",
  };
}

export function valuesFromItem(item: InventoryItem): InventoryFormValues {
  return {
    kind: item.kind || "board",
    purpose: item.purpose || "rental",
    title: item.title ?? "",
    description: item.description ?? "",
    size: item.size ?? "",
    condition: item.condition || "good",
    region_id: item.region ? String(item.region.id) : "",
    spot_id: item.spot ? String(item.spot.id) : "",
    pickup_location: item.pickup_location ?? "",
    available_hours: item.available_hours ?? "",
    rental_price_per_hour: money(item.rental_price_per_hour),
    rental_price_per_day: money(item.rental_price_per_day),
    deposit_note: item.deposit_note ?? "",
    min_rental_hours: String(item.min_rental_hours ?? 1),
    restrictions: item.restrictions ?? "",
    sale_price: money(item.sale_price),
    serial_number: item.serial_number ?? "",
    is_published: Boolean(item.is_published),
    variant_id: item.variant?.id ?? "",
  };
}

const MONEY_RE = /^\d{1,8}([.,]\d{1,2})?$/;

/** Client-side checks (same rules as apps.inventory: title, rental rate for rental/both, numbers). */
export function validateValues(v: InventoryFormValues): FormErrors<InventoryField> {
  const errors: FormErrors<InventoryField> = {};
  if (!v.title.trim()) errors.title = "Укажите название.";
  const rental = RENTAL_PURPOSES.has(v.purpose);
  for (const field of ["rental_price_per_hour", "rental_price_per_day", "sale_price"] as const) {
    const raw = v[field].trim();
    if (raw && !MONEY_RE.test(raw)) errors[field] = "Введите сумму числом, например 1500.";
  }
  if (rental && !v.rental_price_per_day.trim() && !v.rental_price_per_hour.trim() && !errors.rental_price_per_day) {
    errors.rental_price_per_day = "Укажите цену аренды за день или за час.";
  }
  if (rental) {
    const hours = Number(v.min_rental_hours);
    if (!Number.isInteger(hours) || hours < 1 || hours > 720) errors.min_rental_hours = "От 1 до 720 часов.";
  }
  return errors;
}

const num = (raw: string) => {
  const t = raw.trim().replace(",", ".");
  return t === "" ? null : t;
};

/** API payload. Prices of a purpose that is switched off are cleared so the catalogue never shows them. */
export function toPayload(
  v: InventoryFormValues,
  ctx: { organizationId?: string | null; create: boolean; photoIds?: string[]; variantsAllowed: boolean },
): InventoryInput {
  const rental = RENTAL_PURPOSES.has(v.purpose);
  const sale = SALE_PURPOSES.has(v.purpose);
  const body: InventoryInput = {
    kind: v.kind,
    purpose: v.purpose,
    title: v.title.trim(),
    description: v.description.trim(),
    size: v.size.trim(),
    condition: v.condition,
    region_id: v.region_id ? Number(v.region_id) : null,
    spot_id: v.spot_id || null,
    pickup_location: v.pickup_location.trim(),
    available_hours: v.available_hours.trim(),
    rental_price_per_hour: rental ? num(v.rental_price_per_hour) : null,
    rental_price_per_day: rental ? num(v.rental_price_per_day) : null,
    deposit_note: v.deposit_note.trim(),
    restrictions: v.restrictions.trim(),
    sale_price: sale ? num(v.sale_price) : null,
    serial_number: v.serial_number.trim(),
    is_published: v.is_published,
  };
  if (rental) body.min_rental_hours = Number(v.min_rental_hours) || 1;
  if (ctx.variantsAllowed) body.variant_id = v.kind === "board" && v.variant_id ? v.variant_id : null;
  if (ctx.create) {
    if (ctx.organizationId) body.organization_id = ctx.organizationId;
    if (ctx.photoIds?.length) body.photo_ids = ctx.photoIds;
  }
  return body;
}

/** Server field names → form fields. */
export const FIELD_ALIASES: Record<string, string> = {
  region: "region_id",
  spot: "spot_id",
  variant: "variant_id",
  photo_ids: "photos",
  media_ids: "photos",
};

export interface PhotoDiff {
  /** ItemPhoto ids to DELETE */
  remove: number[];
  /** Media ids to POST */
  add: string[];
}

/** What to send after PATCH to turn the saved gallery (`baseline`) into the edited one (`local`). */
export function diffPhotos(baseline: ItemPhoto[], local: Media[]): PhotoDiff {
  const localIds = new Set(local.map((m) => m.id));
  const savedIds = new Set(baseline.map((p) => p.media.id));
  return {
    remove: baseline.filter((p) => !localIds.has(p.media.id)).map((p) => p.id),
    add: local.filter((m) => !savedIds.has(m.id)).map((m) => m.id),
  };
}

/** ItemPhoto ids in the local order, or null when the server order already matches. */
export function desiredOrder(saved: ItemPhoto[], local: Media[]): number[] | null {
  const byMedia = new Map(saved.map((p) => [p.media.id, p.id]));
  const ids = local.map((m) => byMedia.get(m.id)).filter((id): id is number => typeof id === "number");
  if (ids.length !== saved.length) return null;
  const current = [...saved].sort((a, b) => a.position - b.position || a.id - b.id).map((p) => p.id);
  return ids.every((id, i) => id === current[i]) ? null : ids;
}
