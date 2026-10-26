import Link from "next/link";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { Icon } from "./Icon";

/** Page numbers with ellipsis: 1 … 4 5 [6] 7 8 … 20 */
export function pageWindow(page: number, pageCount: number, around = 1): Array<number | "…"> {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i + 1);
  const out: Array<number | "…"> = [1];
  const start = Math.max(2, page - around);
  const end = Math.min(pageCount - 1, page + around);
  if (start > 2) out.push("…");
  for (let p = start; p <= end; p++) out.push(p);
  if (end < pageCount - 1) out.push("…");
  out.push(pageCount);
  return out;
}

/**
 * Prefer `hrefFor` (real links: crawlable catalogue pages, NAV-05/ATX-32); use `onChange` for in-panel lists.
 * Hidden when there is one page.
 */
export function Pagination({
  page,
  pageCount,
  count,
  pageSize = 20,
  hrefFor,
  onChange,
  ariaLabel = "Страницы",
  className,
}: {
  page: number;
  pageCount?: number;
  /** total items (DRF `count`) — alternative to pageCount */
  count?: number;
  pageSize?: number;
  hrefFor?: (page: number) => string;
  onChange?: (page: number) => void;
  ariaLabel?: string;
  className?: string;
}) {
  const total = pageCount ?? Math.max(1, Math.ceil((count ?? 0) / pageSize));
  if (total <= 1) return null;

  const item = (p: number, content: ReactNode, opts: { label?: string; current?: boolean; disabled?: boolean; key?: string } = {}) => {
    const cls = cx("gv-page", opts.current && "active");
    if (opts.disabled) {
      return (
        <span className={cx(cls, "is-disabled")} aria-disabled="true" aria-label={opts.label}>
          {content}
        </span>
      );
    }
    if (hrefFor) {
      return (
        <Link href={hrefFor(p)} className={cls} aria-label={opts.label} aria-current={opts.current ? "page" : undefined} scroll>
          {content}
        </Link>
      );
    }
    return (
      <button type="button" className={cls} aria-label={opts.label} aria-current={opts.current ? "page" : undefined} onClick={() => onChange?.(p)}>
        {content}
      </button>
    );
  };

  return (
    <nav aria-label={ariaLabel} className={cx("gv-pagination", className)}>
      <ul>
        <li>{item(page - 1, <Icon name="chevron-left" size={16} />, { label: "Предыдущая страница", disabled: page <= 1 })}</li>
        {pageWindow(page, total).map((p, i) => (
          <li key={`${p}-${i}`}>
            {p === "…" ? (
              <span className="gv-page-gap" aria-hidden="true">
                …
              </span>
            ) : (
              item(p, p, { label: `Страница ${p}`, current: p === page })
            )}
          </li>
        ))}
        <li>{item(page + 1, <Icon name="chevron-right" size={16} />, { label: "Следующая страница", disabled: page >= total })}</li>
      </ul>
    </nav>
  );
}
