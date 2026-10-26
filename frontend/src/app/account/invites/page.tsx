import type { Metadata } from "next";
import { Suspense } from "react";
import { InvitesPage } from "@/components/account/misc/AccountSections";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Приглашения" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <InvitesPage />
    </Suspense>
  );
}
