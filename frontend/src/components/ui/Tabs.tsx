"use client";
import Link from "next/link";
import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import { CountBadge } from "./Badge";

export interface TabItem {
  id: string;
  label: ReactNode;
  badge?: number;
  disabled?: boolean;
}

/**
 * In-page tabs (WAI-ARIA tabs pattern): role=tablist/tab/tabpanel, roving tabindex, arrows/Home/End,
 * automatic activation. The strip scrolls horizontally on phones instead of cutting the last tab
 * (prototype bug: «Отзывы ★» cut at 390px). Pair with <TabPanel>.
 */
export function Tabs({
  items,
  value,
  onChange,
  ariaLabel,
  idPrefix,
  className,
}: {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  ariaLabel: string;
  /** Unique per page; links tabs and panels (`${idPrefix}-tab-${id}` / `${idPrefix}-panel-${id}`). */
  idPrefix: string;
  className?: string;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const enabled = items.filter((t) => !t.disabled);

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    const idx = enabled.findIndex((t) => t.id === value);
    let next = -1;
    if (e.key === "ArrowRight") next = (idx + 1) % enabled.length;
    else if (e.key === "ArrowLeft") next = (idx - 1 + enabled.length) % enabled.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = enabled.length - 1;
    if (next < 0) return;
    e.preventDefault();
    const id = enabled[next].id;
    onChange(id);
    refs.current[id]?.focus();
    refs.current[id]?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  };

  return (
    <div role="tablist" aria-label={ariaLabel} className={cx("gv-tabs", className)}>
      {items.map((t) => {
        const selected = t.id === value;
        return (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[t.id] = el;
            }}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${t.id}`}
            aria-selected={selected}
            aria-controls={`${idPrefix}-panel-${t.id}`}
            tabIndex={selected ? 0 : -1}
            disabled={t.disabled}
            className={cx("gv-tab-btn", selected && "active")}
            onClick={() => onChange(t.id)}
            onKeyDown={onKeyDown}
          >
            <span>{t.label}</span>
            <CountBadge value={t.badge} className="gv-tab-count" />
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({ idPrefix, id, value, children, className }: { idPrefix: string; id: string; value: string; children: ReactNode; className?: string }) {
  const active = id === value;
  return (
    <div
      role="tabpanel"
      id={`${idPrefix}-panel-${id}`}
      aria-labelledby={`${idPrefix}-tab-${id}`}
      hidden={!active}
      tabIndex={0}
      className={className}
    >
      {active ? children : null}
    </div>
  );
}

/**
 * Same look for URL-driven sections (sub-routes like /account/instructor/schedule): a <nav> of links with
 * aria-current, NOT role=tab (each item is a separate page, deep-linkable — NAV-05).
 */
export function NavTabs({ items, current, ariaLabel, className }: { items: Array<{ href: string; label: ReactNode; badge?: number }>; current: string; ariaLabel: string; className?: string }) {
  return (
    <nav aria-label={ariaLabel} className={cx("gv-tabs", className)}>
      {items.map((t) => {
        const active = current === t.href || current.startsWith(`${t.href}/`);
        return (
          <Link key={t.href} href={t.href} className={cx("gv-tab-btn", active && "active")} aria-current={active ? "page" : undefined}>
            <span>{t.label}</span>
            <CountBadge value={t.badge} className="gv-tab-count" />
          </Link>
        );
      })}
    </nav>
  );
}
