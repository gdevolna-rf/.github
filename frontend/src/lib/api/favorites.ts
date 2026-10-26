/** favorites: GET /me/favorites/ids, GET /me/favorites?type=, POST /favorites, DELETE /favorites/{type}/{id}. */
import { api } from "./client";
import type { FavoriteTargetType, Paginated } from "./types";

export type FavoriteKey = `${FavoriteTargetType}:${string}`;

export const favoriteKey = (type: FavoriteTargetType, id: string | number): FavoriteKey => `${type}:${String(id)}`;

/**
 * `/me/favorites/ids` may come as `{spot: [ids], instructor: [ids]…}`, as `[{target_type, target_id}]`,
 * or as `["spot:<id>", …]`; all of them become a Set of `type:id` keys.
 */
export function normalizeFavoriteIds(data: unknown): Set<FavoriteKey> {
  const out = new Set<FavoriteKey>();
  if (Array.isArray(data)) {
    for (const item of data) {
      if (typeof item === "string" && item.includes(":")) out.add(item as FavoriteKey);
      else if (item && typeof item === "object") {
        const o = item as Record<string, unknown>;
        if (o.target_type && o.target_id != null) out.add(favoriteKey(o.target_type as FavoriteTargetType, String(o.target_id)));
      }
    }
  } else if (data && typeof data === "object") {
    const o = data as Record<string, unknown>;
    const source = (o.results ?? o.ids ?? o) as Record<string, unknown>;
    if (Array.isArray(source)) return normalizeFavoriteIds(source);
    for (const [type, ids] of Object.entries(source)) {
      if (Array.isArray(ids)) ids.forEach((id) => out.add(favoriteKey(type as FavoriteTargetType, String(id))));
    }
  }
  return out;
}

export interface FavoriteItem {
  id: string | number;
  target_type: FavoriteTargetType;
  target_id: string;
  created_at: string;
  /** Card payload of the target (spot, instructor, organization…) — shape depends on target_type. */
  target?: Record<string, unknown>;
}

export const favoritesApi = {
  ids: () => api.get<unknown>("me/favorites/ids").then(normalizeFavoriteIds),
  list: (type?: FavoriteTargetType, page = 1) =>
    api.get<Paginated<FavoriteItem>>("me/favorites", { query: { type, page } }),
  add: (type: FavoriteTargetType, id: string | number) =>
    api.post<unknown>("favorites", { target_type: type, target_id: String(id) }),
  remove: (type: FavoriteTargetType, id: string | number) =>
    api.delete(`favorites/${encodeURIComponent(type)}/${encodeURIComponent(String(id))}`),
};
