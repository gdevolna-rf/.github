import type { Metadata } from "next";
import { Suspense } from "react";
import { BookingsPage } from "@/components/account/bookings/BookingsPages";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Бронирования" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <BookingsPage />
    </Suspense>
  );
}
