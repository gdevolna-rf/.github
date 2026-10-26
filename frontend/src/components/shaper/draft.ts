/**
 * Pure helpers of the shaper cabinet: form drafts ↔ API payloads, «what changed» diffs (only changed fields are
 * sent — re-sending a rounded display value would create a needless F10 version), gallery sync plans and
 * server error mapping (variant fields, bulk `items.N.field`).
 */
import type { Media } from "@/lib/api/types";
import type {
  BoardMediaItem,
  BulkRowInput,
  Variant,
  VariantInput,
  VariantTableRow,
  Workshop,
  WorkshopInput,
} from "@/lib/api/shaper";

/* ---------------- numbers ---------------- */

/** "62 000,50" → "62000.50"; "" → "". */
export function normalizeNumber(value: string): string {
  return value.replace(/\s+/g, "").replace(",", ".").trim();
}

/** Decimal string from the API → compact input value: "20.50" → "20.5", "84.00" → "84", null → "". */
export function decimalToInput(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return String(Math.round(n * 1000) / 1000);
}

const isNumber = (v: string) => /^-?\d+(\.\d+)?$/.test(normalizeNumber(v));

/* ---------------- variants ---------------- */

export interface VariantDraft {
  /** local key (server id for saved variants) */
  key: string;
  id?: string;
  length: string;
  width: string;
  thickness: string;
  volume: string;
  material_id: string;
  fin_system: string;
  fin_setup: string;
  construction: string;
  price: string;
  made_to_order_days: string;
  in_stock_quantity: string;
  sku_suffix: string;
  /* read-only server data */
  sku?: string;
  version?: number;
  has_orders?: boolean;
  availability?: string;
  availability_label?: string;
  is_active?: boolean;
}

export type VariantField = Exclude<keyof VariantDraft, "key" | "id" | "sku" | "version" | "has_orders" | "availability" | "availability_label" | "is_active">;

let seq = 0;
export const newKey = () => `new-${Date.now().toString(36)}-${(seq += 1)}`;

export function emptyVariantDraft(): VariantDraft {
  return {
    key: newKey(),
    length: "",
    width: "",
    thickness: "",
    volume: "",
    material_id: "",
    fin_system: "fcs2",
    fin_setup: "",
    construction: "",
    price: "",
    made_to_order_days: "",
    in_stock_quantity: "0",
    sku_suffix: "",
  };
}

export function variantDraftFromServer(v: Variant): VariantDraft {
  return {
    key: v.id,
    id: v.id,
    // length in the shaper's notation (5'10"); width/thickness as plain inches so nothing is rounded (2.6 ≠ 2 5/8)
    length: v.length_display || decimalToInput(v.length_in),
    width: decimalToInput(v.width_in),
    thickness: decimalToInput(v.thickness_in),
    volume: decimalToInput(v.volume_l),
    material_id: v.material ? String(v.material.id) : "",
    fin_system: v.fin_system || "fcs2",
    fin_setup: v.fin_setup ?? "",
    construction: v.construction ?? "",
    price: decimalToInput(v.price),
    made_to_order_days: v.made_to_order_days === null || v.made_to_order_days === undefined ? "" : String(v.made_to_order_days),
    in_stock_quantity: String(v.items_available_for_sale ?? 0),
    sku_suffix: v.sku_suffix ?? "",
    sku: v.sku,
    version: v.version,
    has_orders: v.has_orders,
    availability: v.availability,
    availability_label: v.availability_label,
    is_active: v.is_active,
  };
}

/** Fields whose change on a variant with orders creates a new version (server SPEC_FIELDS, F10). */
export const SPEC_FIELDS: VariantField[] = ["length", "width", "thickness", "volume", "material_id", "construction", "fin_system", "sku_suffix"];

export function changedVariantFields(draft: VariantDraft, original?: VariantDraft): VariantField[] {
  const fields: VariantField[] = [
    "length",
    "width",
    "thickness",
    "volume",
    "material_id",
    "fin_system",
    "fin_setup",
    "construction",
    "price",
    "made_to_order_days",
    "in_stock_quantity",
    "sku_suffix",
  ];
  if (!original) return fields.filter((f) => draft[f].trim() !== "");
  return fields.filter((f) => draft[f].trim() !== original[f].trim());
}

/** True when saving would create a new version of a variant that already has orders (F10 notice). */
export function willVersion(draft: VariantDraft, original?: VariantDraft): boolean {
  if (!original?.has_orders) return false;
  return changedVariantFields(draft, original).some((f) => SPEC_FIELDS.includes(f));
}

