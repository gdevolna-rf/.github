import type { Metadata } from "next";
import { Suspense } from "react";
import { ShaperStats } from "@/components/shaper/ShaperSections";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Статистика мастерской" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ShaperStats />
    </Suspense>
  );
}
