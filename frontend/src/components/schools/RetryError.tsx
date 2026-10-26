"use client";
/** ErrorState for Server Component pages: «Повторить» re-renders the route (router.refresh). */
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { ErrorState } from "@/components/ui";
import { ApiError } from "@/lib/api/errors";

export function RetryError({ status, code, message, title }: { status: number; code: string; message: string; title?: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const error = new ApiError({ status, code, message });
  return (
    <ErrorState
      error={error}
      title={title}
      retryLabel={pending ? "Загружаем…" : "Повторить"}
      onRetry={() => start(() => router.refresh())}
    />
  );
}
