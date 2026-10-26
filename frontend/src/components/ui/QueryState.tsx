"use client";
import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { isApiError } from "@/lib/api/errors";
import { EmptyState, ErrorState, LoadingState, NoAccess } from "./States";

/**
 * Renders the right state for a TanStack query so pages don't repeat the same branches:
 *
 *   <QueryState query={q} isEmpty={(d) => d.results.length === 0}
 *     empty={<EmptyState compact title="Обращений пока нет" />}>
 *     {(data) => <InquiryList items={data.results} />}
 *   </QueryState>
 *
 * - first load → LoadingState (skeleton by default)
 * - 403 → NoAccess, other errors → ErrorState with «Повторить» (refetch)
 * - background refetch errors keep showing cached data (no flicker)
 */
export function QueryState<T>({
  query,
  children,
  isEmpty,
  empty,
  loading,
  errorTitle,
}: {
  query: Pick<UseQueryResult<T>, "data" | "error" | "isPending" | "isError" | "refetch">;
  children: (data: T) => ReactNode;
  isEmpty?: (data: T) => boolean;
  empty?: ReactNode;
  loading?: ReactNode;
  errorTitle?: string;
}) {
  if (query.isPending) return <>{loading ?? <LoadingState variant="skeleton" />}</>;
  if (query.isError && query.data === undefined) {
    if (isApiError(query.error) && query.error.isForbidden) return <NoAccess />;
    return <ErrorState error={query.error} title={errorTitle} onRetry={() => void query.refetch()} />;
  }
  const data = query.data as T;
  if (isEmpty?.(data)) return <>{empty ?? <EmptyState compact title="Здесь пока пусто" />}</>;
  return <>{children(data)}</>;
}
