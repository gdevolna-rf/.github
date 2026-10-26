"use client";
/**
 * Данные и согласия (ACC-13, TRUST-09, AT-10): журнал согласий, выгрузка персональных данных (JSON в закрытом
 * хранилище, скачивание по короткоживущей ссылке GET /media/{id}/url), запрос удаления аккаунта с отсрочкой
 * и отмена. Ошибка «сначала передайте владение организацией» объясняется со ссылкой на организации.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { accountApi, accountKeys, type DataExport, type DeletionState } from "@/lib/api/account";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import { mediaApi } from "@/lib/api/media";
import { formatDateTime, formatDate } from "@/lib/format";
import { routes } from "@/lib/routes";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { QueryState } from "@/components/ui/QueryState";
import { EmptyState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { CONSENT_LABELS, EXPORT_STATUS } from "../shared/options";
import { DialogError, ReasonDialog } from "../shared/ReasonDialog";
import { viewerTimeZone } from "../shared/utils";

function ConsentsBlock() {
  const query = useQuery({ queryKey: accountKeys.consents, queryFn: accountApi.consents });
  const [showAll, setShowAll] = useState(false);
  const tz = viewerTimeZone();
  return (
    <div className="acc-block" aria-labelledby="consents-title">
      <h3 id="consents-title">Журнал согласий</h3>
      <p className="gv-ac-muted">
        Каждая выдача и отзыв согласия сохраняются с датой. Обязательные согласия (соглашение и обработка данных) отзываются
        удалением аккаунта.
      </p>
      <QueryState query={query} isEmpty={(d) => d.history.length === 0} empty={<EmptyState compact title="Записей пока нет" />}>
        {(data) => {
          const rows = showAll ? data.history : data.history.slice(0, 6);
          return (
            <>
              <ul className="acc-consents">
                {rows.map((r) => (
                  <li key={r.id}>
                    <span className="acc-consent-kind">{CONSENT_LABELS[r.kind] ?? "Согласие"}</span>
                    <Badge tone={r.granted ? "ok" : "muted"}>{r.granted ? "Выдано" : "Отозвано"}</Badge>
                    <time dateTime={r.created_at}>{formatDateTime(r.created_at, { timeZone: tz })}</time>
                  </li>
                ))}
              </ul>
              {data.history.length > 6 && (
                <Button variant="link" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
                  {showAll ? "Свернуть" : `Показать всю историю (${data.history.length})`}
                </Button>
              )}
            </>
          );
        }}
      </QueryState>
    </div>
  );
}

function ExportsBlock() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const query = useQuery({
    queryKey: accountKeys.exports,
    queryFn: accountApi.exports,
    refetchInterval: (q) => ((q.state.data as DataExport[] | undefined)?.some((e) => e.status === "pending") ? 4000 : false),
  });
  const create = useMutation({
    mutationFn: accountApi.requestExport,
    onSuccess: () => {
      toast.success("Готовим выгрузку. Мы пришлём уведомление, когда файл будет готов.");
      void queryClient.invalidateQueries({ queryKey: accountKeys.exports });
    },
    onError: (err) => toast.error(err),
  });
  const [downloading, setDownloading] = useState<string | null>(null);
  const tz = viewerTimeZone();

  const download = async (exp: DataExport) => {
    if (!exp.file) return;
    setDownloading(exp.id);
    try {
      const { url } = await mediaApi.privateUrl(exp.file.id);
      window.location.assign(url);
    } catch (err) {
      toast.error(err, { action: { label: "Повторить", onClick: () => void download(exp) } });
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="acc-block" aria-labelledby="exports-title">
      <div className="acc-block-head">
        <div>
          <h3 id="exports-title">Выгрузка моих данных</h3>
          <p className="gv-ac-muted">Профиль, заказы, переписка, отзывы и согласия одним JSON-файлом. Ссылка на скачивание действует пару минут.</p>
        </div>
        <Button variant="soft" icon="upload" loading={create.isPending} onClick={() => create.mutate()}>
          Запросить выгрузку
        </Button>
      </div>
      <QueryState query={query} isEmpty={(d) => d.length === 0} empty={<EmptyState compact title="Выгрузок ещё не было" />}>
        {(items) => (
          <ul className="acc-exports">
            {items.map((e) => {
              const st = EXPORT_STATUS[e.status] ?? { label: "Статус уточняется", tone: "new" as const };
              return (
                <li key={e.id} className="gv-ac-line">
                  <div className="gv-ac-line-main">
                    <strong>Выгрузка от {formatDateTime(e.created_at, { timeZone: tz })}</strong>
                    <small>{e.completed_at ? `Готова ${formatDateTime(e.completed_at, { timeZone: tz })}` : e.status === "pending" ? "Обычно занимает до пары минут" : ""}</small>
                  </div>
                  <Badge tone={st.tone}>{st.label}</Badge>
                  {e.status === "ready" && e.file && (
                    <Button variant="soft" size="sm" icon="upload" loading={downloading === e.id} onClick={() => void download(e)}>
                      Скачать
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </QueryState>
    </div>
  );
}

function DeletionBlock() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: accountKeys.deletion, queryFn: accountApi.deletion });
  const [open, setOpen] = useState(false);
  const [understood, setUnderstood] = useState(false);
  const [ownershipError, setOwnershipError] = useState<string | null>(null);

  const afterChange = (state: DeletionState) => {
    queryClient.setQueryData(accountKeys.deletion, state);
    void queryClient.invalidateQueries({ queryKey: qk.me, exact: true });
  };

  const cancel = useMutation({
    mutationFn: accountApi.cancelDeletion,
    onSuccess: (state) => {
      afterChange(state);
      toast.success("Удаление отменено — аккаунт остаётся с вами");
    },
    onError: (err) => toast.error(err, { action: { label: "Повторить", onClick: () => cancel.mutate() } }),
  });

  return (
    <div className="acc-block acc-danger-zone" aria-labelledby="deletion-title">
      <h3 id="deletion-title">Удаление аккаунта</h3>
      <QueryState query={query}>
        {(state) =>
          state.pending && state.request ? (
            <div className="acc-banner is-warn" role="status">
              <Icon name="alert" size={20} />
              <div>
                <b>Аккаунт будет удалён {formatDate(state.request.scheduled_for, { timeZone: viewerTimeZone() })}.</b>
                <p>
                  До этой даты можно передумать. Личные данные будут обезличены; заказы, переписка и журналы сохранятся без
                  вашего имени.
                </p>
              </div>
              <Button variant="primary" loading={cancel.isPending} onClick={() => cancel.mutate()}>
                Отменить удаление
              </Button>
            </div>
          ) : (
            <>
              <p className="gv-ac-muted">
                После запроса у вас будет {state.grace_days} дн. на отмену. Затем профиль, фото, контакты и выгрузки удаляются,
                а заказы, обращения и отзывы остаются у другой стороны без вашего имени («Удалённый пользователь»).
              </p>
              {ownershipError && (
                <div className="acc-banner is-error" role="alert">
                  <Icon name="school" size={20} />
                  <div>
                    <b>Сначала передайте владение организацией</b>
                    <p>{ownershipError}</p>
                    <p>
                      Откройте <Link href={routes.account.orgs}>«Школы и организации»</Link> → «Команда» → «Передать владение»
                      другому участнику, затем повторите запрос.
                    </p>
                  </div>
                </div>
              )}
              <Button
                variant="danger"
                icon="trash"
                onClick={() => {
                  setUnderstood(false);
                  setOpen(true);
                }}
              >
                Удалить аккаунт…
              </Button>
              <ReasonDialog
                open={open}
                onClose={() => setOpen(false)}
                title="Удалить аккаунт?"
                description={`Аккаунт будет удалён через ${state.grace_days} дн. До этого срока удаление можно отменить здесь же.`}
                reasonLabel="Почему уходите (необязательно)"
                maxLength={2000}
                confirmLabel="Запросить удаление"
                onConfirm={async (reason) => {
                  if (!understood) throw new DialogError("Отметьте, что понимаете последствия удаления.");
                  try {
                    const res = await accountApi.requestDeletion(reason);
                    setOwnershipError(null);
                    afterChange(res);
                    toast.success("Запрос на удаление принят. Мы отправили письмо с подробностями.");
                  } catch (err) {
                    if (isApiError(err) && err.code === "ownership_transfer_required") {
                      setOwnershipError(err.message);
                      setOpen(false);
                      return;
                    }
                    throw err;
                  }
                }}
              >
                <Checkbox
                  label="Я понимаю, что профиль и личные данные будут удалены"
                  description="Выгрузите данные заранее, если они вам нужны."
                  checked={understood}
                  onChange={(e) => setUnderstood(e.target.checked)}
                />
              </ReasonDialog>
            </>
          )
        }
      </QueryState>
      {cancel.isError && <p className="gv-field-error">{errorMessage(cancel.error)}</p>}
    </div>
  );
}

export function DataSection() {
  return (
    <section id="data" className="gv-ac-panel acc-settings-section" aria-labelledby="data-title">
      <h2 id="data-title">Данные и согласия</h2>
      <p className="gv-ac-desc">Что вы разрешили, выгрузка ваших данных и удаление аккаунта.</p>
      <ConsentsBlock />
      <div className="gv-ac-sep" />
      <ExportsBlock />
      <div className="gv-ac-sep" />
      <DeletionBlock />
    </section>
  );
}
