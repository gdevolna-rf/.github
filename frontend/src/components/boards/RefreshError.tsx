"use client";
/**
 * Error block for Server Component pages: the server render failed to load a list, «Повторить» re-runs it
 * (router.refresh) without a full reload (ATX-25). Network errors show «Нет соединения».
 */
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api/errors";
import { ErrorState } from "@/components/ui";

export interface SerializedError {
  status: number;
  code: string;
  message: string;
  requestId?: string | null;
}

/** ApiError is a class — pass only plain fields from a Server Component. */
export function serializeError(err: unknown): SerializedError {
  const e = err as Partial<ApiError> | null;
  return {
    status: typeof e?.status === "number" ? e.status : 0,
    code: typeof e?.code === "string" ? e.code : "network",
    message: typeof e?.message === "string" && e.message ? e.message : "Не удалось загрузить данные.",
    requestId: typeof e?.requestId === "string" ? e.requestId : null,
  };
}

export function RefreshError({ error, title, compact }: { error: SerializedError; title?: string; compact?: boolean }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const apiError = new ApiError({ status: error.status, code: error.code, message: error.message, requestId: error.requestId });
  return (
    <ErrorState
      error={apiError}
      title={title}
      compact={compact}
      retryLabel={pending ? "Загружаем…" : "Повторить"}
      onRetry={() => startTransition(() => router.refresh())}
    />
  );
}
