"use client";
/**
 * /moderation/audit — immutable audit log (DATA-09, 5.3): filters by object type/id, actor, exact action or
 * action group, period; each event expands to a before/after diff. Filters are URL parameters.
 */
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { modKeys, moderationApi, type AuditParams } from "@/lib/api/moderation";
import { formatNumber, plural } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { Select, TextInput } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { QueryState } from "@/components/ui/QueryState";
import { EmptyState } from "@/components/ui/States";
import { AuditTrail } from "./AuditTrail";
import { useModQuery } from "./hooks";
import { AUDIT_ACTION_PREFIXES, AUDIT_OBJECT_TYPES } from "./labels";
import { modRoutes } from "./routes";

const PAGE_SIZE = 30;
const FIELDS = ["object_type", "object_id", "actor", "action", "action_prefix", "from", "to"] as const;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** "2026-10-01" → start/end of that day in the browser's zone, ISO. */
export function dayBoundary(date: string, end: boolean): string | undefined {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return undefined;
  const d = new Date(`${date}T${end ? "23:59:59.999" : "00:00:00"}`);
  return Number.isNaN(d.getTime()) ? undefined : d.toISOString();
}

export function readAuditParams(search: URLSearchParams): AuditParams {
  const get = (k: string) => search.get(k)?.trim() || undefined;
  const page = Number(get("page") || 1);
  const fromDay = get("from");
  const toDay = get("to");
  return {
    object_type: get("object_type"),
    object_id: get("object_id"),
    actor: get("actor"),
    action: get("action"),
    action_prefix: get("action_prefix"),
    from: fromDay ? dayBoundary(fromDay, false) : undefined,
    to: toDay ? dayBoundary(toDay, true) : undefined,
    page: page > 1 ? Math.floor(page) : 1,
  };
}

type Draft = Record<(typeof FIELDS)[number], string>;

export function AuditLog() {
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname() || modRoutes.audit();
  const sp = new URLSearchParams(search?.toString() ?? "");
  const params = readAuditParams(sp);
  const [draft, setDraft] = useState<Draft>(() => Object.fromEntries(FIELDS.map((k) => [k, sp.get(k) ?? ""])) as Draft);
  const [actorError, setActorError] = useState<string | null>(null);
  const searchKey = search?.toString() ?? "";
  useEffect(() => {
    const current = new URLSearchParams(searchKey);
    setDraft(Object.fromEntries(FIELDS.map((k) => [k, current.get(k) ?? ""])) as Draft);
  }, [searchKey]);

  const apiParams: AuditParams = params;
  const q = useModQuery({
    queryKey: modKeys.audit(apiParams),
    queryFn: () => moderationApi.audit({ ...apiParams, page_size: PAGE_SIZE }),
    placeholderData: (prev) => prev,
  });

  const hrefFor = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(searchKey);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    const s = next.toString();
    return s ? `${pathname}?${s}` : pathname;
  };

  const apply = (e: FormEvent) => {
    e.preventDefault();
    if (draft.actor && !UUID_RE.test(draft.actor.trim())) {
      setActorError("Нужен id аккаунта (UUID) — его можно скопировать из сводки аккаунта.");
      return;
    }
    setActorError(null);
    const patch: Record<string, string | undefined> = { page: undefined };
    for (const k of FIELDS) patch[k] = draft[k].trim() || undefined;
    router.replace(hrefFor(patch), { scroll: false });
  };

  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setDraft((d) => ({ ...d, [k]: e.target.value }));
  const filtered = FIELDS.some((k) => sp.get(k));

  return (
    <section className="gv-ac-panel gv-mod-panel" aria-labelledby="audit-title">
      <div className="gv-card-head">
        <div className="gv-card-head-text">
          <h2 id="audit-title">Журнал действий</h2>
          <p className="gv-ac-desc">Неизменяемая история решений модераторов, действий пользователей и администраторов. Записи нельзя изменить или удалить.</p>
        </div>
      </div>
      <form className="gv-mod-audit-filters" onSubmit={apply} role="search" aria-label="Фильтры журнала">
        <Select label="Тип объекта" value={draft.object_type} onChange={set("object_type")} placeholder="Любой" options={AUDIT_OBJECT_TYPES} />
        <TextInput label="ID объекта" value={draft.object_id} onChange={set("object_id")} placeholder="UUID или число" maxLength={64} />
        <TextInput label="ID исполнителя" value={draft.actor} onChange={set("actor")} placeholder="UUID аккаунта" error={actorError} maxLength={36} />
        <Select label="Группа действий" value={draft.action_prefix} onChange={set("action_prefix")} placeholder="Все" options={AUDIT_ACTION_PREFIXES} />
        <TextInput label="Точное действие" value={draft.action} onChange={set("action")} placeholder="spot.change_approved" maxLength={80} />
        <TextInput label="С даты" type="date" value={draft.from} onChange={set("from")} />
        <TextInput label="По дату" type="date" value={draft.to} onChange={set("to")} />
        <div className="gv-mod-audit-submit">
          <Button type="submit" variant="primary" icon="filter">
            Применить
          </Button>
          {filtered && (
            <Button variant="pill" onClick={() => router.replace(pathname, { scroll: false })}>
              Сбросить
            </Button>
          )}
        </div>
      </form>
      <QueryState
        query={q}
        isEmpty={(d) => d.results.length === 0}
        empty={<EmptyState compact title={filtered ? "Записей по фильтрам нет" : "Журнал пуст"} text={filtered ? "Проверьте ID и период." : undefined} />}
      >
        {(data) => (
          <>
            <p className="gv-mod-count" aria-live="polite">
              {formatNumber(data.count)} {plural(data.count, ["запись", "записи", "записей"])}
              {q.isFetching && !q.isPending ? " · обновляем…" : ""}
            </p>
            <AuditTrail events={data.results} showObject />
            <Pagination page={params.page ?? 1} count={data.count} pageSize={PAGE_SIZE} hrefFor={(n) => hrefFor({ page: n > 1 ? String(n) : undefined })} />
          </>
        )}
      </QueryState>
    </section>
  );
}
