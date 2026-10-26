"use client";
/**
 * Rows of the «Обращения» inbox (SHAPERS_SCREENS §5.4 `.request-item` / `.gv-inbox-row`): counterpart, kind ·
 * subject, last message preview, time, status badge, real unread count «N новых» (MSG-06/07) and actions.
 */
import Link from "next/link";
import type { ConversationListItem, InquiryListItem } from "@/lib/api/account-inbox";
import { cx } from "@/lib/cx";
import { formatRelative, plural } from "@/lib/format";
import { ORGANIZATION_KIND_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { Avatar } from "@/components/ui/Avatar";
import { StatusBadge } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { previewText, viewerTimeZone } from "../shared/utils";
import { InquiryActions } from "./InquiryActions";

export function UnreadPill({ count }: { count: number }) {
  if (!count) return null;
  return (
    <span className="acc-unread" aria-label={`${count} ${plural(count, ["новое сообщение", "новых сообщения", "новых сообщений"])}`}>
      <span aria-hidden="true">{count > 99 ? "99+" : count} {plural(count, ["новое", "новых", "новых"])}</span>
    </span>
  );
}

export function InquiryRow({ item }: { item: InquiryListItem }) {
  const party = item.counterpart;
  const media = party?.type === "organization" ? party.logo : party?.avatar;
  const time = item.last_message?.created_at ?? item.updated_at;
  const outgoing = item.my_role === "customer";
  const href = routes.account.inquiry(item.id);
  return (
    <li className={cx("acc-row", item.unread_count > 0 && "is-unread")}>
      <Avatar media={media ?? null} name={party?.name ?? "?"} size={42} />
      <div className="acc-row-main">
        <div className="acc-row-top">
          <Link href={href} className="acc-row-title">
            {outgoing && <Icon name="send" size={13} className="acc-row-dir" title="Исходящее" />}
            <span className="gv-clamp-1">{party?.name ?? "Собеседник"}</span>
          </Link>
          <time className="acc-row-time" dateTime={time}>
            {formatRelative(time, { timeZone: viewerTimeZone() })}
          </time>
        </div>
        <p className="acc-row-sub gv-clamp-1" title={item.subject}>
          {item.kind_label}
          {item.subject ? ` · ${item.subject}` : ""}
          {item.provider_organization && !outgoing ? ` · ${item.provider_organization.name}` : ""}
        </p>
        <p className={cx("acc-row-preview gv-clamp-1", item.unread_count > 0 && "is-strong")}>{previewText(item.last_message)}</p>
        <div className="acc-row-meta">
          <StatusBadge domain="inquiry" status={item.status} />
          <UnreadPill count={item.unread_count} />
          {item.provider_organization && outgoing && (
            <span className="acc-row-org">
              {ORGANIZATION_KIND_LABELS[item.provider_organization.kind as keyof typeof ORGANIZATION_KIND_LABELS] ?? "Организация"}
            </span>
          )}
        </div>
      </div>
      <div className="acc-row-actions">
        <InquiryActions inquiry={item} size="sm" />
        <Link href={href} className="gv-ac-btn acc-chat-link" aria-label={`Открыть чат: ${party?.name ?? "обращение"}`}>
          <Icon name="chat" size={15} /> Чат
        </Link>
      </div>
    </li>
  );
}

export function ConversationRow({ item, href }: { item: ConversationListItem; href: string }) {
  const party = item.counterpart;
  const time = item.last_message?.created_at ?? item.last_message_at ?? item.created_at;
  return (
    <li className={cx("acc-row is-direct", item.unread_count > 0 && "is-unread")}>
      <Avatar media={party?.avatar ?? null} name={party?.name ?? "?"} size={42} />
      <div className="acc-row-main">
        <div className="acc-row-top">
          <Link href={href} className="acc-row-title">
            <span className="gv-clamp-1">{party?.name ?? "Участник GG Surfer"}</span>
          </Link>
          <time className="acc-row-time" dateTime={time}>
            {formatRelative(time, { timeZone: viewerTimeZone() })}
          </time>
        </div>
        <p className={cx("acc-row-preview gv-clamp-1", item.unread_count > 0 && "is-strong")}>{previewText(item.last_message)}</p>
        <div className="acc-row-meta">
          <span className="tag gg">GG Surfer</span>
          {item.unread_count > 0 ? <UnreadPill count={item.unread_count} /> : <span className="acc-read">Прочитано</span>}
        </div>
      </div>
    </li>
  );
}
