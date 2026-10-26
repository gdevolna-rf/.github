/**
 * Shallow before/after diff of audit JSON (DATA-09): one row per top-level key of either side.
 * Nested values are compared structurally (key order does not matter) and printed as pretty JSON.
 */

export type DiffChange = "added" | "removed" | "changed" | "same";

export interface DiffRow {
  key: string;
  before: unknown;
  after: unknown;
  change: DiffChange;
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** Structural equality for JSON values. */
export function jsonEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((v, i) => jsonEqual(v, b[i]));
  if (isPlainObject(a) && isPlainObject(b)) {
    const ka = Object.keys(a);
    const kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => Object.prototype.hasOwnProperty.call(b, k) && jsonEqual(a[k], b[k]));
  }
  return false;
}

/**
 * Objects → per-key rows (keys in first-seen order: before, then new keys of after).
 * Non-object sides (null, scalars, arrays) → a single row with key "".
 */
export function diffJson(before: unknown, after: unknown): DiffRow[] {
  const b = before ?? null;
  const a = after ?? null;
  if (b === null && a === null) return [];
  if (!(isPlainObject(b) || b === null) || !(isPlainObject(a) || a === null)) {
    return [{ key: "", before: b, after: a, change: jsonEqual(b, a) ? "same" : b === null ? "added" : a === null ? "removed" : "changed" }];
  }
  const bo = (b ?? {}) as Record<string, unknown>;
  const ao = (a ?? {}) as Record<string, unknown>;
  const keys = [...Object.keys(bo), ...Object.keys(ao).filter((k) => !(k in bo))];
  return keys.map((key) => {
    const inB = key in bo;
    const inA = key in ao;
    const change: DiffChange = !inB ? "added" : !inA ? "removed" : jsonEqual(bo[key], ao[key]) ? "same" : "changed";
    return { key, before: inB ? bo[key] : undefined, after: inA ? ao[key] : undefined, change };
  });
}

/** Printable value: strings as-is, everything else as indented JSON; undefined → "—". */
export function formatJsonValue(v: unknown): string {
  if (v === undefined) return "—";
  if (typeof v === "string") return v === "" ? "«»" : v;
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}
