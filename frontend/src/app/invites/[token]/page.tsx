import type { Metadata } from "next";
import { Suspense } from "react";
import { buildMetadata } from "@/lib/seo";
import { InviteResponse } from "@/components/auth/InviteResponse";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = buildMetadata({ title: "Приглашение", path: "/invites", noindex: true });

export default async function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return (
    <Suspense fallback={<LoadingState />}>
      <InviteResponse token={token} />
    </Suspense>
  );
}
