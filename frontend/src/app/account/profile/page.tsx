import type { Metadata } from "next";
import { Suspense } from "react";
import { ProfileForm } from "@/components/account/profile/ProfileForm";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Мой профиль" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ProfileForm />
    </Suspense>
  );
}
