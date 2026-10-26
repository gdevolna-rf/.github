"use client";
/**
 * «Было / сейчас / предлагается» for a spot proposal (TRUST-04, F08, AT-07). Compass fields (wind / swell)
 * are drawn as roses so the moderator sees the direction change at a glance; text keeps line breaks.
 * Without `current` (author's view) only «было → предлагается» is shown.
 */
import type { SpotDiffItem } from "@/lib/api/moderation";
import { cx } from "@/lib/cx";
import { compassCodes, type Choice } from "@/lib/labels";
import { CompassRose } from "@/components/ui/CompassRose";
import { Icon } from "@/components/ui/Icon";

function asCompass(v: unknown): Choice[] {
  return Array.isArray(v) ? (v as Choice[]) : [];
}

function Value({ item, value, display, which }: { item: SpotDiffItem; value: unknown; display: string; which: "old" | "current" | "new" }) {
  if (item.kind === "compass") {
    const kind = item.field.includes("swell") ? "swell" : "wind";
    const codes = compassCodes(asCompass(value));
    return (
      <div className="gv-mod-rose">
        <CompassRose bare kind={kind} directions={codes} size={132} />
        <span className="gv-mod-diff-text">{display || "—"}</span>
      </div>
    );
  }
  return <span className={cx("gv-mod-diff-text", which === "new" && "is-new")}>{display || "—"}</span>;
}

export function SpotDiff({ items, showCurrent = true }: { items: SpotDiffItem[]; showCurrent?: boolean }) {
  if (!items.length) return <p className="gv-mod-muted">Изменений нет.</p>;
  const withCurrent = showCurrent && items.some((i) => i.current !== undefined);
  return (
    <ul className={cx("gv-mod-diff", withCurrent && "has-current")}>
      {items.map((item) => (
        <li key={item.field} className="gv-mod-diff-row">
          <div className="gv-mod-diff-field">
            <b>{item.label}</b>
            {withCurrent && item.changed_since_submission && (
              <span className="gv-mod-flag" title="Значение на карточке изменилось после подачи предложения">
                <Icon name="alert" size={13} /> Карточка изменилась после подачи
              </span>
            )}
          </div>
          <div className="gv-mod-diff-cols">
            <div className="gv-mod-diff-col is-old">
              <span className="gv-mod-diff-head">Было при подаче</span>
              <Value item={item} value={item.old} display={item.old_display} which="old" />
            </div>
            {withCurrent && (
              <div className={cx("gv-mod-diff-col is-current", item.changed_since_submission && "is-warn")}>
                <span className="gv-mod-diff-head">Сейчас на карточке</span>
                <Value item={item} value={item.current} display={item.current_display ?? ""} which="current" />
              </div>
            )}
            <div className="gv-mod-diff-col is-new">
              <span className="gv-mod-diff-head">Предлагается</span>
              <Value item={item} value={item.new} display={item.new_display} which="new" />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
