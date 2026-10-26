import type { Metadata } from "next";
import { Suspense } from "react";
import { WorkshopPage } from "@/components/shaper/ShaperSections";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Профиль мастерской" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <WorkshopPage />
    </Suspense>
  );
}
