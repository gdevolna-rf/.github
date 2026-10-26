import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, apiUrl, buildQuery, newIdempotencyKey, pageFromUrl, resetCsrfForTests } from "./client";
import { ApiError, NETWORK_ERROR_MESSAGE, UNAVAILABLE_ERROR_MESSAGE, parseApiError } from "./errors";
import { clearCookies, CSRF_OK, json, mockApi } from "@/test/utils";

beforeEach(() => {
  resetCsrfForTests();
  clearCookies();
});

describe("apiUrl / buildQuery", () => {
  it("prefixes /api/v1, drops empty query values and repeats arrays", () => {
    expect(apiUrl("spots", { region: "kamchatka", q: "", page: 2, types: ["spot", "school"], x: undefined })).toBe(
      "/api/v1/spots?region=kamchatka&page=2&types=spot&types=school",
    );
    expect(apiUrl("/me/counters")).toBe("/api/v1/me/counters");
    expect(apiUrl("http://backend:8000/api/v1/spots?page=2")).toBe("/api/v1/spots?page=2");
    expect(buildQuery({ a: null, b: false })).toBe("b=false");
    expect(pageFromUrl("http://localhost:8080/api/v1/spots?page=3")).toBe(3);
    expect(pageFromUrl(null)).toBeUndefined();
  });
});

describe("api client", () => {
  it("sends GET with session cookies and parses JSON", async () => {
    const m = mockApi({ "GET /api/v1/spots": () => json({ count: 0, results: [] }) });
    await expect(api.get("spots", { query: { page: 1 } })).resolves.toEqual({ count: 0, results: [] });
    const init = m.fetch.mock.calls[0][1] as RequestInit;
    expect(init.credentials).toBe("include");
    expect((init.headers as Record<string, string>).Accept).toBe("application/json");
    expect(m.calls("GET /api/v1/auth/csrf")).toHaveLength(0); // safe methods need no CSRF
  });

  it("fetches the CSRF cookie once and sends X-CSRFToken on unsafe requests", async () => {
    const m = mockApi({
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/favorites": () => json({ ok: true }, 201),
      "DELETE /api/v1/favorites/spot/1": () => new Response(null, { status: 204 }),
    });
    await api.post("favorites", { target_type: "spot", target_id: "1" });
    await api.delete("favorites/spot/1");
    expect(m.calls("GET /api/v1/auth/csrf")).toHaveLength(1);
    const post = m.calls("POST /api/v1/favorites")[0];
    expect((post.init!.headers as Record<string, string>)["X-CSRFToken"]).toBe("test-csrf-token");
    expect((post.init!.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(post.body).toEqual({ target_type: "spot", target_id: "1" });
    const del = m.calls("DELETE /api/v1/favorites/spot/1")[0];
    expect((del.init!.headers as Record<string, string>)["X-CSRFToken"]).toBe("test-csrf-token");
  });

  it("re-reads the rotated csrftoken cookie (Django rotates it on login)", async () => {
    mockApi({
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/auth/login": () => {
        document.cookie = "csrftoken=rotated-after-login; path=/";
        return json({ id: "u1", email: "a@b.ru" });
      },
      "POST /api/v1/auth/logout": () => new Response(null, { status: 204 }),
    });
    await api.post("auth/login", { email: "a@b.ru", password: "x" });
    const m = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock;
    await api.post("auth/logout");
    const last = m.calls[m.calls.length - 1][1] as RequestInit;
    expect((last.headers as Record<string, string>)["X-CSRFToken"]).toBe("rotated-after-login");
  });

  it("refreshes the token and retries once when the server rejects CSRF", async () => {
    let attempts = 0;
    const m = mockApi({
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/inquiries": () => {
        attempts += 1;
        return attempts === 1
          ? json({ error: { code: "permission_denied", message: "CSRF Failed: CSRF token missing.", fields: {} } }, 403)
          : json({ id: "inq-1" }, 201);
      },
    });
    await expect(api.post("inquiries", { kind: "general" })).resolves.toEqual({ id: "inq-1" });
    expect(m.calls("GET /api/v1/auth/csrf")).toHaveLength(2);
    expect(attempts).toBe(2);
  });

  it("parses the unified error body into ApiError {status, code, message, fields, requestId}", async () => {
    mockApi({
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/auth/register": () =>
        json(
          {
            error: {
              code: "validation_error",
              message: "Проверьте введённые данные.",
              fields: { email: ["Этот адрес уже зарегистрирован."] },
              request_id: "req-42",
            },
          },
          400,
        ),
    });
    const err = (await api.post("auth/register", {}).catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 400, code: "validation_error", message: "Проверьте введённые данные.", requestId: "req-42" });
    expect(err.fieldError("email")).toBe("Этот адрес уже зарегистрирован.");
    expect(err.isValidation).toBe(true);
    expect(err.retryable).toBe(false);
  });

  it("maps HTML gateway errors and legacy DRF bodies to Russian messages", () => {
    expect(parseApiError(502, "<html>502 Bad Gateway</html>")).toMatchObject({ code: "server_unavailable", message: UNAVAILABLE_ERROR_MESSAGE });
    const legacy = parseApiError(400, { title: ["Обязательное поле."], detail: "Ошибка" });
    expect(legacy.fields).toEqual({ title: ["Обязательное поле."] });
    expect(legacy.message).toBe("Ошибка");
    const guest = parseApiError(403, { error: { code: "not_authenticated", message: "Требуется вход в аккаунт." } });
    expect(guest.isUnauthenticated).toBe(true);
    expect(guest.isForbidden).toBe(false);
  });

  it("turns a network failure into ApiError code 'network' and retries safe requests", async () => {
    let n = 0;
    const m = mockApi({
      "GET /api/v1/regions": () => {
        n += 1;
        if (n === 1) throw new TypeError("Failed to fetch");
        return json([{ id: 1, slug: "kamchatka", name: "Камчатка" }]);
      },
    });
    await expect(api.get("regions", { retries: 1 })).resolves.toHaveLength(1);
    expect(m.calls("GET /api/v1/regions")).toHaveLength(2);

    mockApi({
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/bookings": () => {
        throw new TypeError("Load failed");
      },
    });
    const err = await api.post("bookings", { seats: 1 }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 0, code: "network", message: NETWORK_ERROR_MESSAGE, isNetwork: true, retryable: true });
    // unsafe request without an Idempotency-Key is never retried automatically
    expect((globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.filter((c) => String(c[0]).includes("bookings"))).toHaveLength(1);
  });

  it("sends Idempotency-Key and allows a safe retry of POST", async () => {
    let n = 0;
    const m = mockApi({
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/bookings": () => {
        n += 1;
        if (n === 1) throw new TypeError("Failed to fetch");
        return json({ id: "b1" }, 201);
      },
    });
    const key = newIdempotencyKey();
    await expect(api.post("bookings", { seats: 1 }, { idempotencyKey: key })).resolves.toEqual({ id: "b1" });
    const calls = m.calls("POST /api/v1/bookings");
    expect(calls).toHaveLength(2);
    expect((calls[1].init!.headers as Record<string, string>)["Idempotency-Key"]).toBe(key);
  });

  it("returns undefined for 204 No Content", async () => {
    mockApi({ "GET /api/v1/auth/csrf": CSRF_OK, "POST /api/v1/auth/logout": () => new Response(null, { status: 204 }) });
    await expect(api.post("auth/logout")).resolves.toBeUndefined();
  });
});
