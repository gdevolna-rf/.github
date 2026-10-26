/**
 * Pure helpers of the /search page (NAV-04): query normalisation, the type filter and which groups to show.
 * Kept free of React so the rules are unit-tested.
 */
import {
  isSearchType,
  SEARCH_MAX_QUERY,
  SEARCH_MIN_QUERY,
  SEARCH_TYPES,
  type SearchGroup,
  type SearchResponse,
  type SearchType,
} from "@/lib/api/search";
import { routes } from "@/lib/routes";

export type QueryState = "empty" | "short" | "ok";

/** Collapse whitespace and cut to the server maximum (the backend does the same). */
export function normalizeQuery(raw: string | string[] | undefined | null): string {
  const value = Array.isArray(raw) ? (raw[0] ?? "") : (raw ?? "");
  return value.split(/\s+/).filter(Boolean).join(" ").slice(0, SEARCH_MAX_QUERY);
}

export function queryState(q: string): QueryState {
  if (!q) return "empty";
  return q.length < SEARCH_MIN_QUERY ? "short" : "ok";
}

/** `?types=` accepts one type here (the filter chips); unknown values are ignored. */
export function parseType(raw: string | string[] | undefined | null): SearchType | null {
  const value = Array.isArray(raw) ? raw[0] : raw;
  const first = (value ?? "").split(",")[0]?.trim().toLowerCase();
  return isSearchType(first) ? first : null;
}

/** /search?q=…[&types=…] */
export function searchHref(q: string, type?: SearchType | null): string {
  const base = routes.search(q);
  return type ? `${base}${base.includes("?") ? "&" : "?"}types=${encodeURIComponent(type)}` : base;
}

export interface TypeChip {
  type: SearchType | null;
  label: string;
  total: number;
  href: string;
  active: boolean;
}

/** «Все» + one chip per known type with its total (from the all-types response). */
export function typeChips(all: SearchResponse | null, q: string, active: SearchType | null): TypeChip[] {
  const totals = new Map<SearchType, SearchGroup>();
  for (const g of all?.groups ?? []) totals.set(g.type, g);
  const chips: TypeChip[] = SEARCH_TYPES.map(({ type, label }) => ({
    type,
    label: totals.get(type)?.label || label,
    total: totals.get(type)?.total ?? 0,
    href: searchHref(q, type),
    active: active === type,
  }));
  const sum = chips.reduce((n, c) => n + c.total, 0);
  return [{ type: null, label: "Все", total: sum, href: searchHref(q), active: active === null }, ...chips];
}

/**
 * Groups to render: with a type filter — only that group (from the detailed response when available);
 * without — every non-empty group in the canonical order.
 */
export function visibleGroups(all: SearchResponse | null, one: SearchResponse | null, active: SearchType | null): SearchGroup[] {
  const order = (g: SearchGroup) => SEARCH_TYPES.findIndex((t) => t.type === g.type);
  if (active) {
    const group = one?.groups.find((g) => g.type === active) ?? all?.groups.find((g) => g.type === active);
    return group && group.total > 0 ? [group] : [];
  }
  return [...(all?.groups ?? [])].filter((g) => g.total > 0 && g.results.length > 0).sort((a, b) => order(a) - order(b));
}

/** How many results are not shown in the group (→ «Показать ещё (N)»). */
export function hiddenCount(group: SearchGroup): number {
  return Math.max(0, group.total - group.results.length);
}

export function totalResults(all: SearchResponse | null): number {
  return (all?.groups ?? []).reduce((n, g) => n + g.total, 0);
}
