import type { ApiErrorBody } from "./types";

/** User-facing texts for errors that never reach the API (ATX-25: clear message + retry). */
export const NETWORK_ERROR_MESSAGE = "Нет соединения с сервером. Проверьте интернет и попробуйте ещё раз.";
export const TIMEOUT_ERROR_MESSAGE = "Сервер долго не отвечает. Попробуйте ещё раз.";
export const UNAVAILABLE_ERROR_MESSAGE = "Сервис временно недоступен. Попробуйте ещё раз через минуту.";

const STATUS_MESSAGES: Record<number, string> = {
  400: "Проверьте введённые данные.",
  401: "Требуется вход в аккаунт.",
  403: "Недостаточно прав.",
  404: "Не найдено.",
  405: "Действие недоступно.",
  409: "Данные изменились — обновите страницу и попробуйте ещё раз.",
  413: "Файл слишком большой.",
  429: "Слишком много запросов, попробуйте позже.",
  500: "Внутренняя ошибка сервера. Мы уже разбираемся.",
};

export type FieldErrors = Record<string, string[]>;

/**
 * Typed error for every failed API call. Mirrors the unified backend body
 * `{"error": {"code", "message", "fields", "request_id"}}` (ARCHITECTURE §2).
 * `status === 0` means the request never got an HTTP response (network / timeout).
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: FieldErrors;
  readonly requestId: string | null;

  constructor(init: { status: number; code: string; message: string; fields?: FieldErrors; requestId?: string | null }) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.fields = init.fields ?? {};
    this.requestId = init.requestId ?? null;
  }

  /** No HTTP response at all (offline, DNS, CORS, aborted by timeout). */
  get isNetwork(): boolean {
    return this.status === 0;
  }
  /** Not logged in (DRF session auth answers 403 `not_authenticated`, token auth would answer 401). */
  get isUnauthenticated(): boolean {
    return this.status === 401 || this.code === "not_authenticated";
  }
  get isForbidden(): boolean {
    return this.status === 403 && !this.isUnauthenticated;
  }
  get isNotFound(): boolean {
    return this.status === 404;
  }
  get isValidation(): boolean {
    return this.status === 400;
  }
  get isConflict(): boolean {
    return this.status === 409;
  }
  /** Worth retrying as-is: network trouble, timeouts, 429 and 5xx. */
  get retryable(): boolean {
    return this.status === 0 || this.status === 429 || this.status >= 500;
  }

  /** First message for a form field (`fields.email[0]`), if any. */
  fieldError(name: string): string | undefined {
    return this.fields[name]?.[0];
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

function isErrorBody(body: unknown): body is ApiErrorBody {
  return (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof (body as { error: unknown }).error === "object" &&
    (body as { error: unknown }).error !== null
  );
}

/** DRF-style fallbacks: `{"detail": "..."}` or `{"field": ["..."]}` (in case a view bypasses the handler). */
function fromLegacyBody(body: Record<string, unknown>): { message?: string; fields: FieldErrors } {
  const fields: FieldErrors = {};
  let message: string | undefined;
  for (const [key, value] of Object.entries(body)) {
    if (key === "detail" && typeof value === "string") message = value;
    else if (key === "non_field_errors" && Array.isArray(value)) message = String(value[0]);
    else if (Array.isArray(value)) fields[key] = value.map(String);
    else if (typeof value === "string") fields[key] = [value];
  }
  return { message, fields };
}

/** Build an ApiError from an HTTP status and a parsed (or unparsable) response body. */
export function parseApiError(status: number, body: unknown, requestIdHeader?: string | null): ApiError {
  if (isErrorBody(body)) {
    const e = body.error;
    return new ApiError({
      status,
      code: e.code || codeForStatus(status),
      message: e.message || STATUS_MESSAGES[status] || "Ошибка.",
      fields: normalizeFields(e.fields),
      requestId: e.request_id ?? requestIdHeader ?? null,
    });
  }
  if (typeof body === "object" && body !== null && !Array.isArray(body)) {
    const legacy = fromLegacyBody(body as Record<string, unknown>);
    return new ApiError({
      status,
      code: codeForStatus(status),
      message: legacy.message || messageForStatus(status),
      fields: legacy.fields,
      requestId: requestIdHeader ?? null,
    });
  }
  // HTML from nginx (502/504) or empty body
  return new ApiError({
    status,
    code: codeForStatus(status),
    message: messageForStatus(status),
    requestId: requestIdHeader ?? null,
  });
}

function normalizeFields(fields: unknown): FieldErrors {
  if (!fields || typeof fields !== "object") return {};
  const out: FieldErrors = {};
  for (const [key, value] of Object.entries(fields as Record<string, unknown>)) {
    if (Array.isArray(value)) out[key] = value.map(String);
    else if (value != null) out[key] = [String(value)];
  }
  return out;
}

function codeForStatus(status: number): string {
  if (status === 400) return "validation_error";
  if (status === 401) return "not_authenticated";
  if (status === 403) return "permission_denied";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 429) return "throttled";
  if (status === 502 || status === 503 || status === 504) return "server_unavailable";
  if (status >= 500) return "server_error";
  return "error";
}

function messageForStatus(status: number): string {
  if (status === 502 || status === 503 || status === 504) return UNAVAILABLE_ERROR_MESSAGE;
  return STATUS_MESSAGES[status] ?? (status >= 500 ? STATUS_MESSAGES[500] : "Ошибка запроса.");
}

export function networkError(): ApiError {
  return new ApiError({ status: 0, code: "network", message: NETWORK_ERROR_MESSAGE });
}

export function timeoutError(): ApiError {
  return new ApiError({ status: 0, code: "timeout", message: TIMEOUT_ERROR_MESSAGE });
}

/** Russian text for any thrown value — use in toasts and ErrorState. */
export function errorMessage(error: unknown, fallback = "Что-то пошло не так. Попробуйте ещё раз."): string {
  if (isApiError(error)) return error.message;
  // Raw browser errors ("Failed to fetch", "Load failed") are never shown as-is.
  if (error instanceof TypeError) return NETWORK_ERROR_MESSAGE;
  return fallback;
}
