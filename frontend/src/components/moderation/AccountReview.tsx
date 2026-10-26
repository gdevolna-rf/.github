"use client";
/**
 * /moderation/accounts/{id}: account summary for a moderator (TRUST-07, F14): roles, organizations, counters,
 * restrictions (restrict with kind/reason/expiry, lift) and complaints about the account's content.
 */
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { isApiError } from "@/lib/api/errors";
import { modKeys, moderationApi, type Restriction, type RestrictionKind } from "@/lib/api/moderation";
import { formatNumber } from "@/lib/format";
import { choiceCode, choiceLabel, MEMBERSHIP_ROLE_LABELS, ORGANIZATION_KIND_LABELS, STAFF_ROLE_LABELS } from "@/lib/labels";
import { Avatar } from "@/components/ui/Avatar";
import { Badge, StatusBadge, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select, TextInput, Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { QueryState } from "@/components/ui/QueryState";
import { EmptyState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { Facts, PersonLine, SectionTitle, When } from "./Bits";
import { useModQuery } from "./hooks";
import { COMPLAINT_ACTION_LABELS, COMPLAINT_REASON_LABELS, COMPLAINT_TARGET_LABELS, RESTRICTION_KIND_HINTS, RESTRICTION_KIND_LABELS } from "./labels";
import { modRoutes } from "./routes";

const KINDS: RestrictionKind[] = ["publishing", "messaging", "suspended"];

function RestrictDialog({ accountId, open, onClose }: { accountId: string; open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [kind, setKind] = useState<RestrictionKind>("publishing");
  const [reason, setReason] = useState("");
  const [expires, setExpires] = useState("");
  const [errors, setErrors] = useState<{ reason?: string; expires?: string }>({});
  const m = useMutation({
    mutationFn: () =>
      moderationApi.restrict(accountId, { kind, reason: reason.trim(), expires_at: expires ? new Date(expires).toISOString() : null }),
    onSuccess: () => {
      toast.success("Ограничение применено");
      void queryClient.invalidateQueries({ queryKey: modKeys.all });
      setReason("");
      setExpires("");
      onClose();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next: typeof errors = {};
    if (!reason.trim()) next.reason = "Укажите причину — её увидит пользователь.";
    if (expires && new Date(expires).getTime() <= Date.now()) next.expires = "Дата должна быть в будущем.";
    setErrors(next);
    if (Object.keys(next).length) return;
    m.mutate();
  };
  const apiErr = isApiError(m.error) ? m.error : null;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Ограничить аккаунт"
      description="Вход, апелляции и собственные данные остаются доступны пользователю. Действие записывается в журнал."
      size="wide"
      footer={
        <>
          <Button variant="pill" onClick={onClose} disabled={m.isPending}>
            Отмена
          </Button>
          <Button type="submit" form="restrict-form" variant="danger" icon="lock" loading={m.isPending}>
            Ограничить
          </Button>
        </>
      }
    >
      <form id="restrict-form" onSubmit={submit} noValidate className="gv-mod-decision">
        {apiErr && (
          <div className="gv-form-error" role="alert">
            <Icon name="alert" size={18} />
            <span>{apiErr.message}</span>
          </div>
        )}
        <fieldset className="gv-mod-measures">
          <legend>Вид ограничения</legend>
          {KINDS.map((k) => (
            <label key={k}>
              <input type="radio" name="restriction-kind" value={k} checked={kind === k} onChange={() => setKind(k)} />
              <span>
                <b>{RESTRICTION_KIND_LABELS[k]}</b>
                <small>{RESTRICTION_KIND_HINTS[k]}</small>
              </span>
            </label>
          ))}
        </fieldset>
        <Textarea label="Причина (увидит пользователь)" required value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} rows={3} error={errors.reason ?? apiErr?.fieldError("reason")} />
        <TextInput
          label="Действует до"
          type="datetime-local"
          value={expires}
          onChange={(e) => setExpires(e.target.value)}
          hint="Пусто — бессрочно, пока модератор не снимет"
          error={errors.expires ?? apiErr?.fieldError("expires_at")}
        />
      </form>
    </Modal>
  );
}

function LiftDialog({ restriction, onClose }: { restriction: Restriction | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [note, setNote] = useState("");
  const m = useMutation({
    mutationFn: () => moderationApi.lift(restriction!.id, note.trim()),
    onSuccess: () => {
      toast.success("Ограничение снято");
      void queryClient.invalidateQueries({ queryKey: modKeys.all });
      setNote("");
      onClose();
    },
  });
  return (
    <Modal
      open={Boolean(restriction)}
      onClose={onClose}
      title="Снять ограничение"
      description={restriction ? `${choiceLabel(restriction.kind, RESTRICTION_KIND_LABELS)}: ${restriction.reason}` : undefined}
      footer={
        <>
          <Button variant="pill" onClick={onClose} disabled={m.isPending}>
            Отмена
          </Button>
          <Button variant="primary" icon="check" loading={m.isPending} onClick={() => m.mutate()}>
            Снять ограничение
          </Button>
        </>
      }
    >
      {isApiError(m.error) && (
        <div className="gv-form-error" role="alert">
          <Icon name="alert" size={18} />
          <span>{m.error.message}</span>
        </div>
      )}
      <Textarea label="Комментарий (необязательно)" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} rows={3} />
    </Modal>
  );
}

export function AccountReview({ id }: { id: string }) {
  const q = useModQuery({ queryKey: modKeys.account(id), queryFn: () => moderationApi.account(id) });
  const [restrictOpen, setRestrictOpen] = useState(false);
  const [lifting, setLifting] = useState<Restriction | null>(null);

  return (
    <section className="gv-ac-panel gv-mod-panel" aria-labelledby="acc-title">
      <Link href={modRoutes.queue} className="feature-link gv-mod-back">
        <Icon name="arrow-left" size={15} /> К очереди
      </Link>
      <QueryState query={q} errorTitle="Не удалось загрузить аккаунт">
        {(data) => {
          const s = data.summary;
          const name = data.account.is_deleted || s.is_deleted ? "Удалённый аккаунт" : data.account.display_name;
          const active = data.restrictions.filter((r) => r.is_active);
          return (
            <>
              <header className="gv-mod-account-head">
                <Avatar media={data.account.avatar} name={name} size={58} />
                <div>
                  <h2 id="acc-title">{name}</h2>
                  <p className="gv-mod-muted">
                    {data.account.handle ? `@${data.account.handle} · ` : ""}на сайте с <When value={s.date_joined} />
                  </p>
                  <div className="gv-mod-tags">
                    {s.roles.map((r) => (
                      <Tag key={r} variant="verified" icon="shield">
                        {STAFF_ROLE_LABELS[r as keyof typeof STAFF_ROLE_LABELS] ?? r}
                      </Tag>
                    ))}
                    {!s.is_active && <Badge tone="danger">Аккаунт деактивирован</Badge>}
                    {s.is_email_verified ? <Badge tone="ok">Email подтверждён</Badge> : <Badge tone="new">Email не подтверждён</Badge>}
                    {active.length > 0 && <Badge tone="danger" icon="lock">Ограничений: {active.length}</Badge>}
                  </div>
                </div>
                <div className="gv-mod-account-actions">
                  <Button variant="danger" icon="lock" onClick={() => setRestrictOpen(true)} disabled={s.is_deleted}>
                    Ограничить
                  </Button>
                  <Link className="feature-link" href={modRoutes.audit({ actor: data.account.id })}>
                    Действия аккаунта в журнале →
                  </Link>
                  <Link className="feature-link" href={modRoutes.audit({ object_type: "accounts.account", object_id: data.account.id })}>
                    Решения по аккаунту →
                  </Link>
                </div>
              </header>

              <div className="gv-mod-account-grid">
                <section className="gv-mod-block" aria-labelledby="acc-counts">
                  <SectionTitle icon="graph">
                    <span id="acc-counts">Активность</span>
                  </SectionTitle>
                  <Facts
                    items={[
                      ["Отзывы опубликованы", formatNumber(s.counts.reviews.published ?? 0)],
                      ["Отзывы на модерации", formatNumber(s.counts.reviews.pending ?? 0)],
                      ["Отклонено / скрыто", `${formatNumber(s.counts.reviews.rejected ?? 0)} / ${formatNumber(s.counts.reviews.hidden ?? 0)}`],
                      ["Правки спотов", formatNumber(s.counts.spot_proposals)],
                      ["Подал жалоб", formatNumber(s.counts.complaints_filed)],
                      ["Жалоб на аккаунт", `${formatNumber(s.counts.complaints_against)} (подтверждено ${formatNumber(s.counts.complaints_against_upheld)})`],
                    ]}
                  />
                </section>
                <section className="gv-mod-block" aria-labelledby="acc-orgs">
                  <SectionTitle icon="school">
                    <span id="acc-orgs">Организации</span>
                  </SectionTitle>
                  {s.organizations.length ? (
                    <ul className="gv-mod-plain-list">
                      {s.organizations.map((o) => (
                        <li key={o.id}>
                          <b>{o.name}</b>
                          <small>
                            {ORGANIZATION_KIND_LABELS[o.kind as keyof typeof ORGANIZATION_KIND_LABELS] ?? o.kind} ·{" "}
                            {MEMBERSHIP_ROLE_LABELS[o.role as keyof typeof MEMBERSHIP_ROLE_LABELS] ?? o.role}
                          </small>
                          <StatusBadge domain="organization" status={o.status} />
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="gv-mod-muted">Не состоит в организациях.</p>
                  )}
                </section>
              </div>

              <section className="gv-mod-block" aria-labelledby="acc-restr">
                <SectionTitle icon="lock">
                  <span id="acc-restr">Ограничения</span>
                </SectionTitle>
                {data.restrictions.length ? (
                  <ul className="gv-mod-rows">
                    {data.restrictions.map((r) => (
                      <li key={r.id} className={r.is_active ? "is-active" : undefined}>
                        <div className="gv-mod-row-main">
                          <b>{choiceLabel(r.kind, RESTRICTION_KIND_LABELS)}</b>
                          {r.is_active ? <Badge tone="danger">Действует</Badge> : <Badge tone="muted">{r.lifted_at ? "Снято" : "Истекло"}</Badge>}
                          <p>{r.reason}</p>
                          <small>
                            С <When value={r.created_at} />
                            {r.expires_at ? (
                              <>
                                {" "}
                                до <When value={r.expires_at} />
                              </>
                            ) : (
                              " · бессрочно"
                            )}
                            {r.lifted_at ? (
                              <>
                                {" "}
                                · снято <When value={r.lifted_at} />
                              </>
                            ) : null}
                          </small>
                          {r.created_by && (
                            <span className="gv-mod-row-by">
                              Назначил: <PersonLine person={r.created_by} size={20} link={false} />
                            </span>
                          )}
                        </div>
                        {r.is_active && (
                          <Button variant="soft" size="sm" onClick={() => setLifting(r)}>
                            Снять
                          </Button>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState compact title="Ограничений не было" />
                )}
              </section>

              <section className="gv-mod-block" aria-labelledby="acc-compl">
                <SectionTitle icon="alert">
                  <span id="acc-compl">Жалобы на материалы аккаунта</span>
                </SectionTitle>
                {data.complaints.length ? (
                  <ul className="gv-mod-rows">
                    {data.complaints.map((c) => (
                      <li key={c.id}>
                        <div className="gv-mod-row-main">
                          <b>
                            {choiceLabel(c.reason, COMPLAINT_REASON_LABELS)} · {choiceLabel(c.target_type, COMPLAINT_TARGET_LABELS)}
                          </b>
                          <StatusBadge domain="complaint" status={choiceCode(c.status)} />
                          {choiceCode(c.status) === "resolved" && <Tag variant="plain">{choiceLabel(c.action_taken, COMPLAINT_ACTION_LABELS)}</Tag>}
                          {c.appealed_at && <Badge tone="info">Обжаловано</Badge>}
                          {c.text && <p className="gv-clamp-2" title={c.text}>{c.text}</p>}
                          <small>
                            <When value={c.created_at} /> · от {c.reporter?.display_name ?? "участника"}
                          </small>
                        </div>
                        <Link className="feature-link" href={modRoutes.audit({ object_type: "trust.complaint", object_id: c.id })}>
                          История →
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState compact title="Жалоб нет" />
                )}
              </section>

              <RestrictDialog accountId={data.account.id} open={restrictOpen} onClose={() => setRestrictOpen(false)} />
              <LiftDialog restriction={lifting} onClose={() => setLifting(null)} />
            </>
          );
        }}
      </QueryState>
    </section>
  );
}
