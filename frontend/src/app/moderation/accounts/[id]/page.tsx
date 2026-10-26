import type { Metadata } from "next";
import { AccountReview } from "@/components/moderation/AccountReview";

export const metadata: Metadata = { title: "Аккаунт" };

export default async function ModerationAccountPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AccountReview id={id} />;
}
