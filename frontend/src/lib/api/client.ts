/**
 * Browser API client for `/api/v1` (ARCHITECTURE §2).
 *
 * - session cookie (`credentials: "include"`), JSON in/out;
 * - CSRF: one `GET /api/v1/auth/csrf` (only if the `csrftoken` cookie is missing), then
 *   `X-CSRFToken: <csrftoken cookie>` on every unsafe request; the cookie is re-read each time because
 *   Django rotates it on login; one automatic retry when the server rejects the token;
 * - errors → typed `ApiError {status, code, message, fields, requestId}`; no response → code "network";
 * - safe requests (GET/HEAD) and requests with an Idempotency-Key are retried automatically on
 *   network/5xx errors (ATX-25); the UI then offers a manual retry (ErrorState / toast action).
 *
 * Use only in Client Components. Server Components use `src/lib/api/server.ts`.
 */
import { ApiError, isApiError, networkError, parseApiError, timeoutError } from "./errors";

export const API_BASE = "/api/v1";
const CSRF_COOKIE = "csrftoken";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export type QueryValue = string | number | boolean | null | undefined | Array<string | number | boolean>;
export type Query = Record<string, QueryValue>;

export interface ApiRequestOptions {
  method?: "GET" | "HEAD" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Query;
  /** Plain objects are sent as JSON; FormData/Blob/string are sent as-is. */
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  /** Sends `Idempotency-Key` (required by POST /inquiries and POST /bookings). Makes the request retry-safe. */
  idempotencyKey?: string;
  /** Automatic retries for retry-safe requests on network/5xx errors. Default: 2 for GET, 1 with idempotencyKey, else 0. */
  retries?: number;
  /** Per-attempt timeout. Default 20 s. */
  timeoutMs?: number;
}

/** Build `/api/v1/<path>?<query>`. Absolute URLs (DRF `next` links) are reduced to path + query. */
export function apiUrl(path: string, query?: Query): string {
  let url: string;
  if (/^https?:\/\//.test(path)) {
    const u = new URL(path);
    url = u.pathname + u.search;
  } else if (path.startsWith(API_BASE)) {
    url = path;
  } else {
    url = `${API_BASE}/${path.replace(/^\/+/, "")}`;
  }
  const qs = buildQuery(query);
  if (!qs) return url;
  return url + (url.includes("?") ? "&" : "?") + qs;
}

export function buildQuery(query?: Query): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else params.append(key, String(value));
  }
  return params.toString();
}

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

let csrfPromise: Promise<void> | null = null;

/** Make sure the `csrftoken` cookie exists. Called once lazily; `force` re-requests it (token rejected). */
export function ensureCsrf(force = false): Promise<void> {
  if (!force && readCookie(CSRF_COOKIE)) return Promise.resolve();
  if (!csrfPromise || force) {
    csrfPromise = fetch(apiUrl("auth/csrf"), { credentials: "include", headers: { Accept: "application/json" } })
      .then((res) => {
        if (!res.ok) throw parseApiError(res.status, null, res.headers.get("X-Request-ID"));
      })
      .catch((err) => {
        csrfPromise = null; // allow a later retry
        throw isApiError(err) ? err : networkError();
      });
  }
  return csrfPromise;
}

/** For tests: forget the cached CSRF bootstrap. */
export function resetCsrfForTests(): void {
  csrfPromise = null;
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

function isCsrfFailure(error: ApiError): boolean {
  return error.status === 403 && /csrf/i.test(`${error.code} ${error.message}`);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function attempt<T>(url: string, init: RequestInit, timeoutMs: number, outer?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onOuterAbort = () => controller.abort();
  outer?.addEventListener("abort", onOuterAbort);

  let res: Response;
  try {
    res = await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (outer?.aborted) throw err; // caller cancelled (TanStack Query) — propagate AbortError
    throw timedOut ? timeoutError() : networkError();
  } finally {
    clearTimeout(timer);
    outer?.removeEventListener("abort", onOuterAbort);
  }

  const requestId = res.headers.get("X-Request-ID");
  if (res.status === 204 || res.status === 205) return undefined as T;
  const text = await res.text().catch(() => "");
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) throw parseApiError(res.status, body, requestId);
  return body as T;
}

export async function apiRequest<T = unknown>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const method = options.method ?? (options.body !== undefined ? "POST" : "GET");
  const url = apiUrl(path, options.query);
  const unsafe = UNSAFE.has(method);
  const retrySafe = !unsafe || Boolean(options.idempotencyKey);
  const retries = options.retries ?? (method === "GET" || method === "HEAD" ? 2 : options.idempotencyKey ? 1 : 0);
  const timeoutMs = options.timeoutMs ?? 20_000;

  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  let body: BodyInit | undefined;
  if (options.body !== undefined && options.body !== null) {
    const b = options.body;
    if (b instanceof FormData || b instanceof Blob || typeof b === "string" || b instanceof URLSearchParams) {
      body = b as BodyInit;
    } else {
      body = JSON.stringify(b);
      headers["Content-Type"] = "application/json";
    }
  }
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  let csrfRetried = false;
  for (let n = 0; ; n++) {
    if (unsafe) {
      await ensureCsrf();
      const token = readCookie(CSRF_COOKIE);
      if (token) headers["X-CSRFToken"] = token;
    }
    try {
      return await attempt<T>(url, { method, headers, body, credentials: "include" }, timeoutMs, options.signal);
    } catch (err) {
      if (!isApiError(err)) throw err;
      if (unsafe && !csrfRetried && isCsrfFailure(err)) {
        csrfRetried = true;
        await ensureCsrf(true);
        n--; // the CSRF refresh does not consume a network retry
        continue;
      }
      const transient = err.isNetwork || err.status === 502 || err.status === 503 || err.status === 504;
      if (retrySafe && transient && n < retries && !options.signal?.aborted) {
        await sleep(400 * 2 ** n);
        continue;
      }
      throw err;
    }
  }
}

type BodyOptions = Omit<ApiRequestOptions, "method" | "body">;

export const api = {
  get: <T>(path: string, options?: Omit<ApiRequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: BodyOptions) =>
    apiRequest<T>(path, { ...options, method: "POST", body: body ?? {} }),
  put: <T>(path: string, body?: unknown, options?: BodyOptions) =>
    apiRequest<T>(path, { ...options, method: "PUT", body: body ?? {} }),
  patch: <T>(path: string, body?: unknown, options?: BodyOptions) =>
    apiRequest<T>(path, { ...options, method: "PATCH", body: body ?? {} }),
  delete: <T = void>(path: string, options?: BodyOptions) => apiRequest<T>(path, { ...options, method: "DELETE" }),
};

/** `?page=` of a DRF `next`/`previous` link (for useInfiniteQuery getNextPageParam). */
export function pageFromUrl(url: string | null | undefined): number | undefined {
  if (!url) return undefined;
  try {
    const page = new URL(url, "http://x").searchParams.get("page");
    return page ? Number(page) : 1;
  } catch {
    return undefined;
  }
}
