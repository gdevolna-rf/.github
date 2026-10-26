"use client";
/**
 * One lesson session (school or private) for the cabinets: time in the session's own zone with the zone label,
 * status, school/private tag, spot, instructor, capacity and free seats (SCH-05, ATX-14), pending requests,
 * reschedule / cancel reasons, participants and an action row.
 */
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { formatMoney, isoDateInZone, plural, WORDS } from "@/lib/format";
import type { BookingsSummary, LessonSession, SessionParticipant } from "@/lib/api/learningCabinet";
import { Avatar } from "@/components/ui/Avatar";
import { StatusBadge, Tag } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { formatDay, timeRange, tzLabel } from "./time";

export interface SessionCardProps {
  session: LessonSession;
  /** school view: who teaches */
  showInstructor?: boolean;
  /** instructor view: which school (or «Частное занятие») */
  showKind?: boolean;
  requestedCount?: number;
  summary?: BookingsSummary;
  waitlistCount?: number;
  actions?: ReactNode;
  children?: ReactNode;
  headingLevel?: "h3" | "h4";
  className?: string;
}

export function SessionCard({
  session: s,
  showInstructor,
  showKind = true,
  requestedCount,
  summary,
  waitlistCount,
  actions,
  children,
  headingLevel: H = "h3",
  className,
}: SessionCardProps) {
  const tz = s.timezone;
  const day = isoDateInZone(s.starts_at, tz);
  const requested = requestedCount ?? summary?.requested ?? 0;
  return (
    <article className={cx("lc-session", `is-${s.status}`, className)}>
      <div className="lc-session-when">
        <strong>{timeRange(s.starts_at, s.ends_at, tz)}</strong>
        <span>{formatDay(day, "weekday")}</span>
        <small title={`Часовой пояс места: ${tz}`}>
          <Icon name="clock" size={12} /> {tzLabel(tz, s.starts_at)}
        </small>
      </div>
      <div className="lc-session-main">
        <div className="lc-session-tags">
          <StatusBadge domain="session" status={s.status} />
          {showKind &&
            (s.kind === "school" && s.organization ? (
              <Tag icon="school" title="Занятие школы">
                {s.organization.name}
              </Tag>
            ) : (
              <Tag icon="user">Частное занятие</Tag>
            ))}
          {s.is_full && s.status === "scheduled" && <Tag variant="plain" className="lc-tag-full">Мест нет</Tag>}
        </div>
        <H className="lc-session-title gv-clamp-2" title={s.title}>
          {s.title}
        </H>
        <ul className="lc-session-meta">
          <li>
            <Icon name="map-pin" size={14} />
            {s.spot ? s.spot.name : "Спот не указан"}
          </li>
          {showInstructor && (
            <li>
              <Icon name="clover" size={14} />
              {s.instructor ? s.instructor.display_name : <span className="lc-warn-text">Инструктор не назначен</span>}
            </li>
          )}
          <li>
            <Icon name="users" size={14} />
            Записано {s.seats_taken} из {s.capacity} · {s.free_seats > 0 ? `свободно ${s.free_seats}` : "свободных мест нет"}
          </li>
          {s.price ? (
            <li>
              <Icon name="sparkle" size={14} />
              {formatMoney(s.price, s.currency)}
            </li>
          ) : null}
        </ul>
        {(requested > 0 || (waitlistCount ?? 0) > 0) && (
          <p className="lc-session-pending">
            {requested > 0 && (
              <span>
                <Icon name="bell" size={13} /> Ждут подтверждения: {requested} {plural(requested, ["запись", "записи", "записей"])}
              </span>
            )}
            {(waitlistCount ?? 0) > 0 && (
              <span>
                <Icon name="users" size={13} /> В листе ожидания: {waitlistCount}
              </span>
            )}
          </p>
        )}
        {s.status === "scheduled" && s.reschedule_reason ? (
          <p className="lc-session-note">
            <Icon name="refresh" size={13} /> Перенесено: {s.reschedule_reason}
          </p>
        ) : null}
        {s.status === "cancelled" && s.cancel_reason ? (
          <p className="lc-session-note is-cancel">
            <Icon name="alert" size={13} /> Причина отмены: {s.cancel_reason}
          </p>
        ) : null}
        {children}
        {actions ? <div className="lc-session-actions">{actions}</div> : null}
      </div>
    </article>
  );
}

/** Participants of a session (instructor schedule / school session details). */
export function ParticipantList({ participants, open }: { participants: SessionParticipant[]; open?: boolean }) {
  if (!participants.length) {
    return <p className="lc-participants-empty">Подтверждённых участников пока нет.</p>;
  }
  const seats = participants.reduce((n, p) => n + (p.seats || 1), 0);
  return (
    <details className="lc-participants" open={open}>
      <summary>
        Участники · {participants.length} ({seats} {plural(seats, WORDS.seat)})
      </summary>
      <ul>
        {participants.map((p) => (
          <li key={p.booking_id}>
            <Avatar media={p.customer?.avatar} name={p.name} size={28} />
            <span className="lc-participant-name gv-clamp-1" title={p.name}>
              {p.name}
              {p.seats > 1 ? ` × ${p.seats}` : ""}
            </span>
            {p.participant_is_minor && <Tag variant="plain" className="lc-tag-minor">Несовершеннолетний</Tag>}
            <StatusBadge domain="booking" status={p.status} />
          </li>
        ))}
      </ul>
    </details>
  );
}
