"use client";
/** Reference-data hooks shared by the instructor and school cabinets (cached for 10 minutes). */
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { lk, refsApi, type RegionOption, type SpotOption } from "@/lib/api/learningCabinet";
import { DEFAULT_TIME_ZONE } from "@/lib/format";
import { isTimeZone } from "./time";

const TEN_MIN = 10 * 60_000;

export function useRegions() {
  return useQuery({ queryKey: lk.regions, queryFn: refsApi.regions, staleTime: TEN_MIN });
}

/** All published spots (6–100 rows), filtered on the client by region. */
export function useSpots() {
  return useQuery({ queryKey: lk.spots(), queryFn: () => refsApi.spots(), staleTime: TEN_MIN });
}

export function useBoardTypes() {
  return useQuery({ queryKey: lk.boardTypes, queryFn: refsApi.boardTypes, staleTime: TEN_MIN });
}

/** region slug → IANA zone (from GET /regions). */
export function useRegionZones(): (regionSlug: string | null | undefined) => string | null {
  const regions = useRegions();
  return useMemo(() => {
    const map = new Map<string, string>((regions.data ?? []).map((r: RegionOption) => [r.slug, r.timezone]));
    return (slug) => {
      const tz = slug ? map.get(slug) : undefined;
      return isTimeZone(tz) ? tz : null;
    };
  }, [regions.data]);
}

/**
 * Zone of a spot (its region) with fallbacks — the same order the backend uses (learning.services.common.tz_name_for):
 * spot region → organization region → Europe/Moscow.
 */
export function useSpotZone() {
  const zoneOf = useRegionZones();
  const spots = useSpots();
  return useMemo(() => {
    const bySlug = new Map<string, SpotOption>((spots.data ?? []).map((s) => [s.slug, s]));
    return (spotSlug: string | null | undefined, fallbackRegionSlug?: string | null): string => {
      const spot = spotSlug ? bySlug.get(spotSlug) : undefined;
      return zoneOf(spot?.region?.slug) ?? zoneOf(fallbackRegionSlug) ?? DEFAULT_TIME_ZONE;
    };
  }, [spots.data, zoneOf]);
}
