"use client";
/** Error block for a server-rendered list that failed to load (ATX-25): message + «Повторить» (router.refresh). */
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { ErrorState } from "@/components/ui";
import { ApiError } from "@/lib/api/errors";

/** Server → client props must be plain objects: rebuild the ApiError from its fields. */
function revive(error: unknown): unknown {
  if (error && typeof error === "object" && "status" in error && "message" in error) {
    const e = error as { status: number; code?: string; message: string };
    return new ApiError({ status: e.status, code: e.code ?? "error", message: e.message });
  }
  return error;
}

export function CatalogError({ error, title = "Список не загрузился" }: { error: unknown; title?: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  return (
    <ErrorState
      title={title}
      error={revive(error)}
      retryLabel={pending ? "Загружаем…" : "Повторить"}
      onRetry={() => start(() => router.refresh())}
    />
  );
}
