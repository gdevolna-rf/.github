/**
 * Shaper cabinet sub-routes (ARCHITECTURE §9 «/account/shaper/...»). Built from routes.ts (the single source of
 * the base paths); the shared routes file has no sub-paths for this section yet.
 * `organization` keeps the selected workshop when the account belongs to several (me/workshop?organization=).
 */
import { routes } from "@/lib/routes";

const withOrg = (path: string, organization?: string | null) =>
  organization ? `${path}${path.includes("?") ? "&" : "?"}organization=${encodeURIComponent(organization)}` : path;

export const shaperRoutes = {
  panel: (organization?: string | null) => withOrg(routes.account.shaper, organization),
  boards: (organization?: string | null) => withOrg(`${routes.account.shaper}/boards`, organization),
  workshop: (organization?: string | null) => withOrg(`${routes.account.shaper}/workshop`, organization),
  stats: (organization?: string | null) => withOrg(`${routes.account.shaper}/stats`, organization),
  /** the unified inbox (fe-account, MSG-01) filtered to the shaper role */
  inquiries: `${routes.account.inquiries}?role=shaper`,
  /** provider bookings (fe-account) — rentals of workshop boards */
  bookings: (organization?: string | null) =>
    `${routes.account.bookings}?box=provider&kind=rental${organization ? `&organization=${encodeURIComponent(organization)}` : ""}`,
};
