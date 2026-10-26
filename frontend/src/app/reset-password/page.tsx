import type { Metadata } from "next";
import { Suspense } from "react";
import { buildMetadata } from "@/lib/seo";
import { ResetPassword } from "@/components/auth/ResetPassword";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = buildMetadata({ title: "Восстановление доступа", path: "/reset-password", noindex: true });

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ResetPassword />
    </Suspense>
  );
}
