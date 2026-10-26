"use client";
/**
 * Error block for Server Component sections (catalogue API down / timeout, ATX-25): message + «Повторить»
 * that re-renders the route (router.refresh) without a full reload.
 */
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button, Icon } from "@/components/ui";

export function RetryError({ title = "Не получилось загрузить", message, compact }: { title?: string; message: string; compact?: boolean }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  return (
    <div className={`gv-state gv-state-error${compact ? " is-compact" : ""}`} role="alert">
      <span className="gv-state-icon" aria-hidden="true">
        <Icon name="alert" size={22} />
      </span>
      <div className="gv-state-body">
        <h3>{title}</h3>
        <p>{message}</p>
      </div>
      <Button variant="pill" icon="refresh" loading={pending} onClick={() => start(() => router.refresh())}>
        Повторить
      </Button>
    </div>
  );
}
