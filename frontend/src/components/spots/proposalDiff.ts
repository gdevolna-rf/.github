/**
 * «Было → предлагается» for spot proposals (SPT-07/08, TZ 8.1): current values from the spot detail, the form
 * draft, normalisation identical to the backend (apps/spots/services/proposals.normalize_value: trimmed text,
 * compass/hazard lists in dictionary order, sorted months, infrastructure rows) and human-readable values.
 */
import type {
  EditableSpotField,
  InfrastructureInput,
  ProposalValue,
  SpotDetail,
  SpotDictionaries,
} from "@/lib/api/spots";
import { COMPASS, COMPASS_POINTS } from "@/lib/labels";
import type { CompassPoint } from "@/lib/api/types";

export type DraftValue = string | string[] | InfrastructureInput[];
export type Draft = Partial<Record<EditableSpotField, DraftValue>>;

export const TEXT_FIELDS: EditableSpotField[] = [
  "short_description",
  "description",
  "wave_character",
  "wave_power",
  "season",
  "best_tide",
  "typical_conditions",
  "hazard_notes",
  "entry_exit",
  "access",
  "water_temp_note",
  "seasonal_warning",
];
export const CHOICE_FIELDS: EditableSpotField[] = ["difficulty", "bottom_type", "break_type"];
export const LIST_FIELDS: EditableSpotField[] = ["best_wind_directions", "best_swell_directions", "hazards", "best_months"];

/** Current value of a field in the same shape as the draft. */
export function currentValue(spot: SpotDetail, field: EditableSpotField): DraftValue {
  switch (field) {
    case "difficulty":
    case "bottom_type":
    case "break_type":
      return spot[field]?.code ?? "";
    case "best_wind_directions":
    case "best_swell_directions":
      return (spot[field] ?? []).map((c) => c.code);
    case "hazards":
      return (spot.hazards ?? []).map((h) => h.code);
    case "best_months":
      return (spot.best_months ?? []).map((m) => String(m.code));
    case "infrastructure":
      return (spot.infrastructure ?? []).map((i) => ({ type: i.type, name: i.name ?? "", distance_m: i.distance_m ?? null }));
    default:
      return (spot[field] as string | null | undefined) ?? "";
  }
}

export function initialDraft(spot: SpotDetail, fields: EditableSpotField[]): Draft {
  const draft: Draft = {};
  for (const f of fields) draft[f] = currentValue(spot, f);
  return draft;
}

function orderBy<T extends string>(values: T[], order: readonly string[]): T[] {
  const uniq = Array.from(new Set(values));
  return uniq.filter((v) => order.includes(v)).sort((a, b) => order.indexOf(a) - order.indexOf(b));
}

/** Value as it will be sent / compared (backend normalisation). */
export function normalize(field: EditableSpotField, value: DraftValue | undefined, dicts?: Pick<SpotDictionaries, "hazards">): ProposalValue {
  if (field === "best_wind_directions" || field === "best_swell_directions") {
    return orderBy((value as string[]) ?? [], COMPASS_POINTS);
  }
  if (field === "hazards") {
    const order = dicts?.hazards?.map((h) => h.code) ?? [];
    const list = Array.from(new Set((value as string[]) ?? []));
    return order.length ? orderBy(list, order) : list.sort();
  }
  if (field === "best_months") {
    return Array.from(new Set(((value as string[]) ?? []).map(Number).filter((n) => n >= 1 && n <= 12))).sort((a, b) => a - b);
  }
  if (field === "infrastructure") {
    return ((value as InfrastructureInput[]) ?? [])
      .map((row) => ({
        type: row.type || "other",
        name: (row.name ?? "").trim(),
        distance_m: row.distance_m === null || row.distance_m === undefined || Number.isNaN(row.distance_m) ? null : Math.round(row.distance_m),
      }))
      .filter((row) => row.type !== "other" || row.name || row.distance_m !== null);
  }
  if (CHOICE_FIELDS.includes(field)) return ((value as string) ?? "") || null;
  return ((value as string) ?? "").trim();
}

const same = (a: ProposalValue, b: ProposalValue) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

/** Only the fields that differ from the published card, normalised. */
export function buildChanges(
  spot: SpotDetail,
  draft: Draft,
  dicts?: Pick<SpotDictionaries, "hazards">,
): Partial<Record<EditableSpotField, ProposalValue>> {
  const out: Partial<Record<EditableSpotField, ProposalValue>> = {};
  for (const [field, value] of Object.entries(draft) as Array<[EditableSpotField, DraftValue]>) {
    const next = normalize(field, value, dicts);
    const now = normalize(field, currentValue(spot, field), dicts);
    // choice fields cannot be cleared (the backend requires a value)
    if (CHOICE_FIELDS.includes(field) && next === null) continue;
    if (!same(next, now)) out[field] = next;
  }
  return out;
}

/** Human-readable value for the diff preview (mirrors backend display_value). */
export function displayValue(field: EditableSpotField, value: ProposalValue, dicts?: SpotDictionaries | null): string {
  if (value === null || value === "" || (Array.isArray(value) && value.length === 0)) return "—";
  const label = (list: Array<{ code: string | number; label: string }> | undefined, code: string | number) =>
    list?.find((c) => String(c.code) === String(code))?.label ?? String(code);
  switch (field) {
    case "difficulty":
      return label(dicts?.difficulty, value as string);
    case "bottom_type":
      return label(dicts?.bottom_type, value as string);
    case "break_type":
      return label(dicts?.break_type, value as string);
    case "best_wind_directions":
    case "best_swell_directions":
      return (value as string[]).map((c) => COMPASS[c as CompassPoint]?.name ?? c).join(", ");
    case "best_months":
      return (value as number[]).map((m) => label(dicts?.months, m)).join(", ");
    case "hazards":
      return (value as string[]).map((c) => label(dicts?.hazards, c)).join(", ");
    case "infrastructure":
      return (value as InfrastructureInput[])
        .map((row) => {
          let text = label(dicts?.infrastructure_types, row.type);
          if (row.name) text += ` «${row.name}»`;
          if (row.distance_m !== null && row.distance_m !== undefined) text += ` — ${row.distance_m} м`;
          return text;
        })
        .join("; ");
    default:
      return String(value);
  }
}
