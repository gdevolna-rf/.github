import type { Metadata } from "next";
import { Suspense } from "react";
import { ReviewsPage } from "@/components/account/misc/AccountSections";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Мои отзывы" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ReviewsPage />
    </Suspense>
  );
}
