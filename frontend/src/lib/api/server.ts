/**
 * Server-side fetch for Server Components, route handlers, sitemap and metadata.
 * Talks to Django directly (`INTERNAL_API_URL`, http://backend:8000 in docker) — never through nginx.
 *
 * Public catalogue data is cached with ISR: `next: { revalidate }` (default 300 s) + optional tags,
 * so `revalidateTag("spots")` can refresh it on demand. Authenticated data must NOT be fetched here
 * (no cookies are forwarded); use the browser client + TanStack Query in Client Components instead.
 */
import { ApiError, networkError, parseApiError, timeoutError } from "./errors";
import { buildQuery, type Query } from "./client";
import type { Paginated } from "./types";

export const INTERNAL_API_URL = (process.env.INTERNAL_API_URL || "http://backend:8000").replace(/\/+$/, "");

export interface ServerFetchOptions {
  query?: Query;
  /** Seconds of ISR caching; `false` = never cache (cache: "no-store"). Default 300. */
  revalidate?: number | false;
  tags?: string[];
  /** Abort after this many ms (the page falls back gracefully). Default 5000. */
  timeoutMs?: number;
  headers?: Record<string, string>;
}

function assertServer() {
  if (typeof window !== "undefined") {
    throw new Error("src/lib/api/server.ts is server-only; use src/lib/api/client.ts in the browser");
  }
}

export function serverApiUrl(path: string, query?: Query): string {
  const clean = path.replace(/^\/+/, "").replace(/^api\/v1\//, "");
  const qs = buildQuery(query);
  return `${INTERNAL_API_URL}/api/v1/${clean}${qs ? `?${qs}` : ""}`;
}

/** GET a public endpoint. Throws ApiError (status 0 + code "network"/"timeout" when the API is down). */
export async function serverFetch<T>(path: string, options: ServerFetchOptions = {}): Promise<T> {
  assertServer();
  const { revalidate = 300, tags, timeoutMs = 5000, query, headers } = options;
  const url = /^https?:\/\//.test(path) ? toInternal(path) : serverApiUrl(path, query);
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { Accept: "application/json", ...headers },
      signal: controller.signal,
      ...(revalidate === false ? { cache: "no-store" as const } : { next: { revalidate, tags } }),
    });
  } catch {
    throw timedOut ? timeoutError() : networkError();
  } finally {
    clearTimeout(timer);
  }
  const text = await res.text().catch(() => "");
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) throw parseApiError(res.status, body, res.headers.get("X-Request-ID"));
  return body as T;
}

/**
 * Same as serverFetch but never throws: returns `null` when the API is unavailable or the endpoint is not
 * implemented yet (404/405/5xx). Use for optional blocks (home teasers) so the page still renders.
 */
export async function serverFetchSafe<T>(path: string, options: ServerFetchOptions = {}): Promise<T | null> {
  try {
    return await serverFetch<T>(path, options);
  } catch (err) {
    if (process.env.NODE_ENV !== "test") {
      const e = err as ApiError;
      console.warn(`[serverFetchSafe] ${path}: ${e?.status ?? "?"} ${e?.code ?? ""}`);
    }
    return null;
  }
}

/** Follow DRF pagination (`next`) and collect results; stops at `maxPages`. Used by sitemap.ts. */
export async function serverFetchAll<T>(
  path: string,
  options: ServerFetchOptions & { maxPages?: number; pageSize?: number } = {},
): Promise<T[]> {
  const { maxPages = 20, pageSize = 100, query, ...rest } = options;
  const out: T[] = [];
  let next: string | null = serverApiUrl(path, { ...query, page_size: pageSize });
  for (let i = 0; next && i < maxPages; i++) {
    const page: Paginated<T> | T[] = await serverFetch<Paginated<T> | T[]>(next, rest);
    if (Array.isArray(page)) {
      out.push(...page);
      break;
    }
    out.push(...page.results);
    next = page.next;
  }
  return out;
}

/** DRF builds absolute `next` links with the request host; keep them on the internal network. */
function toInternal(url: string): string {
  const u = new URL(url);
  return `${INTERNAL_API_URL}${u.pathname}${u.search}`;
}

/** Results array of a list endpoint that may or may not be paginated. */
export function listResults<T>(data: Paginated<T> | T[] | null | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.results ?? []);
}
