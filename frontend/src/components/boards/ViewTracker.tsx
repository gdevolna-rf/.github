"use client";
/**
 * Qualified view beacon (MET-08, ARCHITECTURE §6): POST /analytics/views once per mounted detail page, after a
 * short delay so bounces are not counted. The server filters bots, self-views and repeat viewers; failures are
 * silent (analytics must never break a page).
 */
import { useEffect } from "react";
import { trackView, type ViewSubjectType } from "@/lib/api/boards";

export function ViewTracker({ type, id, delayMs = 1200 }: { type: ViewSubjectType; id: string; delayMs?: number }) {
  useEffect(() => {
    if (!id) return;
    const timer = setTimeout(() => {
      trackView(type, id).catch(() => undefined);
    }, delayMs);
    return () => clearTimeout(timer);
  }, [type, id, delayMs]);
  return null;
}
