import type { Metadata } from "next";
import { InquiryDetailPage } from "@/components/account/inbox/InquiryDetailPage";

export const metadata: Metadata = { title: "Обращение" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <InquiryDetailPage id={id} />;
}
