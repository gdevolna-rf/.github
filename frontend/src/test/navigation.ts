/**
 * Controllable mock of `next/navigation` for unit tests (registered globally in vitest.setup.ts).
 *   navigation.set({ pathname: "/account/profile", search: "tab=2" });
 *   expect(navigation.router.replace).toHaveBeenCalledWith("/login?next=…");
 */
import { vi } from "vitest";

export const navigation = {
  pathname: "/",
  search: "",
  router: {
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  },
  set(opts: { pathname?: string; search?: string }) {
    if (opts.pathname !== undefined) this.pathname = opts.pathname;
    if (opts.search !== undefined) this.search = opts.search;
  },
  reset() {
    this.pathname = "/";
    this.search = "";
    Object.values(this.router).forEach((fn) => fn.mockReset());
  },
};

export const navigationMock = {
  useRouter: () => navigation.router,
  usePathname: () => navigation.pathname,
  useSearchParams: () => new URLSearchParams(navigation.search),
  useParams: () => ({}),
  redirect: vi.fn(),
  notFound: vi.fn(),
};
