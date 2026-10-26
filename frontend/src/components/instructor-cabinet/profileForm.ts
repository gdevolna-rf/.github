/**
 * Instructor card form (INS-01/02): state ⇄ API payload, client validation (Zod) mirroring
 * InstructorProfileWriteSerializer, and the publication checklist wording (ACC-15).
 */
import { z } from "zod";
import type { InstructorOwn, InstructorProfileInput } from "@/lib/api/instructorCabinet";
import type { FormErrors } from "@/lib/forms";
import { routes } from "@/lib/routes";

export const MAX_FUN_FACTS = 5;

export interface ProfileForm {
  headline: string;
  about: string;
  fun_facts: string[];
  regions: string[];
  spots: string[];
  surfing_since: string;
  teaching_since: string;
  riding_level: string;
  formats: string[];
  student_levels: string[];
  board_types: string[];
  languages: string[];
  price_from: string;
  currency: string;
  contact_note: string;
}

export const EMPTY_FORM: ProfileForm = {
  headline: "",
  about: "",
  fun_facts: [""],
  regions: [],
  spots: [],
  surfing_since: "",
  teaching_since: "",
  riding_level: "",
  formats: [],
  student_levels: [],
  board_types: [],
  languages: ["ru"],
  price_from: "",
  currency: "RUB",
  contact_note: "",
};

const money = (v: string | null | undefined) => {
  if (v === null || v === undefined || v === "") return "";
  const n = Number(v);
  return Number.isFinite(n) ? String(Number.isInteger(n) ? n : n.toFixed(2)) : "";
};

export function profileToForm(p: InstructorOwn | null | undefined, defaults: { regionSlug?: string | null } = {}): ProfileForm {
  if (!p) return { ...EMPTY_FORM, regions: defaults.regionSlug ? [defaults.regionSlug] : [] };
  return {
    headline: p.headline ?? "",
    about: p.about ?? "",
    fun_facts: p.fun_facts?.length ? [...p.fun_facts] : [""],
    regions: (p.regions ?? []).map((r) => r.slug),
    spots: (p.spots ?? []).map((s) => s.slug),
    surfing_since: p.surfing_since ? String(p.surfing_since) : "",
    teaching_since: p.teaching_since ? String(p.teaching_since) : "",
    riding_level: p.riding_level ?? "",
    formats: [...(p.formats ?? [])],
    student_levels: [...(p.student_levels ?? [])],
    board_types: [...(p.board_types ?? [])],
    languages: [...(p.languages ?? [])],
    price_from: money(p.price_from),
    currency: p.currency || "RUB",
    contact_note: p.contact_note ?? "",
  };
}

const year = (label: string) =>
  z
    .string()
    .trim()
    .refine((v) => v === "" || (/^\d{4}$/.test(v) && Number(v) >= 1940 && Number(v) <= new Date().getFullYear()), `${label}: год от 1940 до текущего`);

export const profileSchema = z
  .object({
    headline: z.string().max(200, "Не длиннее 200 символов"),
    about: z.string().max(4000, "Не длиннее 4000 символов"),
    fun_facts: z.array(z.string().max(200, "Факт — не длиннее 200 символов")).max(MAX_FUN_FACTS),
    regions: z.array(z.string()).max(20, "Не больше 20 регионов"),
    spots: z.array(z.string()).max(50, "Не больше 50 спотов"),
    surfing_since: year("Катаетесь с"),
    teaching_since: year("Преподаёте с"),
    riding_level: z.string(),
    formats: z.array(z.string()),
    student_levels: z.array(z.string()),
    board_types: z.array(z.string()),
    languages: z.array(z.string()),
    price_from: z
      .string()
      .trim()
      .refine((v) => v === "" || (/^\d+([.,]\d{1,2})?$/.test(v) && Number(v.replace(",", ".")) >= 0), "Укажите сумму числом, например 3500"),
    currency: z.string().regex(/^[A-Z]{3}$/),
    contact_note: z.string().max(300, "Не длиннее 300 символов"),
  })
  .refine((v) => !v.surfing_since || !v.teaching_since || Number(v.teaching_since) >= Number(v.surfing_since), {
    message: "Преподавание не может начаться раньше катания",
    path: ["teaching_since"],
  });

export function formToInput(f: ProfileForm): InstructorProfileInput {
  return {
    headline: f.headline.trim(),
    about: f.about.trim(),
    fun_facts: f.fun_facts.map((x) => x.trim()).filter(Boolean),
    region_slugs: f.regions,
    spot_slugs: f.spots,
    surfing_since: f.surfing_since ? Number(f.surfing_since) : null,
    teaching_since: f.teaching_since ? Number(f.teaching_since) : null,
    riding_level: f.riding_level,
    formats: f.formats,
    student_levels: f.student_levels,
    board_types: f.board_types,
    languages: f.languages,
    price_from: f.price_from.trim() ? f.price_from.trim().replace(",", ".") : null,
    currency: f.currency,
    contact_note: f.contact_note.trim(),
  };
}

/** Server field names → form field names (errors and the checklist). */
export const FIELD_ALIASES: Record<string, string> = { region_slugs: "regions", spot_slugs: "spots" };

/** Publication checklist (ACC-15): what to fill and where. The certificate is NOT required (F03, ATX-04). */
export const CHECKLIST: Record<string, { label: string; href?: string; field?: keyof ProfileForm }> = {
  name: { label: "Имя и фамилия в общем профиле", href: routes.account.profile },
  headline: { label: "Короткое описание или раздел «О себе»", field: "headline" },
  region_slugs: { label: "Хотя бы один регион занятий", field: "regions" },
  formats: { label: "Хотя бы один формат занятий", field: "formats" },
  price_from: { label: "Цена «от» или активное предложение", field: "price_from" },
  email: { label: "Подтверждённый email", href: routes.account.settings },
};

export interface ChecklistItem {
  key: string;
  label: string;
  message: string;
  href?: string;
  field?: keyof ProfileForm;
}

export function checklistItems(missing: Record<string, string | string[]> | null | undefined): ChecklistItem[] {
  return Object.entries(missing ?? {}).map(([key, value]) => {
    const def = CHECKLIST[key];
    const message = Array.isArray(value) ? value[0] ?? "" : value;
    return { key, label: def?.label ?? message, message, href: def?.href, field: def?.field };
  });
}

/** Years of teaching for the preview (display only). */
export function experienceYears(f: Pick<ProfileForm, "teaching_since" | "surfing_since">, now = new Date()): number | null {
  const since = Number(f.teaching_since || f.surfing_since);
  if (!since) return null;
  return Math.max(0, now.getFullYear() - since);
}

export function isSameForm(a: ProfileForm, b: ProfileForm): boolean {
  return JSON.stringify(formToInput(a)) === JSON.stringify(formToInput(b));
}

export type ProfileErrors = FormErrors<keyof ProfileForm>;
