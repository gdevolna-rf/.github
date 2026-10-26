"use client";
/**
 * Этапы ремонта / индивидуального заказа (SHO-06): исполнитель добавляет этапы и отмечает выполненными,
 * клиент подтверждает. Статусы — единый словарь (StatusBadge domain="milestone").
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { inboxApi, inboxKeys, type InquiryDetail, type Milestone } from "@/lib/api/account-inbox";
import { formatDate, formatMoney } from "@/lib/format";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/Badge";
import { TextInput } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { todayIso, viewerTimeZone } from "../shared/utils";

export function Milestones({ inquiry }: { inquiry: InquiryDetail }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const provider = inquiry.my_role === "provider";
  const open = inquiry.status === "new" || inquiry.status === "in_progress";
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ title: "", amount: "", due_date: "" });
  const [error, setError] = useState<string | null>(null);

  const refresh = (updated?: Milestone) => {
    queryClient.setQueryData<InquiryDetail>(inboxKeys.detail(inquiry.id), (old) => {
      if (!old || !updated) return old;
      const exists = old.milestones.some((m) => m.id === updated.id);
      return { ...old, milestones: exists ? old.milestones.map((m) => (m.id === updated.id ? updated : m)) : [...old.milestones, updated] };
    });
    void queryClient.invalidateQueries({ queryKey: inboxKeys.detail(inquiry.id) });
  };

  const add = useMutation({
    mutationFn: () =>
      inboxApi.addMilestone(inquiry.id, {
        title: form.title.trim(),
        amount: form.amount ? form.amount.replace(",", ".").replace(/\s/g, "") : null,
        due_date: form.due_date || null,
      }),
    onSuccess: (m) => {
      refresh(m);
      setForm({ title: "", amount: "", due_date: "" });
      setAdding(false);
      toast.success("Этап добавлен");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Не удалось добавить этап."),
  });
  const done = useMutation({
    mutationFn: (m: Milestone) => inboxApi.milestoneDone(m.id),
    onSuccess: (m) => {
      refresh(m);
      toast.success("Этап отмечен выполненным — клиент получит уведомление");
    },
    onError: (err) => toast.error(err),
  });
  const confirm = useMutation({
    mutationFn: (m: Milestone) => inboxApi.milestoneConfirm(m.id),
    onSuccess: (m) => {
      refresh(m);
      toast.success("Этап подтверждён");
    },
    onError: (err) => toast.error(err),
  });
  const remove = useMutation({
    mutationFn: (m: Milestone) => inboxApi.deleteMilestone(inquiry.id, m.id),
    onSuccess: (_d, m) => {
      queryClient.setQueryData<InquiryDetail>(inboxKeys.detail(inquiry.id), (old) => (old ? { ...old, milestones: old.milestones.filter((x) => x.id !== m.id) } : old));
      toast.success("Этап удалён");
    },
    onError: (err) => toast.error(err),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) {
      setError("Назовите этап, например «Диагностика и смета».");
      return;
    }
    if (form.amount && !/^\d{1,10}([.,]\d{1,2})?$/.test(form.amount.replace(/\s/g, ""))) {
      setError("Сумма — число в рублях.");
      return;
    }
    setError(null);
    add.mutate();
  };

  const tz = viewerTimeZone();
  const items = [...inquiry.milestones].sort((a, b) => a.position - b.position);

  return (
    <section className="acc-side-block" aria-labelledby="ms-title">
      <h3 id="ms-title">Этапы работ</h3>
      {items.length === 0 ? (
        <EmptyState
          compact
          title="Этапов пока нет"
          text={provider ? "Разбейте работу на этапы — клиент подтвердит каждый." : "Исполнитель добавит этапы, а вы подтвердите выполненные."}
        />
      ) : (
        <ol className="acc-milestones">
          {items.map((m) => (
            <li key={m.id}>
              <div className="acc-ms-main">
                <b>{m.title}</b>
                <small>
                  {[m.amount ? formatMoney(m.amount, inquiry.currency) : null, m.due_date ? `срок ${formatDate(m.due_date, { timeZone: tz, style: "dayMonth" })}` : null]
                    .filter(Boolean)
                    .join(" · ") || "Без суммы и срока"}
                </small>
              </div>
              <StatusBadge domain="milestone" status={m.status} />
              <div className="acc-ms-actions">
                {provider && m.status === "planned" && open && (
                  <>
                    <Button size="sm" variant="soft" icon="check" loading={done.isPending && done.variables?.id === m.id} onClick={() => done.mutate(m)}>
                      Выполнен
                    </Button>
                    <Button size="sm" variant="link" onClick={() => remove.mutate(m)} aria-label={`Удалить этап «${m.title}»`}>
                      Удалить
                    </Button>
                  </>
                )}
                {!provider && m.status === "done" && (
                  <Button size="sm" variant="primary" loading={confirm.isPending && confirm.variables?.id === m.id} onClick={() => confirm.mutate(m)}>
                    Подтвердить
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
      {provider && open && !adding && (
        <Button variant="soft" size="sm" icon="plus" onClick={() => setAdding(true)}>
          Добавить этап
        </Button>
      )}
      {provider && open && adding && (
        <form className="acc-subform" onSubmit={submit} noValidate>
          <TextInput label="Этап" required maxLength={200} value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} autoFocus />
          <div className="gv-form-grid">
            <TextInput label="Сумма, ₽" inputMode="decimal" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} />
            <TextInput label="Срок" type="date" min={todayIso()} value={form.due_date} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} />
          </div>
          {error && (
            <p className="gv-field-error" role="alert">
              {error}
            </p>
          )}
          <div className="gv-ac-form-action">
            <Button type="submit" variant="primary" size="sm" loading={add.isPending}>
              Добавить
            </Button>
            <Button variant="soft" size="sm" onClick={() => setAdding(false)}>
              Отмена
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}
