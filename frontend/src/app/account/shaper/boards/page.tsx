import type { Metadata } from "next";
import { Suspense } from "react";
import { BoardsPage } from "@/components/shaper/BoardsPage";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Мои доски" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <BoardsPage />
    </Suspense>
  );
}
