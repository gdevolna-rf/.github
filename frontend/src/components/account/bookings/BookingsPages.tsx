"use client";
/**
 * «Мои бронирования» и «Бронирования клиентов» — два раздельных ящика, никогда не смешиваются (MSG-02, ATX-27).
 * Действия приходят с сервера (`actions`), словарь статусов единый (SHO-05, ATX-28). Акт выдачи/возврата — RENT-06.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { bookingKeys, bookingsApi, type Booking, type BookingAction, type BookingBox, type BookingDetail, type HandoverKind, type ItemCondition } from "@/lib/api/account-bookings";
import type { Media } from "@/lib/api/types";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import { routes } from "@/lib/routes";
import { formatDateTime, formatMoney } from "@/lib/format";
import { useUrlState } from "../shared/utils";
import {
  Avatar,
  Button,
  ButtonLink,
  Card,
  CardHeader,
  Checkbox,
  EmptyState,
  MediaUploader,
  Modal,
  Pagination,
  QueryState,
  Segmented,
  Select,
  StatusBadge,
  Textarea,
  useToast,
} from "@/components/ui";
import { ReasonDialog } from "../shared/ReasonDialog";

const ACTION_META: Record<BookingAction, { label: string; variant: "primary" | "line" | "link" | "danger"; reason?: "required" | "optional"; confirm: string }> = {
  confirm: { label: "Подтвердить", variant: "primary", confirm: "Подтвердить бронь?" },
  decline: { label: "Отклонить", variant: "line", reason: "required", confirm: "Отклонить запрос" },
  start: { label: "Начать / выдать", variant: "line", confirm: "Отметить начало?" },
  complete: { label: "Завершить", variant: "primary", confirm: "Завершить бронь?" },
  no_show: { label: "Неявка", variant: "link", reason: "optional", confirm: "Отметить неявку" },
  cancel: { label: "Отменить", variant: "danger", reason: "optional", confirm: "Отменить бронь" },
};

const STATUS_OPTIONS = [
  { value: "requested", label: "Запрошено" },
  { value: "confirmed", label: "Подтверждено" },
  { value: "in_progress", label: "Идёт / выдано" },
  { value: "completed", label: "Завершено" },
  { value: "cancelled", label: "Отменено" },
  { value: "declined", label: "Отклонено" },
  { value: "no_show", label: "Неявка" },
];

function when(b: Pick<Booking, "starts_at" | "ends_at">) {
  return `${formatDateTime(b.starts_at)} — ${formatDateTime(b.ends_at)}`;
}

function BookingRow({ b }: { b: Booking }) {
  const photo = b.rental?.photo ?? null;
  const counterpart = b.my_role === "provider" ? b.participant_name || b.customer.display_name : b.provider?.name ?? b.provider_organization?.name;
  return (
    <li className="lc-list-row">
      {photo ? <Avatar media={photo} name={b.title} size={44} /> : <Avatar media={b.my_role === "provider" ? b.customer.avatar : null} name={counterpart ?? b.title} size={44} />}
      <Link className="lc-grow" href={routes.account.booking(b.id)}>
        <strong>{b.title}</strong>
        <div className="small muted">
          {b.kind_label} · {when(b)}
          {counterpart ? ` · ${counterpart}` : ""}
          {b.seats > 1 ? ` · мест: ${b.seats}` : ""}
          {b.is_overdue ? " · просрочено" : ""}
        </div>
      </Link>
      {b.price_amount && <span className="small">{formatMoney(b.price_amount, b.currency)}</span>}
      <StatusBadge domain="booking" status={b.status} />
    </li>
  );
}

export function BookingsPage() {
  const url = useUrlState();
  const box = (url.get("box") === "provider" ? "provider" : "mine") as BookingBox;
  const status = url.get("status") ?? "";
  const kind = (url.get("kind") ?? "") as "" | "lesson" | "rental";
  const organization = url.get("organization") || undefined;
  const page = Number(url.get("page") ?? "1") || 1;
  const q = { box, status: status || undefined, kind, organization, page };
  const list = useQuery({ queryKey: bookingKeys.list(q), queryFn: () => bookingsApi.list(q) });
  return (
    <section className="gv-ac-panel" aria-labelledby="bookings-title">
      <CardHeader
        title={<span id="bookings-title">{box === "mine" ? "Мои бронирования" : "Бронирования клиентов"}</span>}
        description={box === "mine" ? "Ваши записи на занятия и аренду." : "Запросы и брони клиентов к вам, вашей школе или прокату."}
      />
      <div className="lc-toolbar">
        <Segmented
          ariaLabel="Ящик"
          value={box}
          onChange={(v) => url.set({ box: v === "mine" ? null : v, page: null, status: null })}
          options={[
            { value: "mine", label: "Мои" },
            { value: "provider", label: "Клиентов" },
          ]}
        />
        <Select label="Статус" hideLabel appearance="filter" placeholder="Все статусы" value={status} onChange={(e) => url.set({ status: e.target.value || null, page: null })} options={STATUS_OPTIONS} />
        <Select
          label="Тип"
          hideLabel
          appearance="filter"
          placeholder="Занятия и аренда"
          value={kind}
          onChange={(e) => url.set({ kind: e.target.value || null, page: null })}
          options={[
            { value: "lesson", label: "Занятия" },
            { value: "rental", label: "Аренда" },
          ]}
        />
      </div>
      <QueryState
        query={list}
        isEmpty={(d) => d.results.length === 0}
        empty={
          <EmptyState
            compact
            title={box === "mine" ? "Бронирований пока нет" : "Запросов от клиентов пока нет"}
            text={box === "mine" ? "Запишитесь на занятие к инструктору или в школу, или арендуйте доску." : undefined}
            action={box === "mine" ? { label: "Инструкторы", href: routes.instructors } : undefined}
          />
        }
      >
        {(data) => (
          <>
            <ul className="lc-list">
              {data.results.map((b) => (
                <BookingRow key={b.id} b={b} />
              ))}
            </ul>
            <Pagination page={page} count={data.count} pageSize={20} onChange={(n: number) => url.set({ page: n > 1 ? String(n) : null })} />
          </>
        )}
      </QueryState>
    </section>
  );
}

function HandoverDialog({ booking, kind, onClose, onDone }: { booking: BookingDetail; kind: HandoverKind; onClose: () => void; onDone: () => void }) {
  const [condition, setCondition] = useState<ItemCondition>("good");
  const [notes, setNotes] = useState("");
  const [damage, setDamage] = useState(false);
  const [damageText, setDamageText] = useState("");
  const [photos, setPhotos] = useState<Media[]>([]);
  const save = useMutation({
    mutationFn: () =>
      bookingsApi.handover(booking.id, {
        kind,
        condition,
        notes,
        damage_reported: damage,
        damage_description: damage ? damageText : "",
        photo_ids: photos.map((p) => p.id),
      }),
    onSuccess: onDone,
  });
  return (
    <Modal
      open
      onClose={onClose}
      size="wide"
      title={kind === "issue" ? "Акт выдачи" : "Акт возврата"}
      footer={
        <Button variant="primary" loading={save.isPending} onClick={() => save.mutate()}>
          {kind === "issue" ? "Выдать" : "Принять возврат"}
        </Button>
      }
    >
      <Select
        label="Состояние"
        value={condition}
        onChange={(e) => setCondition(e.target.value as ItemCondition)}
        options={[
          { value: "new", label: "Новое" },
          { value: "excellent", label: "Отличное" },
          { value: "good", label: "Хорошее" },
          { value: "fair", label: "Рабочее" },
        ]}
      />
      <Textarea label="Заметки" value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
      {kind === "return" && <Checkbox label="Есть повреждения" checked={damage} onChange={(e) => setDamage(e.target.checked)} />}
      {damage && <Textarea label="Описание повреждений" required value={damageText} onChange={(e) => setDamageText(e.target.value)} rows={2} />}
      <MediaUploader purpose="handover_photo" maxFiles={10} value={photos} onChange={setPhotos} label="Фото" />
      {save.isError && <p className="gv-field-error" role="alert">{isApiError(save.error) ? save.error.message : "Не удалось сохранить акт."}</p>}
    </Modal>
  );
}

export function BookingDetailPage({ id }: { id: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const detail = useQuery({ queryKey: bookingKeys.detail(id), queryFn: () => bookingsApi.detail(id) });
  const handovers = useQuery({ queryKey: bookingKeys.handovers(id), queryFn: () => bookingsApi.handovers(id), enabled: detail.data?.kind === "rental" });
  const [action, setAction] = useState<BookingAction | null>(null);
  const [handover, setHandover] = useState<HandoverKind | null>(null);
  const refresh = () => {
    setAction(null);
    setHandover(null);
    void qc.invalidateQueries({ queryKey: ["bookings"] });
    void qc.invalidateQueries({ queryKey: qk.counters });
  };
  return (
    <QueryState query={detail}>
      {(b) => {
        const isRentalProvider = b.kind === "rental" && b.my_role === "provider";
        const meta = action ? ACTION_META[action] : null;
        return (
          <section className="gv-ac-panel" aria-labelledby="booking-title">
            <div className="lc-toolbar">
              <ButtonLink href={b.my_role === "provider" ? `${routes.account.bookings}?box=provider` : routes.account.bookings} variant="link" icon="arrow-left">
                Все бронирования
              </ButtonLink>
            </div>
            <CardHeader title={<span id="booking-title">{b.title}</span>} description={`${b.kind_label} · ${when(b)}`} actions={<StatusBadge domain="booking" status={b.status} />} />
            <dl className="lc-dl">
              {b.my_role === "provider" ? (
                <>
                  <dt>Клиент</dt>
                  <dd>
                    {b.customer.display_name}
                    {b.participant_name && b.participant_name !== b.customer.display_name ? ` · участник: ${b.participant_name}` : ""}
                    {b.participant_is_minor ? " · несовершеннолетний, согласие представителя получено" : ""}
                  </dd>
                </>
              ) : (
                <>
                  <dt>Исполнитель</dt>
                  <dd>{b.provider?.name ?? b.provider_organization?.name}</dd>
                </>
              )}
              {b.lesson?.spot && (
                <>
                  <dt>Спот</dt>
                  <dd>
                    <Link href={routes.spot(b.lesson.spot.slug)}>{b.lesson.spot.name}</Link>
                  </dd>
                </>
              )}
              {b.lesson?.instructor && (
                <>
                  <dt>Инструктор</dt>
                  <dd>{b.lesson.instructor.display_name}</dd>
                </>
              )}
              {b.rental?.pickup_location && (
                <>
                  <dt>Место получения</dt>
                  <dd>{b.rental.pickup_location}</dd>
                </>
              )}
              <dt>Места</dt>
              <dd>{b.seats}</dd>
              {b.price_amount && (
                <>
                  <dt>Стоимость</dt>
                  <dd>{formatMoney(b.price_amount, b.currency)} (рассчитана сервером, оплата — по договорённости)</dd>
                </>
              )}
              {b.customer_note && (
                <>
                  <dt>Комментарий</dt>
                  <dd>{b.customer_note}</dd>
                </>
              )}
              {(b.decline_reason || b.cancel_reason) && (
                <>
                  <dt>Причина</dt>
                  <dd>{b.decline_reason || b.cancel_reason}</dd>
                </>
              )}
            </dl>
            <div className="lc-form-actions">
              {b.actions.map((a) => (
                <Button key={a} variant={ACTION_META[a].variant} onClick={() => setAction(a)}>
                  {ACTION_META[a].label}
                </Button>
              ))}
              {isRentalProvider && b.status === "confirmed" && (
                <Button variant="line" onClick={() => setHandover("issue")}>
                  Акт выдачи
                </Button>
              )}
              {isRentalProvider && b.status === "in_progress" && (
                <Button variant="line" onClick={() => setHandover("return")}>
                  Акт возврата
                </Button>
              )}
              {b.inquiry && (
                <ButtonLink href={routes.account.inquiry(b.inquiry)} variant="soft" icon="chat">
                  Переписка
                </ButtonLink>
              )}
            </div>
            {b.group.length > 0 && (
              <Card variant="panel">
                <CardHeader title="Связанные бронирования" />
                <ul className="lc-list">
                  {b.group.map((g) => (
                    <li key={g.id} className="lc-list-row">
                      <Link className="lc-grow" href={routes.account.booking(g.id)}>
                        {g.title} · {formatDateTime(g.starts_at)}
                      </Link>
                      <StatusBadge domain="booking" status={g.status} />
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            {(handovers.data ?? []).length > 0 && (
              <Card variant="panel">
                <CardHeader title="Акты выдачи и возврата" />
                <ul className="lc-list">
                  {(handovers.data ?? []).map((h) => (
                    <li key={h.id} className="lc-list-row">
                      <span className="lc-grow">
                        {h.kind_label} · {h.condition_label} · {formatDateTime(h.created_at)}
                        {h.damage_reported ? ` · повреждения: ${h.damage_description}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            <Card variant="panel">
              <CardHeader title="История" />
              <ol className="lc-history">
                {b.history.map((h, i) => (
                  <li key={i}>
                    <span>{formatDateTime(h.created_at)}</span> {h.from_status_label ? `${h.from_status_label} → ` : ""}
                    <b>{h.to_status_label}</b>
                    {h.actor ? ` · ${h.actor.display_name}` : ""}
                    {h.comment ? ` · ${h.comment}` : ""}
                  </li>
                ))}
              </ol>
            </Card>
            {action && meta && (
              <ReasonDialog
                open
                onClose={() => setAction(null)}
                title={meta.confirm}
                withReason={Boolean(meta.reason)}
                reasonRequired={meta.reason === "required"}
                confirmLabel={meta.label}
                onConfirm={(reason) =>
                  bookingsApi.action(b.id, action, reason ? { reason } : {}).then(
                    () => {
                      toast.success("Статус брони обновлён");
                      refresh();
                    },
                  )
                }
              />
            )}
            {handover && <HandoverDialog booking={b} kind={handover} onClose={() => setHandover(null)} onDone={refresh} />}
          </section>
        );
      }}
    </QueryState>
  );
}
