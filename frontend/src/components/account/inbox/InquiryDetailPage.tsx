"use client";
/**
 * Обращение и чат (`/account/inquiries/{id}`): шапка со статусом и действиями (SHO-05, ATX-28), карточка
 * контекста (MSG-08), детали заявки (ремонт: проблема, фото, сроки — SHO-06), этапы работ, история статусов и
 * сам чат (MSG-03/04/05/06): писать можно до принятия, закрытые обращения — только история.
 */
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { inboxApi, inboxKeys, type InquiryDetail } from "@/lib/api/account-inbox";
import { isApiError } from "@/lib/api/errors";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import { ORGANIZATION_KIND_LABELS, statusLabel } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { useToast } from "@/components/ui/Toast";
import { Avatar } from "@/components/ui/Avatar";
import { StatusBadge } from "@/components/ui/Badge";
import { ClampText } from "@/components/ui/ClampText";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, ErrorState, LoadingState, NoAccess } from "@/components/ui/States";
import { openPrivateMedia, PrivateImage } from "../shared/PrivateImage";
import { viewerTimeZone } from "../shared/utils";
import { ChatView } from "./ChatView";
import { ContextCard } from "./ContextCard";
import { InquiryActions } from "./InquiryActions";
import { Milestones } from "./Milestones";

const DETAIL_LABELS: Record<string, string> = {
  problem: "Что случилось",
  board: "Доска",
  desired_date: "Желаемая дата",
  budget: "Бюджет",
  comment: "Комментарий",
  size: "Размер",
  level: "Уровень",
  date: "Дата",
  dates: "Даты",
  from: "С",
  to: "По",
  seats: "Мест",
  participants: "Участников",
  phone: "Телефон",
  delivery: "Доставка",
  delivery_method: "Способ получения",
  length: "Длина",
  width: "Ширина",
  thickness: "Толщина",
  volume: "Объём",
  fins: "Плавники",
  color: "Цвет",
  quantity: "Количество",
};

function detailValue(key: string, value: unknown, tz: string): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") {
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value, { timeZone: tz });
    if (key === "budget" && /^\d+(\.\d+)?$/.test(value)) return formatMoney(value);
    return value;
  }
  return null;
}

