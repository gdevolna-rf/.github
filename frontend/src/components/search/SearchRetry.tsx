"use client";
/** Error of the server-rendered search with «Повторить» (router.refresh re-runs the Server Component). */
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { ErrorState } from "@/components/ui/States";
import { ApiError } from "@/lib/api/errors";

export function SearchRetry({ status, code, message, requestId }: { status: number; code: string; message: string; requestId?: string | null }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <ErrorState
      error={new ApiError({ status, code, message, requestId })}
      title="Поиск сейчас недоступен"
      retryLabel={pending ? "Ищем…" : "Повторить"}
      onRetry={() => startTransition(() => router.refresh())}
    />
  );
}
