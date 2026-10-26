import type { Metadata } from "next";
import { Suspense } from "react";
import { AuditLog } from "@/components/moderation/AuditLog";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Журнал действий" };

/** Audit log with filters and before/after diff (DATA-09). */
export default function ModerationAuditPage() {
  return (
    <Suspense fallback={<LoadingState variant="skeleton" lines={6} />}>
      <AuditLog />
    </Suspense>
  );
}
