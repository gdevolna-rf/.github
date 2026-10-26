import type { Metadata } from "next";
import { Suspense } from "react";
import { ModerationQueue } from "@/components/moderation/ModerationQueue";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Очередь" };

/** Unified moderation queue (TRUST-04). */
export default function ModerationPage() {
  return (
    <Suspense fallback={<LoadingState variant="skeleton" lines={6} />}>
      <ModerationQueue />
    </Suspense>
  );
}
