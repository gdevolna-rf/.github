"use client";
import { useQuery } from "@tanstack/react-query";
import { ik, instructorApi, type InstructorOwn } from "@/lib/api/instructorCabinet";
import { useMe } from "@/lib/auth/hooks";
import { DEFAULT_TIME_ZONE } from "@/lib/format";
import { useRegionZones } from "@/components/learning-cabinet/hooks";

/** Own instructor card (`null` — not created yet). */
export function useInstructorProfile(enabled = true) {
  return useQuery({ queryKey: ik.profile, queryFn: instructorApi.profile, enabled });
}

export function useOffers(enabled = true) {
  return useQuery({ queryKey: ik.offers, queryFn: instructorApi.offers.list, enabled });
}

/** «Home» zone of the instructor: first region of the card → profile region → Europe/Moscow. */
export function useInstructorZone(profile: InstructorOwn | null | undefined): string {
  const { me } = useMe();
  const zoneOf = useRegionZones();
  return zoneOf(profile?.regions?.[0]?.slug) ?? zoneOf(me?.region?.slug) ?? DEFAULT_TIME_ZONE;
}
