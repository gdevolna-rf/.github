"use client";
/**
 * /moderation — single queue (TRUST-04, TRUST-07): kind tabs with open counters, status/assignee/overdue filters,
 * search by summary, SLA markers, «Взять в работу», moderation speed header (GET moderation/stats).
 * Filters live in the URL (shareable, «Назад» works).
 */
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { modKeys, moderationApi, type CaseKind, type CaseListParams, type ModerationCaseItem } from "@/lib/api/moderation";
import { useMe } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { formatNumber, formatRelative, plural, WORDS } from "@/lib/format";
import { choiceCode } from "@/lib/labels";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Checkbox, Select, TextInput } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { QueryState } from "@/components/ui/QueryState";
import { StatStrip } from "@/components/ui/StatStrip";
import { StatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { KindChip, PersonLine, SlaBadge } from "./Bits";
import { useModQuery } from "./hooks";
import { CASE_KIND_FILTERS, CASE_STATUS_FILTERS } from "./labels";
import { modRoutes } from "./routes";

const PAGE_SIZE = 20;
const STATUSES = CASE_STATUS_FILTERS.map((s) => s.value) as string[];

export function readQueueParams(search: URLSearchParams): CaseListParams {
  const kind = search.get("kind") ?? undefined;
  const status = search.get("status");
  const assigned = search.get("assigned");
  const page = Number(search.get("page") || 1);
  return {
    kind: kind && CASE_KIND_FILTERS.some((k) => k.kind === kind) ? kind : undefined,
    status: status && STATUSES.includes(status) ? (status as CaseListParams["status"]) : "open",
    overdue: search.get("overdue") === "1",
    assigned: assigned === "me" || assigned === "none" ? assigned : undefined,
    q: search.get("q")?.trim() || undefined,
    page: Number.isFinite(page) && page > 1 ? Math.floor(page) : 1,
  };
}

function hours(h: number | null | undefined): string {
  if (h === null || h === undefined) return "—";
  if (h < 1) return "< 1 ч";
  if (h < 48) return `${formatNumber(h, 0)} ч`;
  const d = Math.round(h / 24);
  return `${d} ${plural(d, WORDS.day)}`;
}

function QueueStats() {
  const stats = useModQuery({ queryKey: modKeys.stats, queryFn: () => moderationApi.stats(30), staleTime: 30_000 });
  if (!stats.data) {
    return stats.isError ? null : <div className="gv-mod-stats-skeleton" aria-hidden="true" />;
  }
  const s = stats.data;
  return (
    <StatStrip
      ariaLabel="Скорость модерации"
      className="gv-mod-stats"
      items={[
        { label: "Открыто", value: formatNumber(s.open_cases.total), hint: "Открытые и взятые в работу кейсы" },
        {
          label: "Просрочено по SLA",
          value: formatNumber(s.overdue_cases.total),
          tone: s.overdue_cases.total > 0 ? "accent" : "default",
          hint: "Кейсы, срок рассмотрения которых истёк",
        },
        { label: "Самый старый кейс", value: hours(s.oldest_open_case_hours), hint: "Сколько ждёт самый старый открытый кейс" },
        {
          label: "Медиана решения по правкам",
          value: hours(s.spot_proposals.median_hours_to_decision),
          hint: `От подачи до решения за ${s.spot_proposals.period_days} дн.; решено ${s.spot_proposals.decided}: принято ${s.spot_proposals.approved}, отклонено ${s.spot_proposals.rejected}`,
        },
        { label: `Решено за ${s.spot_proposals.period_days} дн.`, value: formatNumber(s.resolved_last_period) },
      ]}
    />
  );
}

function KindTabs({ params, counts, hrefFor }: { params: CaseListParams; counts?: Partial<Record<CaseKind, number>>; hrefFor: (patch: Record<string, string | undefined>) => string }) {
  const total = counts ? Object.values(counts).reduce((a, b) => a + (b ?? 0), 0) : undefined;
  const items = [{ kind: undefined as CaseKind | undefined, label: "Все", count: total }, ...CASE_KIND_FILTERS.map((k) => ({ ...k, count: counts?.[k.kind] }))];
  return (
    <nav aria-label="Тип кейса" className="gv-tabs gv-mod-kind-tabs">
      {items.map((t) => {
        const active = (params.kind ?? undefined) === t.kind;
        return (
          <Link
            key={t.kind ?? "all"}
            href={hrefFor({ kind: t.kind, page: undefined })}
            className={cx("gv-tab-btn", active && "active")}
            aria-current={active ? "page" : undefined}
            scroll={false}
          >
            <span>{t.label}</span>
            {t.count ? (
              <span className="gv-mod-tab-count" aria-label={`открыто: ${t.count}`}>
                {t.count > 99 ? "99+" : t.count}
              </span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}

function CaseRow({ item, meId, onTake, taking }: { item: ModerationCaseItem; meId?: string; onTake: (id: string) => void; taking: boolean }) {
  const status = choiceCode(item.status);
  const mine = item.assigned_to?.id === meId;
  const canTake = status !== "resolved" && !mine;
  return (
    <li className={cx("gv-mod-case", item.is_overdue && status !== "resolved" && "is-overdue")}>
      <div className="gv-mod-case-head">
        <KindChip kind={item.kind} />
        <StatusBadge domain="moderationCase" status={choiceCode(item.status)} />
        <SlaBadge c={item} />
      </div>
      <h3 className="gv-mod-case-title gv-clamp-2" title={item.summary}>
        <Link href={modRoutes.case(item.id)}>{item.summary || "Кейс без описания"}</Link>
      </h3>
      <div className="gv-mod-case-meta">
        <span>
          Создан <time dateTime={item.created_at}>{formatRelative(item.created_at)}</time>
        </span>
        {status === "resolved" ? (
          <span className="gv-mod-case-assignee">
            Решение: <PersonLine person={item.resolved_by} size={22} link={false} />
          </span>
        ) : (
          <span className="gv-mod-case-assignee">
            Исполнитель:{" "}
            {item.assigned_to ? <PersonLine person={item.assigned_to} size={22} link={false} role={mine ? "это вы" : undefined} /> : <i>не назначен</i>}
          </span>
        )}
      </div>
      <div className="gv-mod-case-actions">
        {canTake && (
          <Button variant="soft" size="sm" icon="user" onClick={() => onTake(item.id)} loading={taking}>
            {item.assigned_to ? "Забрать себе" : "Взять в работу"}
          </Button>
        )}
        <ButtonLink href={modRoutes.case(item.id)} variant="primary" size="sm" iconRight="arrow">
          Открыть
        </ButtonLink>
      </div>
    </li>
  );
}

export function ModerationQueue() {
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname() || modRoutes.queue;
  const queryClient = useQueryClient();
  const toast = useToast();
  const { me } = useMe();
  const params = readQueueParams(new URLSearchParams(search?.toString() ?? ""));
  const [q, setQ] = useState(params.q ?? "");
  useEffect(() => setQ(params.q ?? ""), [params.q]);

  const hrefFor = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(search?.toString() ?? "");
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "") next.delete(k);
      else next.set(k, v);
    }
    if (next.get("status") === "open") next.delete("status");
    const s = next.toString();
    return s ? `${pathname}?${s}` : pathname;
  };
  const go = (patch: Record<string, string | undefined>) => router.replace(hrefFor({ page: undefined, ...patch }), { scroll: false });

  const stats = useModQuery({ queryKey: modKeys.stats, queryFn: () => moderationApi.stats(30), staleTime: 30_000 });
  const listKey = { ...params };
  const cases = useModQuery({
    queryKey: modKeys.cases(listKey),
    queryFn: () => moderationApi.cases({ ...params, page_size: PAGE_SIZE }),
    placeholderData: (prev) => prev,
    refetchInterval: 60_000,
  });

  const [takingId, setTakingId] = useState<string | null>(null);
  const take = useMutation({
    mutationFn: (id: string) => moderationApi.take(id),
    onMutate: (id) => setTakingId(id),
    onSettled: () => setTakingId(null),
    onSuccess: (c) => {
      toast.success("Кейс взят в работу", { action: { label: "Открыть", onClick: () => router.push(modRoutes.case(c.id)) } });
      void queryClient.invalidateQueries({ queryKey: modKeys.all });
    },
    onError: (err, id) => {
      toast.error(err, { action: { label: "Повторить", onClick: () => take.mutate(id) } });
      void queryClient.invalidateQueries({ queryKey: ["moderation", "cases"] });
    },
  });

  const submitSearch = (e: FormEvent) => {
    e.preventDefault();
    go({ q: q.trim() || undefined });
  };

  const filtered = Boolean(params.kind || params.overdue || params.assigned || params.q || params.status !== "open");

  return (
    <section className="gv-ac-panel gv-mod-panel" aria-labelledby="mod-queue-title">
      <div className="gv-card-head">
        <div className="gv-card-head-text">
          <h2 id="mod-queue-title">Очередь модерации</h2>
          <p className="gv-ac-desc">Правки спотов, отзывы, сертификаты, публикации организаций, жалобы и апелляции — сначала с ближайшим сроком.</p>
        </div>
      </div>
      <QueueStats />
      <KindTabs params={params} counts={stats.data?.open_cases.by_kind} hrefFor={hrefFor} />

      <div className="gv-mod-filters" role="search" aria-label="Фильтры очереди">
        <Select
          label="Статус"
          value={params.status ?? "open"}
          onChange={(e) => go({ status: e.target.value })}
          options={CASE_STATUS_FILTERS.map((s) => ({ value: s.value, label: s.label }))}
        />
        <Select
          label="Исполнитель"
          value={params.assigned ?? ""}
          onChange={(e) => go({ assigned: e.target.value || undefined })}
          placeholder="Любой"
          options={[
            { value: "me", label: "Мои кейсы" },
            { value: "none", label: "Без исполнителя" },
          ]}
        />
        <form onSubmit={submitSearch} className="gv-mod-search">
          <TextInput label="Поиск по описанию" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Название спота, имя…" maxLength={100} />
          <Button type="submit" variant="soft" icon="search" aria-label="Найти">
            <span className="gv-mod-hide-sm">Найти</span>
          </Button>
        </form>
        <Checkbox label="Только просроченные" checked={Boolean(params.overdue)} onChange={(e) => go({ overdue: e.target.checked ? "1" : undefined })} />
      </div>

      <QueryState
        query={cases}
        isEmpty={(d) => d.results.length === 0}
        empty={
          <EmptyState
            compact
            title={filtered ? "По этим фильтрам кейсов нет" : "Очередь пуста"}
            text={filtered ? "Измените фильтры или посмотрите все открытые кейсы." : "Новые правки, отзывы и жалобы появятся здесь автоматически."}
            action={filtered ? { label: "Сбросить фильтры", href: modRoutes.queue } : undefined}
          />
        }
      >
        {(data) => (
          <>
            <p className="gv-mod-count" aria-live="polite">
              {formatNumber(data.count)} {plural(data.count, ["кейс", "кейса", "кейсов"])}
              {cases.isFetching && !cases.isPending ? " · обновляем…" : ""}
            </p>
            <ul className="gv-mod-cases">
              {data.results.map((item) => (
                <CaseRow key={item.id} item={item} meId={me?.id} onTake={(id) => take.mutate(id)} taking={take.isPending && takingId === item.id} />
              ))}
            </ul>
            <Pagination page={params.page ?? 1} count={data.count} pageSize={PAGE_SIZE} hrefFor={(n) => hrefFor({ page: n > 1 ? String(n) : undefined })} />
          </>
        )}
      </QueryState>
    </section>
  );
}
