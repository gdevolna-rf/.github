/**
 * Screen states (UX-13): every screen shows one of loading / empty / error / no access / offline, plus the
 * success content. Server-safe (no hooks); ErrorState's retry needs a Client parent to pass `onRetry`.
 */
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { isApiError } from "@/lib/api/errors";
import { Button, ButtonLink } from "./Button";
import { Icon, type IconName } from "./Icon";
import { Spinner } from "./Spinner";

export function LoadingState({
  label = "Загружаем…",
  variant = "block",
  lines = 3,
  className,
}: {
  label?: string;
  /** block: spinner + text; skeleton: grey lines (lists/cards); inline: small spinner in a row */
  variant?: "block" | "skeleton" | "inline";
  lines?: number;
  className?: string;
}) {
  if (variant === "skeleton") {
    return (
      <div className={cx("gv-skeleton", className)} role="status" aria-live="polite" aria-busy="true">
        <span className="sr-only">{label}</span>
        {Array.from({ length: lines }, (_, i) => (
          <span key={i} className="gv-skeleton-line" style={{ width: `${92 - ((i * 17) % 40)}%` }} />
        ))}
      </div>
    );
  }
  return (
    <div className={cx("gv-state", "gv-state-loading", variant === "inline" && "is-inline", className)} role="status" aria-live="polite" aria-busy="true">
      <Spinner size={variant === "inline" ? 16 : 26} />
      <span>{label}</span>
    </div>
  );
}

export interface StateAction {
  label: string;
  href?: string;
  onClick?: () => void;
  icon?: IconName;
}

function ActionButton({ action, variant = "pill" }: { action: StateAction; variant?: "pill" | "primary" }) {
  if (action.href) {
    return (
      <ButtonLink href={action.href} variant={variant} iconRight={action.icon ?? "arrow"}>
        {action.label}
      </ButtonLink>
    );
  }
  return (
    <Button variant={variant} onClick={action.onClick} icon={action.icon}>
      {action.label}
    </Button>
  );
}

/**
 * Empty list / no results. Use the illustration for catalogues (prototype «Похоже, все ушли ловить волну!»),
 * `compact` inside cabinet panels (dashed `.gv-ac-empty` box).
 */
export function EmptyState({
  title,
  text,
  action,
  illustration = true,
  compact,
  className,
}: {
  title: string;
  text?: ReactNode;
  action?: StateAction;
  illustration?: boolean;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div className={cx(compact ? "gv-ac-empty gv-empty-compact" : "empty surfer-empty gv-empty", className)}>
      {illustration && !compact && <span className="gv-empty-art" aria-hidden="true" />}
      <h3>{title}</h3>
      {text && <p>{text}</p>}
      {action && <ActionButton action={action} />}
    </div>
  );
}

/** Error with a clear Russian message and a retry (ATX-25). Network errors get the «Нет соединения» wording. */
export function ErrorState({
  error,
  title,
  onRetry,
  retryLabel = "Повторить",
  compact,
  className,
}: {
  error?: unknown;
  title?: string;
  onRetry?: () => void;
  retryLabel?: string;
  compact?: boolean;
  className?: string;
}) {
  const api = isApiError(error) ? error : null;
  const heading =
    title ??
    (api?.isNetwork
      ? "Нет соединения"
      : api?.isNotFound
        ? "Ничего не нашлось"
        : api && api.status >= 500
          ? "Сервис временно недоступен"
          : "Не получилось загрузить");
  const message = api?.message ?? "Что-то пошло не так. Попробуйте ещё раз.";
  return (
    <div className={cx("gv-state gv-state-error", compact && "is-compact", className)} role="alert">
      <span className="gv-state-icon" aria-hidden="true">
        <Icon name={api?.isNetwork ? "wifi-off" : "alert"} size={22} />
      </span>
      <div className="gv-state-body">
        <h3>{heading}</h3>
        <p>{message}</p>
        {api?.requestId && <small className="gv-state-meta">Код для поддержки: {api.requestId}</small>}
      </div>
      {onRetry && (
        <Button variant="pill" icon="refresh" onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
    </div>
  );
}

/** 403 / missing specialty / staff-only screens. Never hint that a client toggle can grant rights (BR-04). */
export function NoAccess({
  title = "Нет доступа",
  text = "У вашего аккаунта нет прав на этот раздел. Если это ошибка, обратитесь к владельцу организации или в поддержку.",
  action,
  className,
}: {
  title?: string;
  text?: ReactNode;
  action?: StateAction;
  className?: string;
}) {
  return (
    <div className={cx("gv-state gv-state-noaccess", className)} role="alert">
      <span className="gv-state-icon" aria-hidden="true">
        <Icon name="lock" size={22} />
      </span>
      <div className="gv-state-body">
        <h3>{title}</h3>
        <p>{text}</p>
      </div>
      {action && <ActionButton action={action} />}
    </div>
  );
}

/** Success confirmation block (form sent, e-mail confirmed…). */
export function SuccessState({ title, text, action, className }: { title: string; text?: ReactNode; action?: StateAction; className?: string }) {
  return (
    <div className={cx("gv-state gv-state-success", className)} role="status">
      <span className="gv-state-icon" aria-hidden="true">
        <Icon name="check" size={22} />
      </span>
      <div className="gv-state-body">
        <h3>{title}</h3>
        {text && <p>{text}</p>}
      </div>
      {action && <ActionButton action={action} variant="primary" />}
    </div>
  );
}
