import type { Metadata } from "next";
import { Suspense } from "react";
import { InboxPage } from "@/components/account/inbox/InboxPage";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Обращения" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <InboxPage />
    </Suspense>
  );
}