/** Client checks before any request; returns field → message. */
export function validateVariant(draft: VariantDraft): Partial<Record<VariantField, string>> {
  const errors: Partial<Record<VariantField, string>> = {};
  if (!draft.length.trim()) errors.length = "Укажите длину, например 5'10\".";
  if (!draft.width.trim()) errors.width = "Укажите ширину в дюймах, например 20 1/2.";
  if (draft.volume.trim() && (!isNumber(draft.volume) || Number(normalizeNumber(draft.volume)) < 1 || Number(normalizeNumber(draft.volume)) > 300))
    errors.volume = "Объём — число от 1 до 300 л.";
  if (draft.price.trim() && (!isNumber(draft.price) || Number(normalizeNumber(draft.price)) < 0)) errors.price = "Цена — неотрицательное число.";
  if (draft.made_to_order_days.trim() && !/^\d{1,3}$/.test(draft.made_to_order_days.trim()))
    errors.made_to_order_days = "Срок — целое число дней от 0 до 365.";
  else if (draft.made_to_order_days.trim() && Number(draft.made_to_order_days) > 365) errors.made_to_order_days = "Срок — не больше 365 дней.";
  if (draft.in_stock_quantity.trim() && (!/^\d{1,3}$/.test(draft.in_stock_quantity.trim()) || Number(draft.in_stock_quantity) > 100))
    errors.in_stock_quantity = "Количество — от 0 до 100.";
  if (draft.sku_suffix.trim() && !/^[A-Za-z0-9]{1,8}$/.test(draft.sku_suffix.trim()))
    errors.sku_suffix = "Суффикс — до 8 латинских букв и цифр.";
  return errors;
}

/** Payload with only the changed fields (all filled fields for a new variant). */
export function variantInput(draft: VariantDraft, original?: VariantDraft): VariantInput {
  const out: VariantInput = {};
  for (const field of changedVariantFields(draft, original)) {
    const raw = draft[field].trim();
    switch (field) {
      case "length":
      case "width":
      case "thickness":
        out[field] = raw;
        break;
      case "volume":
        out.volume_l = raw ? normalizeNumber(raw) : null;
        break;
      case "material_id":
        out.material_id = raw ? Number(raw) : null;
        break;
      case "price":
        out.price = raw ? normalizeNumber(raw) : null;
        break;
      case "made_to_order_days":
        out.made_to_order_days = raw ? Number(raw) : null;
        break;
      case "in_stock_quantity":
        out.in_stock_quantity = raw ? Number(raw) : 0;
        break;
      case "sku_suffix":
        out.sku_suffix = raw.toUpperCase();
        break;
      case "fin_system":
      case "fin_setup":
      case "construction":
        out[field] = raw;
        break;
    }
  }
  return out;
}

const VARIANT_FIELD_ALIASES: Record<string, VariantField> = {
  length: "length",
  length_in: "length",
  width: "width",
  width_in: "width",
  thickness: "thickness",
  thickness_in: "thickness",
  volume_l: "volume",
  material_id: "material_id",
  construction: "construction",
  fin_system: "fin_system",
  fin_setup: "fin_setup",
  price: "price",
  currency: "price",
  made_to_order_days: "made_to_order_days",
  in_stock_quantity: "in_stock_quantity",
  sku_suffix: "sku_suffix",
};

/** ApiError.fields of a variant request → draft field errors (+ `_form` for the rest). */
export function variantFieldErrors(fields: Record<string, string[]>, message?: string): Partial<Record<VariantField | "_form", string>> {
  const out: Partial<Record<VariantField | "_form", string>> = {};
  for (const [key, messages] of Object.entries(fields)) {
    const name = VARIANT_FIELD_ALIASES[key.replace(/^variants\.\d+\./, "")];
    if (name && messages[0]) out[name] = messages[0];
  }
  if (message && (!Object.keys(out).length || out.sku_suffix)) out._form = message;
  return out;
}

/* ---------------- gallery ---------------- */

export interface GallerySyncPlan {
  /** media ids to attach (POST models/{id}/media) */
  add: string[];
  /** BoardMedia item ids to delete */
  remove: number[];
}

export function planGallerySync(server: BoardMediaItem[], local: Media[]): GallerySyncPlan {
  const serverIds = new Set(server.map((i) => i.media.id));
  const localIds = new Set(local.map((m) => m.id));
  return {
    add: local.filter((m) => !serverIds.has(m.id)).map((m) => m.id),
    remove: server.filter((i) => !localIds.has(i.media.id)).map((i) => i.id),
  };
}

/** BoardMedia ids in the local display order, or null when the server order already matches. */
export function galleryOrder(server: BoardMediaItem[], local: Media[]): number[] | null {
  const byMedia = new Map(server.map((i) => [i.media.id, i.id]));
  const ids = local.map((m) => byMedia.get(m.id)).filter((v): v is number => typeof v === "number");
  const current = [...server].sort((a, b) => a.position - b.position).map((i) => i.id);
  if (ids.length !== current.length) return null;
  return ids.every((id, i) => id === current[i]) ? null : ids;
}

