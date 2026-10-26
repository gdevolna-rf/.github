"use client";
/**
 * /moderation/cases/{id}: case header (kind, status, SLA, assignee, «взять в работу»), target by kind,
 * decision buttons from `available_actions` (sticky above the phone tab bar, ATX-22), resolution and the
 * audit trail (`history`). Every decision goes through DecisionDialog (comment where the API requires it).
 */
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { isApiError } from "@/lib/api/errors";
import { modKeys, moderationApi, type CaseAction, type ModerationCaseDetail } from "@/lib/api/moderation";
import { useMe } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { choiceCode } from "@/lib/labels";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { ErrorState, LoadingState, NoAccess } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { actionRule, RESOLUTION_LABELS, sortActions } from "./actions";
import { AuditTrail } from "./AuditTrail";
import { Facts, KindChip, PersonLine, RefreshButton, SectionTitle, SlaBadge, When } from "./Bits";
import { CertificateView, ComplaintView, OrganizationView, ReviewView, SpotChangeView } from "./CaseTargets";
import { DecisionDialog } from "./DecisionDialog";
import { useModQuery } from "./hooks";
import { CASE_ACTION_LABELS } from "./labels";
import { modRoutes } from "./routes";

function TargetBody({ c, onExpired }: { c: ModerationCaseDetail; onExpired: () => void }) {
  const t = c.target;
  if (!t) return <p className="gv-mod-muted">Объект модерации удалён.</p>;
  switch (t.type) {
    case "spot_change":
      return <SpotChangeView t={t} onExpired={onExpired} />;
    case "review":
      return <ReviewView t={t} onExpired={onExpired} />;
    case "certificate":
      return <CertificateView t={t} onExpired={onExpired} />;
    case "organization":
      return <OrganizationView t={t} />;
    case "complaint":
      return <ComplaintView t={t} isAppeal={choiceCode(c.kind) === "appeal"} onExpired={onExpired} />;
    default:
      return <pre className="gv-mod-pre">{JSON.stringify(t, null, 2)}</pre>;
  }
}

function ActionBar({ c, onAction }: { c: ModerationCaseDetail; onAction: (a: CaseAction) => void }) {
  const kind = choiceCode(c.kind) ?? "";
  const actions = sortActions(c.available_actions ?? []);
  if (!actions.length) {
    return (
      <p className="gv-mod-muted gv-mod-no-actions">
        <Icon name="info" size={15} /> Для текущего состояния объекта решений нет — всё уже решено или ждёт автора.
      </p>
    );
  }
  return (
    <div className="gv-sticky-actions gv-mod-actionbar" role="group" aria-label="Решения по кейсу">
      {actions.map((a) => {
        const rule = actionRule(kind, a);
        return (
          <Button key={a} variant={rule.tone === "danger" ? "danger" : rule.tone === "primary" ? "primary" : "pill"} onClick={() => onAction(a)}>
            {CASE_ACTION_LABELS[a] ?? a}
          </Button>
        );
      })}
    </div>
  );
}

export function CaseDetail({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { me } = useMe();
  const [action, setAction] = useState<CaseAction | null>(null);
  const q = useModQuery({ queryKey: modKeys.case(id), queryFn: () => moderationApi.case(id), staleTime: 60_000 });

  const take = useMutation({
    mutationFn: () => moderationApi.take(id),
    onSuccess: () => {
      toast.success("Кейс взят в работу");
      void queryClient.invalidateQueries({ queryKey: modKeys.all });
    },
    onError: (err) => toast.error(err, { action: { label: "Повторить", onClick: () => take.mutate() } }),
  });

  if (q.isPending) return <LoadingState variant="skeleton" lines={8} label="Загружаем кейс…" />;
  if (q.isError && !q.data) {
    const err = q.error;
    if (isApiError(err) && err.isNotFound) {
      return (
        <ErrorState
          error={err}
          title="Кейс не найден"
          onRetry={() => void q.refetch()}
        />
      );
    }
    if (isApiError(err) && err.isForbidden) return <NoAccess text="Решения по кейсам доступны модераторам с подтверждённой 2FA-сессией." />;
    return <ErrorState error={err} title="Не удалось загрузить кейс" onRetry={() => void q.refetch()} />;
  }
  const c = q.data!;
  const status = choiceCode(c.status);
  const mine = c.assigned_to?.id === me?.id;
  const refresh = () => void q.refetch();

  return (
    <article className="gv-ac-panel gv-mod-panel gv-mod-case-detail" aria-labelledby="case-title">
      <Link href={modRoutes.queue} className="feature-link gv-mod-back">
        <Icon name="arrow-left" size={15} /> К очереди
      </Link>
      <header className="gv-mod-case-header">
        <div className="gv-mod-case-head">
          <KindChip kind={c.kind} />
          <StatusBadge domain="moderationCase" status={choiceCode(c.status)} />
          <SlaBadge c={c} />
        </div>
        <h2 id="case-title" className="gv-mod-case-h">
          {c.summary || "Кейс"}
        </h2>
        <div className="gv-mod-case-meta">
          <span>
            Создан <When value={c.created_at} />
          </span>
          {c.due_at && status !== "resolved" && (
            <span>
              Срок по SLA <When value={c.due_at} />
            </span>
          )}
          <span className="gv-mod-case-assignee">
            Исполнитель:{" "}
            {c.assigned_to ? <PersonLine person={c.assigned_to} size={22} link={false} role={mine ? "это вы" : undefined} /> : <i>не назначен</i>}
          </span>
        </div>
        <div className="gv-mod-case-tools">
          {status !== "resolved" && !mine && (
            <Button variant="soft" icon="user" onClick={() => take.mutate()} loading={take.isPending}>
              {c.assigned_to ? "Забрать себе" : "Взять в работу"}
            </Button>
          )}
          <RefreshButton onClick={refresh} loading={q.isFetching && !q.isPending} />
        </div>
      </header>

      {status === "resolved" && (
        <section className={cx("gv-mod-resolution")} aria-label="Решение по кейсу">
          <Icon name="check" size={18} />
          <div>
            <b>Решение: {RESOLUTION_LABELS[c.resolution] ?? (c.resolution || "закрыт")}</b>
            <Facts
              items={[
                ["Кто", c.resolved_by ? <PersonLine key="r" person={c.resolved_by} size={22} /> : "Система / автор"],
                ["Когда", <When key="w" value={c.resolved_at} />],
                ["Комментарий", c.resolution_note],
              ]}
            />
          </div>
        </section>
      )}

      <TargetBody c={c} onExpired={refresh} />

      <ActionBar c={c} onAction={setAction} />

      <section className="gv-mod-block" aria-labelledby="case-history">
        <SectionTitle icon="clock">
          <span id="case-history">Журнал по объекту</span>
        </SectionTitle>
        <AuditTrail events={c.history ?? []} />
        {c.target_id && (
          <Link className="feature-link" href={modRoutes.audit({ object_id: String(c.target_id) })}>
            Открыть в журнале действий →
          </Link>
        )}
      </section>

      <DecisionDialog key={action ?? "none"} c={c} action={action} onClose={() => setAction(null)} />
    </article>
  );
}
