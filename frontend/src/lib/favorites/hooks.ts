"use client";
/**
 * Favorites (MSG-11, ATX-11): ids of everything the user saved, loaded once (GET /me/favorites/ids) and
 * shared by every HeartButton; toggling is optimistic with rollback on error.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { favoriteKey, favoritesApi, type FavoriteKey } from "@/lib/api/favorites";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import type { FavoriteTargetType } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";

const EMPTY = new Set<FavoriteKey>();

export function useFavoriteIds() {
  const { me } = useMe();
  const query = useQuery({
    queryKey: qk.favoriteIds,
    queryFn: async () => {
      try {
        return await favoritesApi.ids();
      } catch (err) {
        if (isApiError(err) && (err.status === 404 || err.status === 405)) return new Set<FavoriteKey>();
        throw err;
      }
    },
    enabled: Boolean(me),
    staleTime: 5 * 60_000,
  });
  return { ids: me ? (query.data ?? EMPTY) : EMPTY, isLoading: Boolean(me) && query.isPending };
}

export function useFavoritesCount(): number {
  return useFavoriteIds().ids.size;
}

export function useIsFavorite(type: FavoriteTargetType, id: string | number): boolean {
  return useFavoriteIds().ids.has(favoriteKey(type, id));
}

export interface ToggleFavoriteVars {
  type: FavoriteTargetType;
  id: string | number;
  /** desired state */
  on: boolean;
}

export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ type, id, on }: ToggleFavoriteVars) => {
      if (on) await favoritesApi.add(type, id);
      else await favoritesApi.remove(type, id);
    },
    onMutate: async ({ type, id, on }) => {
      await queryClient.cancelQueries({ queryKey: qk.favoriteIds });
      const previous = queryClient.getQueryData<Set<FavoriteKey>>(qk.favoriteIds);
      const next = new Set(previous ?? []);
      const key = favoriteKey(type, id);
      if (on) next.add(key);
      else next.delete(key);
      queryClient.setQueryData(qk.favoriteIds, next);
      return { previous };
    },
    onError: (_err, _vars, context) => {
      queryClient.setQueryData(qk.favoriteIds, context?.previous ?? new Set());
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["me", "favorites", "list"] });
    },
  });
}
