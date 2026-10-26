import type { Metadata } from "next";
import { Suspense } from "react";
import { DiaryPage } from "@/components/account/misc/AccountSections";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Дневник катания" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <DiaryPage />
    </Suspense>
  );
}
