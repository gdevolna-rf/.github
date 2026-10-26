import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { getStatus, type StatusDomain, type Tone } from "@/lib/labels";
import { Icon, type IconName } from "./Icon";

/**
 * Tag (prototype `.tag`): neutral info pill. Variants: soft (spot type/level), verified (green), gg (GG Surfer).
 */
export function Tag({
  children,
  variant = "soft",
  icon,
  title,
  className,
}: {
  children: ReactNode;
  variant?: "soft" | "verified" | "gg" | "plain";
  icon?: IconName;
  title?: string;
  className?: string;
}) {
  return (
    <span className={cx("tag", variant !== "plain" && variant, className)} title={title}>
      {icon && <Icon name={icon} size={12} />}
      {children}
    </span>
  );
}

/** Coloured status pill with a tone from the shared vocabulary. */
export function Badge({ tone = "info", children, icon, className }: { tone?: Tone; children: ReactNode; icon?: IconName; className?: string }) {
  return (
    <span className={cx("gv-status", `tone-${tone}`, className)}>
      {icon && <Icon name={icon} size={12} />}
      {children}
    </span>
  );
}

/**
 * Status from labels.ts — the only way to show an inquiry/booking/session/review/proposal status (SHO-05):
 *   <StatusBadge domain="inquiry" status={inquiry.status} />
 */
export function StatusBadge({ domain, status, className }: { domain: StatusDomain; status: string | null | undefined; className?: string }) {
  const def = getStatus(domain, status);
  return (
    <Badge tone={def.tone} className={className}>
      {def.label}
    </Badge>
  );
}

/** Red counter (`.count`), e.g. unread messages. Renders nothing for 0/undefined. "99+" above 99. */
export function CountBadge({ value, className, label }: { value?: number | null; className?: string; label?: string }) {
  if (!value || value <= 0) return null;
  return (
    <span className={cx("count", className)} aria-hidden={label ? undefined : true} aria-label={label}>
      {value > 99 ? "99+" : value}
    </span>
  );
}
