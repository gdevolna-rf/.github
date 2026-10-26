import type { Metadata } from "next";
import { Suspense } from "react";
import { buildMetadata } from "@/lib/seo";
import { LoginForm } from "@/components/auth/LoginForm";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = buildMetadata({ title: "Вход", path: "/login", noindex: true });

export default function LoginPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <LoginForm />
    </Suspense>
  );
}
