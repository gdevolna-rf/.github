/**
 * Moderation sub-routes (ARCHITECTURE §9 «/moderation, /moderation/cases/{id}, /moderation/audit»).
 * Kept here because src/lib/routes.ts only knows `routes.moderation`; the lead may move them there later.
 */
import { routes } from "@/lib/routes";

const seg = (v: string | number) => encodeURIComponent(String(v));

export const modRoutes = {
  queue: routes.moderation,
  case: (id: string) => `${routes.moderation}/cases/${seg(id)}`,
  audit: (params?: Record<string, string | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params ?? {})) if (v) qs.set(k, v);
    const s = qs.toString();
    return `${routes.moderation}/audit${s ? `?${s}` : ""}`;
  },
  account: (id: string) => `${routes.moderation}/accounts/${seg(id)}`,
  staff: `${routes.moderation}/staff`,
} as const;

/** Account sub-pages owned by this domain that are not in routes.ts yet. */
export const mineRoutes = {
  complaints: "/account/complaints",
} as const;
