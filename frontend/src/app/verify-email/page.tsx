import type { Metadata } from "next";
import { Suspense } from "react";
import { buildMetadata } from "@/lib/seo";
import { VerifyEmail } from "@/components/auth/VerifyEmail";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = buildMetadata({ title: "Подтверждение почты", path: "/verify-email", noindex: true });

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <VerifyEmail />
    </Suspense>
  );
}