/* ---------------- bulk table (BRD-12) ---------------- */

export interface BulkDraft {
  price: string;
  made_to_order_days: string;
  in_stock_quantity: string;
  is_active: boolean;
}

export type BulkField = keyof BulkDraft;

export function bulkDraftFromRow(row: VariantTableRow): BulkDraft {
  return {
    price: decimalToInput(row.price),
    made_to_order_days: row.made_to_order_days === null || row.made_to_order_days === undefined ? "" : String(row.made_to_order_days),
    in_stock_quantity: String(row.items_available_for_sale ?? 0),
    is_active: row.is_active,
  };
}

export function bulkRowChanges(draft: BulkDraft, original: BulkDraft): Omit<BulkRowInput, "id"> | null {
  const out: Omit<BulkRowInput, "id"> = {};
  if (draft.price.trim() !== original.price.trim()) out.price = draft.price.trim() ? normalizeNumber(draft.price) : null;
  if (draft.made_to_order_days.trim() !== original.made_to_order_days.trim())
    out.made_to_order_days = draft.made_to_order_days.trim() ? Number(draft.made_to_order_days) : null;
  if (draft.in_stock_quantity.trim() !== original.in_stock_quantity.trim())
    out.in_stock_quantity = draft.in_stock_quantity.trim() ? Number(draft.in_stock_quantity) : 0;
  if (draft.is_active !== original.is_active) out.is_active = draft.is_active;
  return Object.keys(out).length ? out : null;
}

export function validateBulkDraft(draft: BulkDraft): Partial<Record<BulkField, string>> {
  const errors: Partial<Record<BulkField, string>> = {};
  if (draft.price.trim() && (!isNumber(draft.price) || Number(normalizeNumber(draft.price)) < 0)) errors.price = "Неотрицательное число";
  if (draft.made_to_order_days.trim() && (!/^\d{1,3}$/.test(draft.made_to_order_days.trim()) || Number(draft.made_to_order_days) > 365))
    errors.made_to_order_days = "0–365 дней";
  if (draft.in_stock_quantity.trim() && (!/^\d{1,3}$/.test(draft.in_stock_quantity.trim()) || Number(draft.in_stock_quantity) > 100))
    errors.in_stock_quantity = "0–100";
  return errors;
}

/** `items.N.field` errors of PATCH variants/bulk → { variantId: { field: message } }; `rows` = ids in sent order. */
export function bulkErrorsByRow(fields: Record<string, string[]>, rows: string[]): { byRow: Record<string, Partial<Record<BulkField | "id" | "_row", string>>>; other: string[] } {
  const byRow: Record<string, Partial<Record<BulkField | "id" | "_row", string>>> = {};
  const other: string[] = [];
  for (const [key, messages] of Object.entries(fields)) {
    const m = /^items\.(\d+)(?:\.(\w+))?$/.exec(key);
    const id = m ? rows[Number(m[1])] : undefined;
    if (!m || !id) {
      if (messages[0]) other.push(messages[0]);
      continue;
    }
    const field = (m[2] ?? "_row") as BulkField | "id" | "_row";
    const name: BulkField | "id" | "_row" = field === ("currency" as string) ? "price" : field;
    byRow[id] = { ...byRow[id], [name]: messages[0] };
  }
  return { byRow, other };
}

/* ---------------- workshop form ---------------- */

export interface WorkshopDraft {
  name: string;
  shaper_code: string;
  short_description: string;
  description: string;
  region_id: string;
  city: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  telegram: string;
  vk: string;
  youtube: string;
  specialization: string;
  services: string[];
  lead_time: string;
  does_repair: boolean;
  repair_note: string;
  experience_since: string;
  logo: Media | null;
  cover: Media | null;
  promo_video: Media | null;
}

export function workshopDraft(w?: Workshop | null): WorkshopDraft {
  const social = w?.social_links ?? {};
  return {
    name: w?.name ?? "",
    shaper_code: w?.shaper_code ?? "",
    short_description: w?.short_description ?? "",
    description: w?.description ?? "",
    region_id: w?.region ? String(w.region.id) : "",
    city: w?.city ?? "",
    address: w?.address ?? "",
    phone: w?.phone ?? "",
    email: w?.email ?? "",
    website: w?.website ?? "",
    telegram: social.telegram ?? "",
    vk: social.vk ?? "",
    youtube: social.youtube ?? "",
    specialization: w?.specialization ?? "",
    services: [...(w?.services ?? [])],
    lead_time: w?.lead_time ?? "",
    does_repair: Boolean(w?.does_repair),
    repair_note: w?.repair_note ?? "",
    experience_since: w?.experience_since ? String(w.experience_since) : "",
    logo: w?.logo ?? null,
    cover: w?.cover ?? null,
    promo_video: w?.promo_video ?? null,
  };
}

