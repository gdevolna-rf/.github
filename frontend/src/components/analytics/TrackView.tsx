"use client";
/**
 * Qualified view of a public card (раздел 10, MET-01): POST /api/v1/analytics/views once per mount.
 * The server drops bots, self-views and repeats of the same viewer within a day; failures are silent.
 *
 *   <TrackView subjectType="spot" subjectId={spot.id} />
 */
import { useEffect, useRef } from "react";
import { api } from "@/lib/api/client";

export type ViewSubjectType =
  | "instructor"
  | "surfer"
  | "board_model"
  | "board_variant"
  | "spot"
  | "organization"
  | "inventory_item";

export function TrackView({ subjectType, subjectId }: { subjectType: ViewSubjectType; subjectId: string }) {
  const sent = useRef<string | null>(null);
  useEffect(() => {
    const key = `${subjectType}:${subjectId}`;
    if (!subjectId || sent.current === key) return;
    // Wait a moment so a bounce/prefetch does not count as a view (and StrictMode's double effect sends once).
    const timer = setTimeout(() => {
      sent.current = key;
      api.post("analytics/views", { subject_type: subjectType, subject_id: subjectId }, { retries: 0 }).catch(() => {});
    }, 1500);
    return () => clearTimeout(timer);
  }, [subjectType, subjectId]);
  return null;
}