function Details({ inquiry }: { inquiry: InquiryDetail }) {
  const toast = useToast();
  const tz = viewerTimeZone();
  const details = inquiry.details ?? {};
  const params = (details.params && typeof details.params === "object" ? details.params : {}) as Record<string, unknown>;
  const entries = [...Object.entries(details), ...Object.entries(params)]
    .filter(([k]) => !["photos", "photo_ids", "params"].includes(k))
    .map(([k, v]) => [DETAIL_LABELS[k] ?? null, detailValue(k, v, tz)] as const)
    .filter((e): e is readonly [string, string] => Boolean(e[0] && e[1]));
  const photos = details.photos ?? [];
  if (!entries.length && !photos.length && !inquiry.message) return null;
  return (
    <section className="acc-side-block" aria-labelledby="inq-details">
      <h3 id="inq-details">Детали заявки</h3>
      {inquiry.message && (
        <ClampText lines={4} className="acc-inq-message">
          {inquiry.message}
        </ClampText>
      )}
      {entries.length > 0 && (
        <dl className="acc-dl">
          {entries.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
      {photos.length > 0 && (
        <ul className="acc-msg-photos acc-inq-photos" aria-label="Фото к заявке">
          {photos.map((p, i) => (
            <li key={p.id}>
              <button type="button" className="acc-msg-photo" aria-label={`Открыть фото ${i + 1}`} onClick={() => openPrivateMedia(p).catch((err) => toast.error(err))}>
                <PrivateImage media={p} signedUrl={p.signed_thumbnail_url || p.signed_url} alt={`Фото к заявке ${i + 1}`} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function History({ inquiry }: { inquiry: InquiryDetail }) {
  const [open, setOpen] = useState(false);
  const tz = viewerTimeZone();
  if (!inquiry.history.length) return null;
  return (
    <section className="acc-side-block" aria-labelledby="inq-history">
      <h3 id="inq-history">
        <button type="button" className="acc-disclosure" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          История статусов ({inquiry.history.length}) <Icon name={open ? "chevron-up" : "chevron-down"} size={14} />
        </button>
      </h3>
      {open && (
        <ol className="acc-history">
          {inquiry.history.map((h, i) => (
            <li key={`${h.created_at}-${i}`}>
              <StatusBadge domain="inquiry" status={h.to_status} />
              <span>
                {h.actor?.display_name ?? "Система"} · <time dateTime={h.created_at}>{formatDateTime(h.created_at, { timeZone: tz })}</time>
                {h.comment ? <q>{h.comment}</q> : null}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function InquiryDetailPage({ id }: { id: string }) {
  const query = useQuery({ queryKey: inboxKeys.detail(id), queryFn: () => inboxApi.detail(id) });
  const back = (
    <Link href={routes.account.inquiries} className="acc-back">
      <Icon name="arrow-left" size={15} /> Все обращения
    </Link>
  );

  if (query.isPending) {
    return (
      <section className="gv-ac-panel">
        {back}
        <LoadingState variant="skeleton" lines={6} label="Загружаем обращение…" />
      </section>
    );
  }
  if (query.isError && !query.data) {
    const err = query.error;
    return (
      <section className="gv-ac-panel">
        {back}
        {isApiError(err) && err.isNotFound ? (
          <EmptyState compact title="Обращение не найдено" text="Возможно, ссылка устарела или у вас больше нет доступа к этой организации." action={{ label: "К обращениям", href: routes.account.inquiries }} />
        ) : isApiError(err) && err.isForbidden ? (
          <NoAccess />
        ) : (
          <ErrorState error={err} onRetry={() => void query.refetch()} />
        )}
      </section>
    );
  }

  const inq = query.data;
  const party = inq.my_role === "customer" ? inq.provider : inq.counterpart;
  const media = party?.type === "organization" ? party.logo : party?.avatar;
  const closed = inq.status === "declined" || inq.status === "cancelled";
  const showMilestones = inq.kind === "repair" || inq.kind === "custom_order" || inq.milestones.length > 0;
  const tz = viewerTimeZone();
  const reason = inq.status === "declined" ? inq.decline_reason : inq.status === "cancelled" ? inq.cancel_reason : "";

  return (
    <section className="gv-ac-panel acc-thread" aria-labelledby="thread-title">
      {back}
      <header className="acc-thread-head">
        <Avatar media={media ?? null} name={party?.name ?? "?"} size={48} />
        <div className="acc-thread-title">
          <span className="gv-ac-kicker">
            {inq.my_role === "customer" ? "Моя заявка" : "Входящее обращение"} · {inq.kind_label}
          </span>
          <h2 id="thread-title" className="gv-clamp-2" title={inq.subject}>
            {inq.subject || inq.kind_label}
          </h2>
          <p className="acc-thread-sub">
            {inq.my_role === "customer" ? "Исполнитель: " : "Клиент: "}
            {party?.url ? <Link href={party.url}>{party.name}</Link> : (party?.name ?? "—")}
            {inq.provider_organization && inq.my_role === "provider" && (
              <> · {ORGANIZATION_KIND_LABELS[inq.provider_organization.kind as keyof typeof ORGANIZATION_KIND_LABELS] ?? "Организация"} «{inq.provider_organization.name}»</>
            )}
            {" · "}
            <time dateTime={inq.created_at}>от {formatDate(inq.created_at, { timeZone: tz, style: "dayMonth" })}</time>
          </p>
        </div>
        <StatusBadge domain="inquiry" status={inq.status} className="acc-thread-status" />
      </header>

      <div className="acc-thread-bar">
        <InquiryActions inquiry={inq} />
        {inq.status === "completed" && inq.agreed_amount && (
          <span className="acc-amount">
            Сумма сделки: <b>{formatMoney(inq.agreed_amount, inq.currency)}</b>
            {inq.amount_confirmed ? " · подтверждена" : " · не подтверждена"}
          </span>
        )}
      </div>
      {closed && (
        <p className="acc-banner is-muted" role="status">
          <Icon name="info" size={16} />
          <span>
            {statusLabel("inquiry", inq.status)}
            {reason ? `: ${reason}` : "."} Переписка сохранена, новые сообщения отправить нельзя.
          </span>
        </p>
      )}

      <div className="acc-thread-grid">
        <div className="acc-thread-chat">
          {inq.context && <ContextCard context={inq.context} kindLabel={inq.kind_label} compact className="acc-ctx-mobile" />}
          {inq.conversation_id ? (
            <ChatView conversationId={inq.conversation_id} />
          ) : (
            <EmptyState compact title="Переписка недоступна" text="У этого обращения нет чата." />
          )}
        </div>
        <aside className="acc-thread-side" aria-label="О заявке">
          {inq.context && (
            <section className="acc-side-block acc-ctx-desktop" aria-label="Объект обращения">
              <ContextCard context={inq.context} kindLabel={inq.kind_label} />
            </section>
          )}
          <Details inquiry={inq} />
          {showMilestones && <Milestones inquiry={inq} />}
          {inq.bookings.length > 0 && (
            <section className="acc-side-block" aria-labelledby="inq-bookings">
              <h3 id="inq-bookings">Бронирования</h3>
              <ul className="acc-plain-list">
                {inq.bookings.map((b) => (
                  <li key={b.id}>
                    <Link href={routes.account.booking(b.id)}>{formatDateTime(b.starts_at, { timeZone: tz })}</Link>{" "}
                    <StatusBadge domain={b.kind === "rental" ? "rentalBooking" : "booking"} status={b.status} />
                  </li>
                ))}
              </ul>
            </section>
          )}
          <History inquiry={inq} />
        </aside>
      </div>
    </section>
  );
}
