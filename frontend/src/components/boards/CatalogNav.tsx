"use client";
/**
 * URL-driven catalogue filters (FRONTEND_GUIDE §3): the server page renders the list from `searchParams`;
 * filter islands only rewrite the query string with `router.replace` inside a transition, so the previous
 * results stay visible (dimmed, aria-busy) until the new server render arrives. Links stay shareable and indexable.
 *
 *   <CatalogNavProvider>
 *     <MyFilters />                      // const nav = useCatalogNav(); nav.setParams({ region: "krym" })
 *     <CatalogPending>{serverList}</CatalogPending>
 *   </CatalogNavProvider>
 */
import { createContext, useCallback, useContext, useMemo, useTransition, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { cx } from "@/lib/cx";

export type ParamUpdates = Record<string, string | number | boolean | null | undefined>;

interface CatalogNavValue {
  isPending: boolean;
  params: URLSearchParams;
  /** Set (or with null/"" delete) query params; resets `page` unless it is part of the update. */
  setParams: (updates: ParamUpdates, options?: { keepPage?: boolean }) => void;
  /** Drop every param except the listed ones (e.g. keep `tab`). */
  reset: (keep?: string[]) => void;
  hrefWith: (updates: ParamUpdates) => string;
}

const CatalogNavContext = createContext<CatalogNavValue | null>(null);

export function applyParamUpdates(current: URLSearchParams, updates: ParamUpdates, keepPage = false): URLSearchParams {
  const next = new URLSearchParams(current.toString());
  for (const [key, value] of Object.entries(updates)) {
    if (value === null || value === undefined || value === "" || value === false) next.delete(key);
    else next.set(key, String(value));
  }
  if (!keepPage && !("page" in updates)) next.delete("page");
  return next;
}

function toHref(pathname: string, params: URLSearchParams): string {
  const qs = params.toString();
  return qs ? `${pathname}?${qs}` : pathname;
}

export function CatalogNavProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const params = useMemo(() => new URLSearchParams(searchParams?.toString() ?? ""), [searchParams]);

  const go = useCallback(
    (next: URLSearchParams) => {
      startTransition(() => router.replace(toHref(pathname, next), { scroll: false }));
    },
    [pathname, router],
  );

  const value = useMemo<CatalogNavValue>(
    () => ({
      isPending,
      params,
      setParams: (updates, options) => go(applyParamUpdates(params, updates, options?.keepPage)),
      reset: (keep = []) => {
        const next = new URLSearchParams();
        keep.forEach((k) => {
          const v = params.get(k);
          if (v) next.set(k, v);
        });
        go(next);
      },
      hrefWith: (updates) => toHref(pathname, applyParamUpdates(params, updates)),
    }),
    [go, isPending, params, pathname],
  );

  return <CatalogNavContext.Provider value={value}>{children}</CatalogNavContext.Provider>;
}

export function useCatalogNav(): CatalogNavValue {
  const ctx = useContext(CatalogNavContext);
  if (!ctx) throw new Error("useCatalogNav() must be used inside <CatalogNavProvider>");
  return ctx;
}

/** Wraps server-rendered results: dims them and sets aria-busy while new filters are loading. */
export function CatalogPending({ children, className, label = "Обновляем результаты…" }: { children: ReactNode; className?: string; label?: string }) {
  const { isPending } = useCatalogNav();
  return (
    <div className={cx("gv-catalog-results", isPending && "is-pending", className)} aria-busy={isPending || undefined}>
      <p className="sr-only" role="status" aria-live="polite">
        {isPending ? label : ""}
      </p>
      {children}
    </div>
  );
}
