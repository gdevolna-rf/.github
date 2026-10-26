import type { Metadata } from "next";
import { Suspense } from "react";
import { SettingsPage } from "@/components/account/settings/SettingsPage";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Настройки" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <SettingsPage />
    </Suspense>
  );
}
