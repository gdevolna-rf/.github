/**
 * Test helpers: provider wrapper + a tiny fetch router.
 *
 *   const api = mockApi({ "GET /api/v1/me": () => json(ME), "POST /api/v1/favorites": () => json({}, 201) });
 *   renderWithProviders(<HeartButton type="spot" id="1" />);
 *   expect(api.calls("POST /api/v1/favorites")).toHaveLength(1);
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { vi } from "vitest";
import { LoginPromptProvider } from "@/components/auth/LoginPrompt";
import { ToastProvider } from "@/components/ui/Toast";

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

type Handler = (req: { url: string; method: string; init?: RequestInit; body: unknown }) => Response | Promise<Response>;

/** Routes are "METHOD /path" (query string ignored) or "METHOD /path?exact=query". Unknown routes → 404. */
export function mockApi(routes: Record<string, Handler>) {
  const log: Array<{ key: string; url: string; init?: RequestInit; body: unknown }> = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    const u = new URL(url, "http://localhost");
    const key = `${method} ${u.pathname}`;
    let body: unknown = init?.body;
    if (typeof body === "string") {
      try {
        body = JSON.parse(body);
      } catch {
        /* keep string */
      }
    }
    log.push({ key, url, init, body });
    const handler = routes[`${method} ${u.pathname}${u.search}`] ?? routes[key];
    if (!handler) return json({ error: { code: "not_found", message: "Не найдено.", fields: {} } }, 404);
    return handler({ url, method, init, body });
  });
  vi.stubGlobal("fetch", fetchMock);
  return {
    fetch: fetchMock,
    calls: (key: string) => log.filter((c) => c.key === key),
    log,
  };
}

export function makeTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity, staleTime: Infinity }, mutations: { retry: false } },
  });
}

export function renderWithProviders(ui: ReactElement, options: RenderOptions & { queryClient?: QueryClient } = {}) {
  const queryClient = options.queryClient ?? makeTestQueryClient();
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <LoginPromptProvider>{children}</LoginPromptProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
  return { queryClient, ...render(ui, { wrapper: Wrapper, ...options }) };
}

/** Raw `/me` payload in the backend shape (see GET /api/v1/me). */
export const RAW_ME = {
  id: "c56eceb2-ac27-4603-88d8-ebf443b5090d",
  email: "ivan.petrov@demo.gdevolna.local",
  email_verified: true,
  profile: {
    handle: "ivan-petrov",
    first_name: "Иван",
    last_name: "Петров",
    display_name: "Иван Петров",
    avatar: null,
    region: { id: 1, slug: "kamchatskiy-kray", name: "Камчатский край" },
    gg_surfer_enabled: true,
  },
  specialties: [
    { code: "surfer", status: "active", is_primary: false },
    { code: "instructor", status: "active", is_primary: true },
    { code: "shaper", status: "active", is_primary: false },
    { code: "rental", status: "disabled", is_primary: false },
  ],
  staff_roles: [],
  organizations: [
    { id: "org-1", slug: "kamchatka-boards", name: "Kamchatka Boards", kind: "workshop", status: "published", role: "owner", membership_id: "m-1" },
  ],
  instructor_profile: { id: "ip-1", status: "published" },
  two_factor: { enabled: false, verified: false, required: false },
  deletion: null,
};

export const GUEST_403 = () =>
  json({ error: { code: "not_authenticated", message: "Требуется вход в аккаунт.", fields: {}, request_id: "r1" } }, 403);

export const CSRF_OK = () => {
  document.cookie = "csrftoken=test-csrf-token; path=/";
  return json({ detail: "ok" });
};

export function clearCookies() {
  for (const c of document.cookie.split(";")) {
    const name = c.split("=")[0]?.trim();
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  }
}
