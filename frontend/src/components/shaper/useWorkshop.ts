"use client";
/**
 * The current workshop of the shaper cabinet: GET me/workshop (+ `?organization=` when the account belongs to
 * several workshops). `noWorkshop` — 404 no_workshop (show the registration form / explanation).
 */
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { isApiError } from "@/lib/api/errors";
import { shaperApi, shaperKeys } from "@/lib/api/shaper";

export function useWorkshop() {
  const params = useSearchParams();
  const organization = params?.get("organization") || null;
  const query = useQuery({
    queryKey: shaperKeys.workshop(organization),
    queryFn: () => shaperApi.workshop(organization),
    retry: (count, error) => !(isApiError(error) && (error.isNotFound || error.isForbidden || error.isUnauthenticated)) && count < 1,
  });
  const noWorkshop = isApiError(query.error) && query.error.isNotFound;
  return { query, workshop: query.data ?? null, organization, noWorkshop };
}
