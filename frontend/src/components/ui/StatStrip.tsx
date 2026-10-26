import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

export interface StatItem {
  label: string;
  value: ReactNode;
  /** small explanation (formula / period), shown as title and for screen readers */
  hint?: string;
  tone?: "default" | "accent" | "muted";
}

/**
 * Compact one-line metrics (MET-02, SHO-01): only on Dashboard / Statistics / Inquiries — not on every tab
 * (MET-01). Scrolls horizontally on phones instead of wrapping into tiles. Values must be server aggregates
 * (MET-07: never fictitious revenue).
 */
export function StatStrip({ items, ariaLabel = "Показатели", className }: { items: StatItem[]; ariaLabel?: string; className?: string }) {
  return (
    <dl className={cx("gv-stat-strip", className)} aria-label={ariaLabel}>
      {items.map((it) => (
        <div key={it.label} className={cx("gv-stat", it.tone && `tone-${it.tone}`)} title={it.hint}>
          <dt>{it.label}</dt>
          <dd>{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}
