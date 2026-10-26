"use client";
/** Route error boundary (Next 16 passes `retry`): clear message + retry (ATX-25). */
import { useEffect } from "react";
import { ButtonLink } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/States";

export default function RouteError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <div className="gv-special">
      <ErrorState
        title="Страница не загрузилась"
        error={error && typeof error === "object" && "status" in error ? error : undefined}
        onRetry={retry}
      />
      <div className="view-tools">
        <ButtonLink href="/" variant="pill">
          На главную
        </ButtonLink>
      </div>
    </div>
  );
}
