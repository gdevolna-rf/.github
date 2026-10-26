"use client";
/**
 * Auth state for Client Components.
 *   const { me, isGuest, isLoading } = useMe();
 * `me === null` → guest (GET /me answered 401/403), `undefined` while loading.
 */
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { authApi, normalizeMe, type LoginPayload, type Me, type RegisterPayload } from "@/lib/api/auth";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import type { Counters } from "@/lib/api/types";

export async function fetchMe(): Promise<Me | null> {
  try {
    return await authApi.me();
  } catch (err) {
    // 401/403 = not logged in. 404/405 = /me not deployed yet on this backend → behave as guest.
    if (isApiError(err) && (err.isUnauthenticated || err.status === 401 || err.status === 403 || err.status === 404 || err.status === 405)) {
      return null;
    }
    throw err;
  }
}

export function useMe() {
  const query = useQuery({
    queryKey: qk.me,
    queryFn: fetchMe,
    staleTime: 60_000,
    // the API client already retried network/5xx errors for this GET
    retry: false,
  });
  const me = query.data;
  return {
    me: me ?? null,
    /** true only when the server said "not logged in" */
    isGuest: me === null,
    isAuthenticated: Boolean(me),
    /** first load (no data yet) */
    isLoading: query.isPending,
    /** could not determine (network/5xx) and no cached value */
    isError: query.isError && me === undefined,
    error: query.error,
    refetch: query.refetch,
  };
}

export const ZERO_COUNTERS: Counters = { unread_messages: 0, unread_notifications: 0, new_inquiries: 0, pending_bookings: 0 };

/** Badge counters (MSG-06/07). Kept fresh by the realtime bridge; polled every minute as a fallback. */
export function useCounters() {
  const { me } = useMe();
  const query = useQuery({
    queryKey: qk.counters,
    queryFn: async () => {
      try {
        return { ...ZERO_COUNTERS, ...(await authApi.counters()) };
      } catch (err) {
        if (isApiError(err) && (err.status === 404 || err.status === 405)) return ZERO_COUNTERS;
        throw err;
      }
    },
    enabled: Boolean(me),
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });
  return me ? (query.data ?? ZERO_COUNTERS) : ZERO_COUNTERS;
}

/** Drop everything user-specific (logout, session expired). */
export function resetPrivateData(queryClient: QueryClient) {
  queryClient.removeQueries({
    predicate: (q) => {
      const head = q.queryKey[0];
      return head !== "public";
    },
  });
  queryClient.setQueryData(qk.me, null);
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: LoginPayload) => {
      const res = await authApi.login(payload);
      // login may answer with the /me payload; otherwise fetch it
      if (res && typeof res === "object" && "id" in res && "email" in res) {
        const me = normalizeMe(res);
        queryClient.setQueryData(qk.me, me);
        return me;
      }
      return queryClient.fetchQuery({ queryKey: qk.me, queryFn: fetchMe, staleTime: 0 });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"], refetchType: "active" });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      try {
        await authApi.logout();
      } catch (err) {
        if (!(isApiError(err) && (err.status === 401 || err.status === 403))) throw err;
      }
    },
    onSuccess: () => resetPrivateData(queryClient),
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: RegisterPayload) => {
      // register logs the user in and returns the /me payload + next_step
      const result = (await authApi.register(payload)) ?? {};
      let me: Me | null;
      if ("id" in result && "email" in result) {
        me = normalizeMe(result);
        queryClient.setQueryData(qk.me, me);
      } else {
        me = await queryClient.fetchQuery({ queryKey: qk.me, queryFn: fetchMe, staleTime: 0 });
      }
      return { result, me };
    },
  });
}
