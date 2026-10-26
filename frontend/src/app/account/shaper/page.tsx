import type { Metadata } from "next";
import { Suspense } from "react";
import { ShaperPanel } from "@/components/shaper/ShaperPanel";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Кабинет шейпера" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ShaperPanel />
    </Suspense>
  );
}
