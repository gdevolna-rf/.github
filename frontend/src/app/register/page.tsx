import type { Metadata } from "next";
import { Suspense } from "react";
import { buildMetadata } from "@/lib/seo";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = buildMetadata({
  title: "Регистрация",
  description: "Один аккаунт для сёрферов, инструкторов, шейперов, школ и проката.",
  path: "/register",
  noindex: true,
});

export default function RegisterPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <RegisterForm />
    </Suspense>
  );
}
