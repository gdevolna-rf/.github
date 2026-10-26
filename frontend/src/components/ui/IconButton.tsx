import Link from "next/link";
import type { ButtonHTMLAttributes } from "react";
import { cx } from "@/lib/cx";
import { CountBadge } from "./Badge";
import { Icon, type IconName } from "./Icon";

interface Common {
  icon: IconName;
  /** Required accessible name (the button has no visible text). */
  label: string;
  /** Red counter in the top-right corner (hidden at 0). */
  badge?: number;
  /** `square` = header icon button (`.square-btn`), `round` = 36px circle on light surfaces. */
  shape?: "square" | "round";
  className?: string;
  iconSize?: number;
}

function accessibleName(label: string, badge?: number) {
  return badge ? `${label}: ${badge}` : label;
}

export function IconButton({
  icon,
  label,
  badge,
  shape = "square",
  className,
  iconSize = 21,
  type = "button",
  ...rest
}: Common & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children">) {
  return (
    <button
      type={type}
      className={cx(shape === "square" ? "square-btn" : "gv-icon-btn", className)}
      aria-label={accessibleName(label, badge)}
      title={label}
      {...rest}
    >
      <Icon name={icon} size={iconSize} />
      <CountBadge value={badge} />
    </button>
  );
}

export function IconLink({ href, icon, label, badge, shape = "square", className, iconSize = 21 }: Common & { href: string }) {
  return (
    <Link
      href={href}
      className={cx(shape === "square" ? "square-btn" : "gv-icon-btn", className)}
      aria-label={accessibleName(label, badge)}
      title={label}
    >
      <Icon name={icon} size={iconSize} />
      <CountBadge value={badge} />
    </Link>
  );
}
