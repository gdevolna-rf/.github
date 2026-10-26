import { cx } from "@/lib/cx";
import { Icon } from "./Icon";

export type CertificateStatus = "none" | "uploaded" | "verified" | "rejected" | "revoked";

/**
 * Instructor certificate (INS-03, TRUST-03, BR-07): three visually distinct states.
 *  none     → dashed muted outline «Сертификат не указан» (hidden in catalogue cards with hideNone)
 *  uploaded → blue-grey with a clock «Сертификат загружен» — on moderation, NOT verified
 *  verified → green with a check «Сертификат проверен» — only after a moderator decision
 * rejected/revoked are shown to the owner only (cabinet); publicly they render like "none".
 */
export function CertificateBadge({
  status,
  compact,
  hideNone,
  audience = "public",
  className,
}: {
  status: CertificateStatus | string | null | undefined;
  compact?: boolean;
  hideNone?: boolean;
  /** "owner" also shows rejected/revoked with their own wording. */
  audience?: "public" | "owner";
  className?: string;
}) {
  let s = (status || "none") as CertificateStatus;
  if (audience === "public" && (s === "rejected" || s === "revoked")) s = "none";
  if (s === "none" && hideNone) return null;

  if (s === "verified") {
    return (
      <span className={cx("tag verified gv-cert gv-cert-verified", className)} title="Документ проверен модератором ГДеволна">
        <Icon name="shield" size={13} />
        {compact ? "Проверен" : "Сертификат проверен"}
      </span>
    );
  }
  if (s === "uploaded") {
    return (
      <span className={cx("tag gv-cert gv-cert-uploaded", className)} title="Документ загружен и ждёт проверки модератором — это ещё не подтверждение">
        <Icon name="clock" size={13} />
        {compact ? "На проверке" : "Сертификат загружен"}
      </span>
    );
  }
  if (s === "rejected" || s === "revoked") {
    return (
      <span className={cx("tag gv-cert gv-cert-rejected", className)}>
        <Icon name="alert" size={13} />
        {s === "rejected" ? "Сертификат отклонён" : "Сертификат отозван"}
      </span>
    );
  }
  return (
    <span className={cx("tag gv-cert gv-cert-none", className)} title="Сертификат необязателен">
      {compact ? "Без сертификата" : "Сертификат не указан"}
    </span>
  );
}
