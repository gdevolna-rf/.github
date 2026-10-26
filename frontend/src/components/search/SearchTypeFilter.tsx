/**
 * Result-type filter of /search (NAV-04): links «Все · Споты · Инструкторы …» with totals; the current one has
 * aria-current. Types without results are shown muted and are not links.
 */
import Link from "next/link";
import { cx } from "@/lib/cx";
import { Icon } from "@/components/ui/Icon";
import type { TypeChip } from "./searchModel";
import { TYPE_ICONS } from "./SearchResults";

export function SearchTypeFilter({ chips }: { chips: TypeChip[] }) {
  return (
    <nav className="gv-sr-types" aria-label="Тип результатов">
      <ul>
        {chips.map((chip) => {
          const content = (
            <>
              <Icon name={chip.type ? TYPE_ICONS[chip.type] : "grid"} size={14} />
              <span>{chip.label}</span>
              <span className="gv-sr-type-count">{chip.total}</span>
            </>
          );
          return (
            <li key={chip.type ?? "all"}>
              {chip.total > 0 || chip.active || chip.type === null ? (
                <Link
                  href={chip.href}
                  className={cx("chip gv-sr-type", chip.active && "on")}
                  aria-current={chip.active ? "page" : undefined}
                  scroll={false}
                >
                  {content}
                </Link>
              ) : (
                <span className="chip gv-sr-type is-empty" aria-disabled="true" title="Нет результатов">
                  {content}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
