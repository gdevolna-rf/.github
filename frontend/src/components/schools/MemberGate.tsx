"use client";
/**
 * Hides customer actions (book, write, review) from members of the school itself (BR-05, AT-03, SHP-11 analogue):
 * the server refuses them anyway; members see `fallback` (e.g. a link to the school cabinet) instead.
 */
import type { ReactNode } from "react";
import { useMe } from "@/lib/auth/hooks";
import { useHydrated } from "./useHydrated";

export function useIsMember(organizationId: string): boolean {
  const { me } = useMe();
  const hydrated = useHydrated();
  return hydrated && Boolean(me?.organizations?.some((o) => String(o.id) === String(organizationId)));
}

export function MemberGate({
  organizationId,
  children,
  fallback = null,
}: {
  organizationId: string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const member = useIsMember(organizationId);
  return <>{member ? fallback : children}</>;
}
