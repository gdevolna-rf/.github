"use client";
/**
 * Small building blocks shared by moderation screens: person line (avatar + name → account review),
 * SLA marker, definition list, kind chip, signed private media grid with a viewer.
 */
import Link from "next/link";
import { useState, type ReactNode } from "react";
import type { ModeratorMedia, CaseKind } from "@/lib/api/moderation";
import type { Media, PublicAccount } from "@/lib/api/types";
import { cx } from "@/lib/cx";
import { formatDateTime } from "@/lib/format";
import { choiceCode, choiceLabel, type Choice } from "@/lib/labels";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { CASE_KIND_ICONS, CASE_KIND_LABELS } from "./labels";
import { modRoutes } from "./routes";
import { slaInfo } from "./sla";

export function PersonLine({ person, role, link = true, size = 32 }: { person: PublicAccount | null | undefined; role?: string; link?: boolean; size?: number }) {
  if (!person) return <span className="gv-mod-person is-empty">—</span>;
  const name = person.is_deleted ? "Удалённый аккаунт" : person.display_name || "Участник";
  const body = (
    <>
      <Avatar media={person.avatar} name={name} size={size} />
      <span className="gv-mod-person-text">
        <b>{name}</b>
        {(role || person.handle) && <small>{[role, person.handle ? `@${person.handle}` : null].filter(Boolean).join(" · ")}</small>}
      </span>
    </>
  );
  if (!link || person.is_deleted) return <span className="gv-mod-person">{body}</span>;
  return (
    <Link className="gv-mod-person" href={modRoutes.account(person.id)} title="Сводка по аккаунту">
      {body}
    </Link>
  );
}

export function SlaBadge({ c, now }: { c: { due_at: string | null; is_overdue?: boolean; status: unknown }; now?: Date }) {
  const sla = slaInfo(c, now);
  if (sla.tone === "none") return null;
  return (
    <span className={cx("gv-mod-sla", `is-${sla.tone}`)} title={sla.long}>
      <Icon name={sla.tone === "overdue" ? "alert" : "clock"} size={13} />
      <span>{sla.text}</span>
      <span className="sr-only">. {sla.long}</span>
    </span>
  );
}

export function KindChip({ kind }: { kind: Choice | null | undefined }) {
  const code = (choiceCode(kind) ?? "complaint") as CaseKind;
  return (
    <span className={cx("gv-mod-kind", `kind-${code}`)}>
      <Icon name={CASE_KIND_ICONS[code] ?? "info"} size={14} />
      {choiceLabel(kind, CASE_KIND_LABELS) || "Кейс"}
    </span>
  );
}

/** <dl> of label/value pairs; empty values are skipped. */
export function Facts({ items, className }: { items: Array<[string, ReactNode]>; className?: string }) {
  const visible = items.filter(([, v]) => v !== null && v !== undefined && v !== "" && v !== false);
  if (!visible.length) return null;
  return (
    <dl className={cx("gv-mod-facts", className)}>
      {visible.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function When({ value, prefix }: { value: string | null | undefined; prefix?: string }) {
  if (!value) return null;
  return (
    <time dateTime={value}>
      {prefix ? `${prefix} ` : ""}
      {formatDateTime(value)}
    </time>
  );
}

function isImage(m: Pick<Media, "kind" | "content_type">) {
  return m.kind === "image" || (m.content_type || "").startsWith("image/");
}

function urlOf(m: ModeratorMedia | Media): string | null {
  return ("signed_url" in m && m.signed_url) || m.url || null;
}

/**
 * Evidence / review photos / attachments. Private files come with a short-lived `signed_url` (2 min):
 * when a link has expired the image fails to load → «Обновить ссылки» refetches the case.
 */
export function MediaGrid({
  items,
  label,
  onExpired,
  empty = "Файлов нет",
}: {
  items: Array<ModeratorMedia | Media>;
  label: string;
  onExpired?: () => void;
  empty?: string;
}) {
  const [open, setOpen] = useState<ModeratorMedia | Media | null>(null);
  const [failed, setFailed] = useState(false);
  if (!items.length) return <p className="gv-mod-muted">{empty}</p>;
  return (
    <>
      <ul className="gv-mod-media" aria-label={label}>
        {items.map((m, i) => {
          const url = urlOf(m);
          const thumb = m.thumbnail_url || url;
          const name = m.original_filename || `Файл ${i + 1}`;
          return (
            <li key={m.id}>
              {isImage(m) && url ? (
                <button type="button" className="gv-mod-media-btn" onClick={() => setOpen(m)} aria-label={`Открыть фото «${name}»`}>
                  <img src={thumb ?? url} alt="" loading="lazy" onError={() => setFailed(true)} />
                </button>
              ) : url ? (
                <a className="gv-mod-media-doc" href={url} target="_blank" rel="noreferrer noopener">
                  <Icon name="paperclip" size={20} />
                  <span>{name}</span>
                  <small>Открыть в новой вкладке</small>
                </a>
              ) : (
                <span className="gv-mod-media-doc is-missing">
                  <Icon name="image" size={20} />
                  <span>{name}</span>
                  <small>{m.status === "ready" ? "Ссылка недоступна" : "Файл обрабатывается"}</small>
                </span>
              )}
            </li>
          );
        })}
      </ul>
      {failed && onExpired && (
        <p className="gv-mod-muted">
          Ссылки на закрытые файлы действуют 2 минуты.{" "}
          <button
            type="button"
            className="feature-link"
            onClick={() => {
              setFailed(false);
              onExpired();
            }}
          >
            Обновить ссылки
          </button>
        </p>
      )}
      <Modal open={Boolean(open)} onClose={() => setOpen(null)} title={open?.original_filename || "Фото"} size="xl">
        {open && urlOf(open) && (
          <div className="gv-mod-viewer">
            <img src={urlOf(open)!} alt={open.alt_text || open.original_filename || "Фото"} onError={() => onExpired?.()} />
            <a className="feature-link" href={urlOf(open)!} target="_blank" rel="noreferrer noopener">
              Открыть оригинал <Icon name="external" size={14} />
            </a>
          </div>
        )}
      </Modal>
    </>
  );
}

export function SectionTitle({ children, icon, actions }: { children: ReactNode; icon?: Parameters<typeof Icon>[0]["name"]; actions?: ReactNode }) {
  return (
    <div className="gv-mod-section-title">
      <h3>
        {icon && <Icon name={icon} size={17} />}
        {children}
      </h3>
      {actions}
    </div>
  );
}

export function RefreshButton({ onClick, loading }: { onClick: () => void; loading?: boolean }) {
  return (
    <Button variant="soft" size="sm" icon="refresh" onClick={onClick} loading={loading}>
      Обновить
    </Button>
  );
}
