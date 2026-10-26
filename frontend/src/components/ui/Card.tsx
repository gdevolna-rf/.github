import type { ElementType, ReactNode } from "react";
import { cx } from "@/lib/cx";

/**
 * Soft card surfaces of the prototype:
 *  panel — cabinet panel (`.gv-ac-panel`, white, radius 17)
 *  item  — cabinet card (`.gv-ac-card`, radius 13)
 *  side  — public side card (`.side-card`, «Как пользоваться сайтом»)
 *  glass — translucent public card (`.glass`)
 *  note  — light info box (`.gv-ac-note`)
 */
export type CardVariant = "panel" | "item" | "side" | "glass" | "note";

const CLASS: Record<CardVariant, string> = {
  panel: "gv-ac-panel",
  item: "gv-ac-card",
  side: "side-card",
  glass: "glass",
  note: "gv-ac-note",
};

export function Card({
  as: Tag = "section",
  variant = "panel",
  className,
  children,
  ...rest
}: {
  as?: ElementType;
  variant?: CardVariant;
  className?: string;
  children: ReactNode;
  [key: string]: unknown;
}) {
  return (
    <Tag className={cx(CLASS[variant], className)} {...rest}>
      {children}
    </Tag>
  );
}

/** Panel heading: h2 + optional description and right-side actions. */
export function CardHeader({ title, description, actions, as: H = "h2" }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; as?: "h1" | "h2" | "h3" }) {
  return (
    <div className="gv-card-head">
      <div className="gv-card-head-text">
        <H>{title}</H>
        {description && <p className="gv-ac-desc">{description}</p>}
      </div>
      {actions && <div className="gv-card-head-actions">{actions}</div>}
    </div>
  );
}