export type WorkshopField = keyof WorkshopDraft;

export function validateWorkshop(d: WorkshopDraft, now = new Date()): Partial<Record<WorkshopField, string>> {
  const errors: Partial<Record<WorkshopField, string>> = {};
  if (!d.name.trim()) errors.name = "Укажите название мастерской.";
  else if (d.name.trim().length > 90) errors.name = "Не длиннее 90 символов.";
  if (d.shaper_code.trim() && !/^[A-Za-z0-9]{2,6}$/.test(d.shaper_code.trim()))
    errors.shaper_code = "2–6 латинских букв или цифр, например KBA01.";
  if (d.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email.trim())) errors.email = "Проверьте адрес почты.";
  if (d.website.trim() && !/^https?:\/\/\S+\.\S+/.test(d.website.trim())) errors.website = "Адрес сайта начинается с https://";
  if (d.experience_since.trim()) {
    const year = Number(d.experience_since);
    if (!/^\d{4}$/.test(d.experience_since.trim()) || year < 1950 || year > now.getFullYear())
      errors.experience_since = `Год от 1950 до ${now.getFullYear()}.`;
  }
  return errors;
}

/**
 * PUT me/workshop body. On create — all filled fields; on edit — only what changed. The shaper code (SKU prefix)
 * is sent only when the user actually changed it, so saving the profile never drops or rewrites it (prototype bug).
 */
export function workshopInput(d: WorkshopDraft, initial?: Workshop | null): WorkshopInput {
  const base = workshopDraft(initial);
  const creating = !initial;
  const out: WorkshopInput = {};
  const text = (key: "name" | "short_description" | "description" | "city" | "address" | "phone" | "email" | "website" | "specialization" | "lead_time" | "repair_note") => {
    const value = d[key].trim();
    if (creating ? value !== "" : value !== base[key].trim()) out[key] = value;
  };
  (["name", "short_description", "description", "city", "address", "phone", "email", "website", "specialization", "lead_time", "repair_note"] as const).forEach(text);
  const code = d.shaper_code.trim().toUpperCase();
  if (code && code !== base.shaper_code.trim().toUpperCase()) out.shaper_code = code;
  if (creating ? d.region_id !== "" : d.region_id !== base.region_id) out.region_id = d.region_id ? Number(d.region_id) : null;
  if (creating ? d.experience_since !== "" : d.experience_since.trim() !== base.experience_since)
    out.experience_since = d.experience_since.trim() ? Number(d.experience_since) : null;
  const services = d.services.map((s) => s.trim()).filter(Boolean);
  if (creating ? services.length > 0 : services.join("\n") !== base.services.join("\n")) out.services = services;
  if (creating ? d.does_repair : d.does_repair !== base.does_repair) out.does_repair = d.does_repair;
  const social: Record<string, string> = {};
  for (const key of ["telegram", "vk", "youtube"] as const) if (d[key].trim()) social[key] = d[key].trim();
  const baseSocial = { telegram: base.telegram, vk: base.vk, youtube: base.youtube };
  if (creating ? Object.keys(social).length > 0 : (["telegram", "vk", "youtube"] as const).some((k) => d[k].trim() !== baseSocial[k].trim()))
    out.social_links = { ...(initial?.social_links ?? {}), ...social, ...Object.fromEntries((["telegram", "vk", "youtube"] as const).filter((k) => !d[k].trim()).map((k) => [k, ""])) };
  const media = (key: "logo" | "cover" | "promo_video", field: "logo_id" | "cover_id" | "promo_video_id") => {
    const now = d[key]?.id ?? null;
    const was = base[key]?.id ?? null;
    if (now !== was) out[field] = now;
  };
  media("logo", "logo_id");
  media("cover", "cover_id");
  media("promo_video", "promo_video_id");
  return out;
}

const WORKSHOP_FIELD_ALIASES: Record<string, WorkshopField> = {
  region_id: "region_id",
  region: "region_id",
  logo_id: "logo",
  cover_id: "cover",
  promo_video_id: "promo_video",
  social_links: "telegram",
};

export function workshopFieldErrors(fields: Record<string, string[]>): Partial<Record<WorkshopField, string>> {
  const out: Partial<Record<WorkshopField, string>> = {};
  for (const [key, messages] of Object.entries(fields)) {
    const name = (WORKSHOP_FIELD_ALIASES[key] ?? key) as WorkshopField;
    if (messages[0]) out[name] = messages[0];
  }
  return out;
}
