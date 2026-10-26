import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { Icon } from "@/components/ui/Icon";

/**
 * Form-level error/notice (role="alert"): server messages such as 409 «Инструктор уже занят в это время…»
 * (F11, ATX-15) or the publication checklist. `tone="info"` for neutral hints.
 */
export function FormAlert({ children, tone = "error", title, className }: { children: ReactNode; tone?: "error" | "info" | "warn"; title?: string; className?: string }) {
  return (
    <div className={cx("lc-alert", `is-${tone}`, className)} role={tone === "error" ? "alert" : "status"}>
      <Icon name={tone === "error" ? "alert" : tone === "warn" ? "clock" : "info"} size={18} />
      <div className="lc-alert-body">
        {title && <b>{title}</b>}
        <div>{children}</div>
      </div>
    </div>
  );
}
