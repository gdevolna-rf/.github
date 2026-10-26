"use client";
/**
 * Уведомления по видам × каналам (MSG-12): в приложении / email / push. Каждая галочка сохраняется сразу
 * (PUT только изменённого вида) с откатом при ошибке. Без записи сервер отдаёт значения по умолчанию.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accountApi, accountKeys, type NotificationPreference } from "@/lib/api/account";
import { NOTIFICATION_KIND_LABELS } from "@/lib/labels";
import { QueryState } from "@/components/ui/QueryState";
import { useToast } from "@/components/ui/Toast";

type Channel = "in_app" | "email" | "push";
const CHANNELS: Array<{ id: Channel; label: string; short: string }> = [
  { id: "in_app", label: "В приложении", short: "Сайт" },
  { id: "email", label: "Email", short: "Email" },
  { id: "push", label: "Push на телефон", short: "Push" },
];

type Prefs = { preferences: NotificationPreference[] };

export function NotificationPrefsSection() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: accountKeys.notificationPrefs, queryFn: accountApi.notificationPrefs });

  const mutation = useMutation({
    mutationFn: (item: { kind: string } & Partial<Record<Channel, boolean>>) => accountApi.updateNotificationPrefs([item]),
    onMutate: async (item) => {
      await queryClient.cancelQueries({ queryKey: accountKeys.notificationPrefs });
      const previous = queryClient.getQueryData<Prefs>(accountKeys.notificationPrefs);
      if (previous) {
        queryClient.setQueryData<Prefs>(accountKeys.notificationPrefs, {
          preferences: previous.preferences.map((p) => (p.kind === item.kind ? { ...p, ...item, is_default: false } : p)),
        });
      }
      return { previous };
    },
    onError: (err, item, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(accountKeys.notificationPrefs, ctx.previous);
      toast.error(err, { action: { label: "Повторить", onClick: () => mutation.mutate(item) } });
    },
    onSuccess: (data) => queryClient.setQueryData(accountKeys.notificationPrefs, data),
  });

  return (
    <section id="notifications" className="gv-ac-panel acc-settings-section" aria-labelledby="prefs-title">
      <h2 id="prefs-title">Уведомления</h2>
      <p className="gv-ac-desc">
        Выберите, о чём и как сообщать. Важные системные письма (подтверждение почты, сброс пароля, удаление аккаунта)
        приходят всегда.
      </p>
      <QueryState query={query} isEmpty={(d) => d.preferences.length === 0} loading={<div className="gv-skeleton" aria-busy="true"><span className="sr-only">Загружаем настройки…</span><span className="gv-skeleton-line" /><span className="gv-skeleton-line" /></div>}>
        {(data) => (
          <div className="acc-prefs" role="table" aria-label="Каналы уведомлений по видам">
            <div className="acc-prefs-row acc-prefs-head" role="row">
              <span role="columnheader">Событие</span>
              {CHANNELS.map((c) => (
                <span key={c.id} role="columnheader" title={c.label}>
                  {c.short}
                </span>
              ))}
            </div>
            {data.preferences.map((p) => {
              const label = p.label || NOTIFICATION_KIND_LABELS[p.kind] || "Другие уведомления";
              return (
                <div key={p.kind} className="acc-prefs-row" role="row">
                  <span role="rowheader" className="acc-prefs-kind">
                    {label}
                  </span>
                  {CHANNELS.map((c) => (
                    <span key={c.id} role="cell" className="acc-prefs-cell">
                      <input
                        type="checkbox"
                        id={`pref-${p.kind}-${c.id}`}
                        checked={p[c.id]}
                        onChange={(e) => mutation.mutate({ kind: p.kind, [c.id]: e.target.checked })}
                        aria-label={`${label}: ${c.label}`}
                      />
                      <label htmlFor={`pref-${p.kind}-${c.id}`} className="acc-prefs-mobile-label" aria-hidden="true">
                        {c.short}
                      </label>
                    </span>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </QueryState>
      <p className="gv-ac-muted">Push-уведомления придут на устройства, где вы вошли в мобильное приложение ГДеволна.</p>
    </section>
  );
}
