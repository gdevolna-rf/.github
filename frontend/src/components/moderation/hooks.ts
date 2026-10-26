"use client";
/**
 * Moderation data hooks. The API answers 403 when the staff session lost its 2FA mark (or the role was revoked)
 * and 401/403 not_authenticated when the session expired — in both cases we re-read `/me`, so the gate
 * (TwoFactorGate / RequireAuth) shows the TOTP prompt or the login redirect instead of a dead screen.
 */
import { useQuery, useQueryClient, type QueryKey, type UseQueryOptions } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";

export function useRecheckSessionOnError(error: unknown) {
  const queryClient = useQueryClient();
  const last = useRef<unknown>(null);
  useEffect(() => {
    if (!error || error === last.current) return;
    last.current = error;
    if (isApiError(error) && (error.status === 403 || error.isUnauthenticated)) {
      void queryClient.invalidateQueries({ queryKey: qk.me, exact: true });
    }
  }, [error, queryClient]);
}

/** useQuery + session re-check on 401/403. */
export function useModQuery<T>(options: UseQueryOptions<T, Error, T, QueryKey>) {
  const query = useQuery(options);
  useRecheckSessionOnError(query.error);
  return query;
}
