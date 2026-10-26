"use client";
/**
 * URL-driven section tabs for the instructor/school cabinets (each tab is a page — NAV-05). Like the kit's
 * NavTabs, but supports an `exact` root item (overview) and keeps the active tab scrolled into view on phones
 * (CABINET_NOTES F5). `variant="pills"` reproduces the school pane's `.gv-ac-mini-tabs`.
 */
import Link from "next/link";
import { useEffect, useRef } from "react";
import { cx } from "@/lib/cx";
import { CountBadge } from "@/components/ui/Badge";
import { Icon, type IconName } from "@/components/ui/Icon";

export interface CabinetTab {
  href: string;
  label: string;
  icon?: IconName;
  exact?: boolean;
  badge?: number;
}

export function isTabActive(tab: Pick<CabinetTab, "href" | "exact">, pathname: string): boolean {
  if (tab.exact) return pathname === tab.href || pathname === `${tab.href}/`;
  return pathname === tab.href || pathname.startsWith(`${tab.href}/`);
}

export function CabinetTabs({ items, current, ariaLabel, variant = "segmented" }: { items: CabinetTab[]; current: string; ariaLabel: string; variant?: "segmented" | "pills" }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = ref.current;
    const active = el?.querySelector<HTMLElement>("[aria-current='page']");
    if (el && active && el.scrollWidth > el.clientWidth) active.scrollIntoView?.({ block: "nearest", inline: "center" });
  }, [current]);
  return (
    <nav ref={ref} aria-label={ariaLabel} className={cx(variant === "pills" ? "gv-ac-mini-tabs lc-pills" : "gv-tabs lc-tabs")}>
      {items.map((t) => {
        const active = isTabActive(t, current);
        return (
          <Link key={t.href} href={t.href} className={cx(variant === "pills" ? "lc-pill" : "gv-tab-btn", active && "active")} aria-current={active ? "page" : undefined}>
            {t.icon && <Icon name={t.icon} size={15} />}
            <span>{t.label}</span>
            <CountBadge value={t.badge} className="gv-tab-count" />
          </Link>
        );
      })}
    </nav>
  );
}
