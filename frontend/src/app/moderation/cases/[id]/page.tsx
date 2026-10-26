import type { Metadata } from "next";
import { CaseDetail } from "@/components/moderation/CaseDetail";

export const metadata: Metadata = { title: "Кейс" };

export default async function ModerationCasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CaseDetail id={id} />;
}
