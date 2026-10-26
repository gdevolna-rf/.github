import type { Metadata } from "next";
import { Suspense } from "react";
import { NotificationsPage } from "@/components/account/misc/AccountSections";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Уведомления" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <NotificationsPage />
    </Suspense>
  );
}
