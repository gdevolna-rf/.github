"use client";
/** Context card of the inquiry's object (MSG-08): board model / variant / repair / lesson / program / rental. */
import Link from "next/link";
import type { ContextCard as Ctx } from "@/lib/api/account-inbox";
import { cx } from "@/lib/cx";
import { Icon, type IconName } from "@/components/ui/Icon";

const TYPE_LABEL: Record<string, string> = {
  board_model: "Модель доски",
  board_variant: "Размер доски",
  inventory_item: "Снаряжение",
  instructor_offer: "Занятие с инструктором",
  school_program: "Программа школы",
  lesson_session: "Занятие",
  organization: "Организация",
  account: "Исполнитель",
};
const TYPE_ICON: Record<string, IconName> = {
  board_model: "board",
  board_variant: "ruler",
  inventory_item: "box",
  instructor_offer: "clover",
  school_program: "school",
  lesson_session: "calendar",
  organization: "school",
  account: "user",
};

export function ContextCard({ context, kindLabel, compact, className }: { context: Ctx; kindLabel?: string; compact?: boolean; className?: string }) {
  const body = (
    <>
      <span className="acc-ctx-media" aria-hidden="true">
        {context.image ? <img src={context.image} alt="" loading="lazy" /> : <Icon name={TYPE_ICON[context.type] ?? "brief"} size={22} />}
      </span>
      <span className="acc-ctx-text">
        <small>{kindLabel ? `${kindLabel} · ${TYPE_LABEL[context.type] ?? "Объект"}` : (TYPE_LABEL[context.type] ?? "Объект обращения")}</small>
        <b className="gv-clamp-2" title={context.title}>
          {context.title}
        </b>
        {context.subtitle && !compact && <span className="gv-clamp-2">{context.subtitle}</span>}
      </span>
      {context.url && <Icon name="arrow" size={15} className="acc-ctx-arrow" />}
    </>
  );
  if (context.url) {
    return (
      <Link href={context.url} className={cx("acc-ctx", compact && "is-compact", className)} aria-label={`${TYPE_LABEL[context.type] ?? "Объект"}: ${context.title} — открыть страницу`}>
        {body}
      </Link>
    );
  }
  return <div className={cx("acc-ctx", compact && "is-compact", className)}>{body}</div>;
}
