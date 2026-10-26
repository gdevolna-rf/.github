import type { Metadata } from "next";
import { Suspense } from "react";
import { FavoritesPage } from "@/components/account/misc/AccountSections";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Избранное" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <FavoritesPage />
    </Suspense>
  );
}
