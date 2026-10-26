"use client";
/**
 * Audit trail of a case and the before/after JSON viewer (DATA-09, 7.4: every decision is logged).
 */
import { useId, useState } from "react";
import type { AuditEvent } from "@/lib/api/moderation";
import { cx } from "@/lib/cx";
import { formatDateTime } from "@/lib/format";
import { Icon } from "@/components/ui/Icon";
import { PersonLine } from "./Bits";
import { diffJson, formatJsonValue, type DiffChange } from "./jsonDiff";
import { AUDIT_ACTION_LABELS, objectTypeLabel } from "./labels";

const CHANGE_LABEL: Record<DiffChange, string> = {
  added: "добавлено",
  removed: "удалено",
  changed: "изменено",
  same: "без изменений",
};

export function actionLabel(action: string): string {
  return AUDIT_ACTION_LABELS[action] ?? action;
}

/** Side-by-side table «было → стало» for audit JSON; scrolls inside its own box on phones (ATX-19). */
export function JsonDiffView({ before, after, showSame = true }: { before: unknown; after: unknown; showSame?: boolean }) {
  const rows = diffJson(before, after).filter((r) => showSame || r.change !== "same");
  if (!rows.length) return <p className="gv-mod-muted">Данных «до» и «после» нет.</p>;
  return (
    <div className="gv-mod-json" role="region" aria-label="Изменения: было и стало" tabIndex={0}>
      <table>
        <thead>
          <tr>
            <th scope="col">Поле</th>
            <th scope="col">Было</th>
            <th scope="col">Стало</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key || "value"} className={`is-${r.change}`}>
              <th scope="row">
                <code>{r.key || "значение"}</code>
                <small>{CHANGE_LABEL[r.change]}</small>
              </th>
              <td>
                <pre>{formatJsonValue(r.before)}</pre>
              </td>
              <td>
                <pre>{formatJsonValue(r.after)}</pre>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function metaComment(e: AuditEvent): string | null {
  const m = e.metadata ?? {};
  const v = m.comment ?? m.note ?? m.reason;
  return typeof v === "string" && v.trim() ? v : null;
}

function restMetadata(e: AuditEvent): Record<string, unknown> | null {
  const m = { ...(e.metadata ?? {}) };
  delete m.comment;
  delete m.note;
  return Object.keys(m).length ? m : null;
}

export function AuditEventItem({ e, showObject }: { e: AuditEvent; showObject?: boolean }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const comment = metaComment(e);
  const meta = restMetadata(e);
  const hasDetails = e.before != null || e.after != null || meta != null;
  return (
    <li className="gv-mod-event">
      <span className="gv-mod-event-dot" aria-hidden="true" />
      <div className="gv-mod-event-body">
        <div className="gv-mod-event-head">
          <b className={cx(!AUDIT_ACTION_LABELS[e.action] && "is-code")}>{actionLabel(e.action)}</b>
          <time dateTime={e.created_at}>{formatDateTime(e.created_at)}</time>
        </div>
        <div className="gv-mod-event-meta">
          {e.actor ? <PersonLine person={e.actor} size={22} /> : <span className="gv-mod-muted">Система</span>}
          {showObject && (
            <span className="gv-mod-event-object">
              {objectTypeLabel(e.object_type)} · <code title={e.object_id}>{e.object_id.slice(0, 8)}</code>
            </span>
          )}
        </div>
        {comment && <blockquote className="gv-mod-quote">{comment}</blockquote>}
        {hasDetails && (
          <>
            <button type="button" className="feature-link gv-mod-event-toggle" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((v) => !v)}>
              {open ? "Скрыть детали" : "Показать изменения"}
              <Icon name={open ? "chevron-up" : "chevron-down"} size={14} />
            </button>
            <div id={panelId} hidden={!open} className="gv-mod-event-details">
              {open && (
                <>
                  {(e.before != null || e.after != null) && <JsonDiffView before={e.before} after={e.after} />}
                  {meta && (
                    <details className="gv-mod-meta">
                      <summary>Служебные данные</summary>
                      <pre>{formatJsonValue(meta)}</pre>
                    </details>
                  )}
                  <p className="gv-mod-muted gv-mod-small">
                    {e.ip ? `IP ${e.ip}` : "IP не записан"}
                    {e.request_id ? ` · запрос ${e.request_id}` : ""}
                  </p>
                </>
              )}
            </div>
          </>
        )}
      </div>
    </li>
  );
}

export function AuditTrail({ events, showObject, empty = "Записей в журнале пока нет." }: { events: AuditEvent[]; showObject?: boolean; empty?: string }) {
  if (!events.length) return <p className="gv-mod-muted">{empty}</p>;
  return (
    <ol className="gv-mod-events">
      {events.map((e) => (
        <AuditEventItem key={e.id} e={e} showObject={showObject} />
      ))}
    </ol>
  );
}
