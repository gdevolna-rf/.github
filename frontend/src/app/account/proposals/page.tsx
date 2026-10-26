import type { Metadata } from "next";
import { Suspense } from "react";
import { ProposalsPage } from "@/components/account/misc/AccountSections";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Мои правки спотов" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ProposalsPage />
    </Suspense>
  );
}
