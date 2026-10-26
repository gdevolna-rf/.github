import type { Metadata } from "next";
import { BookingDetailPage } from "@/components/account/bookings/BookingsPages";

export const metadata: Metadata = { title: "Бронирование" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <BookingDetailPage id={id} />;
}
