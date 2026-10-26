import type { Metadata } from "next";
import { Suspense } from "react";
import { SpecialtiesPage } from "@/components/account/specialties/SpecialtiesPage";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Мои направления" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <SpecialtiesPage />
    </Suspense>
  );
}
