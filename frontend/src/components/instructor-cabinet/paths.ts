/** Sub-routes of /account/instructor (ARCHITECTURE §9). Built from routes.ts — the single source of the root. */
import { routes } from "@/lib/routes";

const root = routes.account.instructor;

export const instructorPaths = {
  root,
  profile: `${root}/profile`,
  offers: `${root}/offers`,
  schedule: `${root}/schedule`,
  students: `${root}/students`,
  certificates: `${root}/certificates`,
  stats: `${root}/stats`,
} as const;

/** Links into screens owned by other engineers (single inbox — MSG-01). */
export const instructorLinks = {
  inquiries: `${routes.account.inquiries}?role=instructor`,
  bookings: `${routes.account.bookings}?box=provider`,
};
