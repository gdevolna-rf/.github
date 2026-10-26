import type { Metadata } from "next";
import { Suspense } from "react";
import { RentalCabinet } from "@/components/rental/RentalCabinet";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Прокат" };

/** /account/rental — inventory, availability and links to provider bookings (RENT-01…05). `?organization=` for org inventory. */
export default function Page() {
  return (
    <Suspense fallback={<LoadingState label="Открываем прокат…" />}>
      <RentalCabinet />
    </Suspense>
  );
}
