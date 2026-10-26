"use client";
/**
 * Board/shaper actions that depend on the viewer (SHP-11, AT-03): SSR renders the guest view, so «own» is derived
 * on the client from the session's memberships (or the server's `is_own` when the list was fetched with cookies).
 * This is UX only — the server refuses self-inquiries anyway (`self_inquiry`), and InquiryDialog shows that refusal.
 */
import Link from "next/link";
import { Button, Icon } from "@/components/ui";
import { InquiryButton } from "@/components/commerce/InquiryDialog";
import { useMe } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { formatMoney } from "@/lib/format";
import { routes } from "@/lib/routes";

/** True when the logged-in account is an active member of the workshop (organization) `workshopId`. */
export function useIsOwnWorkshop(workshopId: string | null | undefined, serverIsOwn = false): boolean {
  const { me } = useMe();
  if (serverIsOwn) return true;
  if (!me || !workshopId) return false;
  return me.organizations.some((o) => o.id === workshopId && o.kind === "workshop");
}

export interface OrderTarget {
  modelId: string;
  modelName: string;
  workshopId: string;
  workshopName: string;
  isOwn?: boolean;
  /** Ordering a concrete size variant (variants table). */
  variant?: { id: string; sku: string; label?: string; price?: string | null; currency?: string } | null;
}

export function BoardOrderButton({
  target,
  label = "Заказать доску",
  className,
  size,
  variant = "primary",
}: {
  target: OrderTarget;
  label?: string;
  className?: string;
  size?: "sm" | "md";
  variant?: "primary" | "pill" | "soft";
}) {
  const own = useIsOwnWorkshop(target.workshopId, target.isOwn);
  if (own) {
    return (
      <Button variant={variant} size={size} className={cx("catalog-buy", className)} disabled title="Собственную доску заказать нельзя">
        Это ваша доска
      </Button>
    );
  }
  const v = target.variant;
  const context = v
    ? `Модель «${target.modelName}», вариант ${[v.label, v.sku].filter(Boolean).join(" · ")}${v.price ? ` · ${formatMoney(v.price, v.currency)}` : ""}`
    : `Модель «${target.modelName}» · мастерская ${target.workshopName}`;
  return (
    <InquiryButton
      kind="board_purchase"
      targetType={v ? "board_variant" : "board_model"}
      targetId={v ? v.id : target.modelId}
      providerName={target.workshopName}
      title={`Заказать: ${target.modelName}`}
      contextLabel={context}
      variant={variant}
      size={size}
      icon="board"
      className={cx("catalog-buy", className)}
    >
      {label}
    </InquiryButton>
  );
}

/**
 * Profile actions (SHP-10/11, SHO-06): «Написать», «Ремонт» (only when the workshop repairs), «Индивидуальный заказ».
 * On the own workshop the actions are replaced by a link to the shaper cabinet.
 */
export function ShaperActions({
  workshopId,
  workshopName,
  doesRepair,
  acceptsCustom = true,
  isOwn,
  layout = "column",
}: {
  workshopId: string;
  workshopName: string;
  doesRepair: boolean;
  acceptsCustom?: boolean;
  isOwn?: boolean;
  layout?: "column" | "row";
}) {
  const own = useIsOwnWorkshop(workshopId, isOwn);
  if (own) {
    return (
      <div className={cx("gv-profile-actions", layout === "row" && "is-row")}>
        <Button variant="soft" disabled title="Нельзя писать самому себе">
          Это ваша мастерская
        </Button>
        <Link href={routes.account.shaper} className="secondary gv-own-link">
          <Icon name="settings" size={15} /> Управлять в кабинете
        </Link>
      </div>
    );
  }
  return (
    <div className={cx("gv-profile-actions", layout === "row" && "is-row")}>
      <InquiryButton kind="general" providerOrganizationId={workshopId} providerName={workshopName} title={`Написать: ${workshopName}`} icon="chat">
        Написать шейперу
      </InquiryButton>
      {acceptsCustom && (
        <InquiryButton
          kind="custom_order"
          providerOrganizationId={workshopId}
          providerName={workshopName}
          detailsVariant="custom_order"
          title={`Индивидуальный заказ: ${workshopName}`}
          variant="pill"
          icon="ruler"
        >
          Индивидуальный заказ
        </InquiryButton>
      )}
      {doesRepair && (
        <InquiryButton
          kind="repair"
          providerOrganizationId={workshopId}
          providerName={workshopName}
          detailsVariant="repair"
          title={`Ремонт доски: ${workshopName}`}
          variant="pill"
          icon="settings"
        >
          Ремонт
        </InquiryButton>
      )}
    </div>
  );
}
