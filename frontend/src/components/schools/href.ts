/** URL of the schools catalogue with filters (server- and client-safe). */
import { routes } from "@/lib/routes";

export interface SchoolFilterValues {
  region: string;
  spot: string;
  q: string;
}

export function schoolsHref(values: Partial<SchoolFilterValues> & { page?: number }): string {
  const params = new URLSearchParams();
  if (values.region) params.set("region", values.region);
  if (values.spot) params.set("spot", values.spot);
  if (values.q?.trim()) params.set("q", values.q.trim());
  if (values.page && values.page > 1) params.set("page", String(values.page));
  const qs = params.toString();
  return qs ? `${routes.schools}?${qs}` : routes.schools;
}
