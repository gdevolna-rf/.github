"use client";
/**
 * Простые разделы кабинета: избранное (ATX-11), уведомления (ACC-02), мои правки спотов (7.4), отзывы и жалобы
 * (7.5, TRUST-07), приглашения в организации (5.3), дневник катания GG Surfer (COM-04/06, MET-06).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { accountApi, type FavoriteEntry } from "@/lib/api/account";
import { mineApi, mineKeys, itemsOf, type ComplaintAgainstMe, type DiaryEntry, type DiaryInput, type DiaryVisibility, type MyComplaint } from "@/lib/api/mine";
import { favoritesApi } from "@/lib/api/favorites";
import type { Media } from "@/lib/api/types";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import { routes } from "@/lib/routes";
import { formatDate, formatDateTime } from "@/lib/format";
import { MEMBERSHIP_ROLE_LABELS, choiceCode, choiceLabel } from "@/lib/labels";
import { useMe } from "@/lib/auth/hooks";
import {
  Avatar,
  Button,
  ButtonLink,
  Card,
  CardHeader,
  EmptyState,
  MediaImage,
  MediaUploader,
  Modal,
  QueryState,
  Rating,
  RatingInput,
  Select,
  StatStrip,
  StatusBadge,
  Textarea,
  TextInput,
  useToast,
} from "@/components/ui";
import { ReasonDialog } from "../shared/ReasonDialog";

const errText = (e: unknown, fallback: string) => (isApiError(e) ? e.message : fallback);

const FAVORITE_GROUPS: Record<string, string> = {
  spot: "Споты",
  instructor: "Инструкторы",
  organization: "Школы, мастерские и прокаты",
  board_model: "Доски",
  inventory_item: "Оборудование",
};

export function FavoritesPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const list = useQuery({ queryKey: qk.favorites(), queryFn: accountApi.favorites });
  const remove = useMutation({
    mutationFn: (f: FavoriteEntry) => favoritesApi.remove(f.target_type, f.target_id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["me", "favorites"] });
    },
    onError: (e) => toast.error(e),
  });
  return (
    <section className="gv-ac-panel" aria-labelledby="fav-title">
      <CardHeader title={<span id="fav-title">Избранное</span>} description="Споты, инструкторы, школы, шейперы, доски и оборудование." />
      <QueryState
        query={list}
        isEmpty={(d) => d.results.length === 0}
        empty={<EmptyState compact title="В избранном пока пусто" text="Нажмите сердечко на карточке спота, инструктора или доски." action={{ label: "Карта спотов", href: routes.spots }} />}
      >
        {(data) => {
          const groups = new Map<string, FavoriteEntry[]>();
          for (const f of data.results) groups.set(f.target_type, [...(groups.get(f.target_type) ?? []), f]);
          return (
            <div className="lc-stack">
              {[...groups.entries()].map(([type, items]) => (
                <Card key={type} variant="panel">
                  <CardHeader title={FAVORITE_GROUPS[type] ?? type} />
                  <ul className="lc-list">
                    {items.map((f) => (
                      <li key={`${f.target_type}:${f.target_id}`} className="lc-list-row">
                        <Avatar media={f.card.image} name={f.card.title} size={48} />
                        <Link className="lc-grow" href={f.card.url}>
                          <strong>{f.card.title}</strong>
                          <div className="small muted">{f.card.subtitle}</div>
                        </Link>
                        <Button variant="link" onClick={() => remove.mutate(f)}>
                          Убрать
                        </Button>
                      </li>
                    ))}
                  </ul>
                </Card>
              ))}
            </div>
          );
        }}
      </QueryState>
    </section>
  );
}

export function NotificationsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const [unread, setUnread] = useState(false);
  const list = useQuery({ queryKey: [...qk.notifications, unread], queryFn: () => accountApi.notifications({ unread, pageSize: 50 }) });
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: qk.notifications });
    void qc.invalidateQueries({ queryKey: qk.counters });
  };
  const readAll = useMutation({ mutationFn: accountApi.readAllNotifications, onSuccess: refresh });
  const open = useMutation({
    mutationFn: (n: { id: string; link: string; is_read: boolean }) => (n.is_read ? Promise.resolve(null) : accountApi.readNotification(n.id)),
    onSuccess: (_d, n) => {
      refresh();
      if (n.link) router.push(n.link);
    },
  });
  return (
    <section className="gv-ac-panel" aria-labelledby="notif-title">
      <CardHeader
        title={<span id="notif-title">Уведомления</span>}
        actions={
          <>
            <Button variant="link" onClick={() => setUnread((v) => !v)}>
              {unread ? "Показать все" : "Только непрочитанные"}
            </Button>
            <Button variant="line" loading={readAll.isPending} onClick={() => readAll.mutate()}>
              Прочитать все
            </Button>
          </>
        }
      />
      <QueryState query={list} isEmpty={(d) => d.results.length === 0} empty={<EmptyState compact title="Уведомлений нет" />}>
        {(data) => (
          <ul className="lc-list">
            {data.results.map((n) => (
              <li key={n.id} className={`lc-list-row${n.is_read ? "" : " is-unread"}`}>
                <button type="button" className="lc-row-button lc-grow" onClick={() => open.mutate(n)}>
                  <strong>{n.title}</strong> {!n.is_read && <span className="gv-dot" aria-label="не прочитано" />}
                  <div className="small muted">
                    {n.body} · {formatDateTime(n.created_at)}
                  </div>
                </button>
                <span className="gv-tag">{n.kind_label}</span>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </section>
  );
}

const show = (v: unknown) => (Array.isArray(v) ? v.join(", ") : v === null || v === undefined || v === "" ? "—" : String(v));

export function ProposalsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const list = useQuery({ queryKey: mineKeys.proposals(), queryFn: () => mineApi.proposals() });
  const [answering, setAnswering] = useState<string | null>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: mineKeys.proposalsAll });
  const withdraw = useMutation({ mutationFn: (id: string) => mineApi.withdrawProposal(id), onSuccess: refresh, onError: (e) => toast.error(e) });
  return (
    <section className="gv-ac-panel" aria-labelledby="prop-title">
      <CardHeader title={<span id="prop-title">Мои правки спотов</span>} description="Публичная карточка меняется только после решения модератора." />
      <QueryState query={list} isEmpty={(d) => d.results.length === 0} empty={<EmptyState compact title="Вы ещё не предлагали правок" text="Нажмите карандаш на фото спота, чтобы предложить изменение." />}>
        {(data) => (
          <div className="lc-stack">
            {data.results.map((p) => (
              <Card key={p.id} variant="panel">
                <CardHeader
                  title={<Link href={routes.spot(p.spot.slug)}>{p.spot.name}</Link>}
                  description={`Отправлено ${formatDate(p.created_at)}${p.is_reverted ? " · изменения откатаны модератором" : ""}`}
                  actions={<StatusBadge domain="proposal" status={choiceCode(p.status)} />}
                />
                <table className="gv-table">
                  <thead>
                    <tr>
                      <th scope="col">Поле</th>
                      <th scope="col">Было</th>
                      <th scope="col">Предложено</th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.changes.map((c) => (
                      <tr key={c.field}>
                        <td>{c.label}</td>
                        <td>{show(c.old)}</td>
                        <td>{show(c.new)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {p.moderator_comment && <p>Комментарий модератора: {p.moderator_comment}</p>}
                <div className="lc-form-actions">
                  {p.can_edit && (
                    <Button variant="primary" onClick={() => setAnswering(p.id)}>
                      Ответить модератору
                    </Button>
                  )}
                  {p.can_withdraw && (
                    <Button variant="link" onClick={() => withdraw.mutate(p.id)}>
                      Отозвать
                    </Button>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </QueryState>
      {answering && (
        <ReasonDialog
          open
          onClose={() => setAnswering(null)}
          title="Уточнение для модератора"
          reasonLabel="Комментарий и источник"
          reasonRequired
          confirmLabel="Отправить снова"
          onConfirm={(comment) =>
            mineApi.updateProposal(answering, { comment }).then(() => {
              toast.success("Правка снова на модерации");
              setAnswering(null);
              refresh();
            })
          }
        />
      )}
    </section>
  );
}

function ComplaintsBlock() {
  const qc = useQueryClient();
  const toast = useToast();
  const filed = useQuery({ queryKey: mineKeys.complaints("filed"), queryFn: () => mineApi.complaints("filed") });
  const against = useQuery({ queryKey: mineKeys.complaints("against"), queryFn: () => mineApi.complaints("against") });
  const [appealing, setAppealing] = useState<string | null>(null);
  return (
    <Card variant="panel">
      <CardHeader title="Жалобы" description="Ваши жалобы и решения модераторов по вашим материалам (с возможностью апелляции)." />
      <h4>Мои жалобы</h4>
      <QueryState query={filed} isEmpty={(d) => itemsOf(d).length === 0} empty={<p className="small muted">Вы не отправляли жалоб.</p>}>
        {(d) => (
          <ul className="lc-list">
            {(itemsOf(d) as MyComplaint[]).map((c) => (
              <li key={c.id} className="lc-list-row">
                <span className="lc-grow">
                  {choiceLabel(c.target_type)} · {choiceLabel(c.reason)} · {formatDate(c.created_at)}
                </span>
                <StatusBadge domain="complaint" status={choiceCode(c.status)} />
              </li>
            ))}
          </ul>
        )}
      </QueryState>
      <h4>Решения по моим материалам</h4>
      <QueryState query={against} isEmpty={(d) => itemsOf(d).length === 0} empty={<p className="small muted">Ограничений нет.</p>}>
        {(d) => (
          <ul className="lc-list">
            {(itemsOf(d) as ComplaintAgainstMe[]).map((c) => (
              <li key={c.id} className="lc-list-row">
                <span className="lc-grow">
                  {choiceLabel(c.target_type)} · {choiceLabel(c.action_taken)}
                  {c.appealed_at ? " · апелляция подана" : ""}
                </span>
                {c.can_appeal && (
                  <Button variant="line" onClick={() => setAppealing(c.id)}>
                    Обжаловать
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </QueryState>
      {appealing && (
        <ReasonDialog
          open
          onClose={() => setAppealing(null)}
          title="Апелляция"
          reasonLabel="Почему решение стоит пересмотреть"
          reasonRequired
          confirmLabel="Отправить"
          onConfirm={(text) =>
            mineApi.appeal(appealing, text).then(() => {
              toast.success("Апелляция отправлена модератору");
              setAppealing(null);
              void qc.invalidateQueries({ queryKey: mineKeys.complaintsAll });
            })
          }
        />
      )}
    </Card>
  );
}

export function ReviewsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const list = useQuery({ queryKey: mineKeys.reviews(), queryFn: () => mineApi.reviews() });
  const remove = useMutation({
    mutationFn: (id: string) => mineApi.deleteReview(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: mineKeys.reviewsAll }),
    onError: (e) => toast.error(e),
  });
  return (
    <section className="gv-ac-panel" aria-labelledby="rev-title">
      <CardHeader title={<span id="rev-title">Мои отзывы</span>} description="Отзыв виден всем после модерации; правка опубликованного отзыва тоже проходит проверку." />
      <QueryState query={list} isEmpty={(d) => d.results.length === 0} empty={<EmptyState compact title="Отзывов пока нет" />}>
        {(data) => (
          <ul className="lc-list">
            {data.results.map((r) => (
              <li key={r.id} className="lc-list-row">
                <div className="lc-grow">
                  <Link href={r.target.link}>
                    <strong>{r.target.name}</strong>
                  </Link>{" "}
                  <Rating value={r.rating} />
                  <p>{r.text}</p>
                  {r.has_pending_revision && <p className="small">Новая версия на модерации: {r.pending_rating}★ {r.pending_text}</p>}
                  {r.moderation_note && <p className="small muted">Комментарий модератора: {r.moderation_note}</p>}
                </div>
                <StatusBadge domain="review" status={choiceCode(r.status)} />
                <Button variant="link" onClick={() => remove.mutate(r.id)}>
                  Удалить
                </Button>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
      <ComplaintsBlock />
    </section>
  );
}

export function InvitesPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { me } = useMe();
  const list = useQuery({ queryKey: mineKeys.invites, queryFn: mineApi.invites });
  const done = (msg: string) => {
    toast.success(msg);
    void qc.invalidateQueries({ queryKey: mineKeys.invites });
    void qc.invalidateQueries({ queryKey: qk.me });
  };
  const accept = useMutation({ mutationFn: (t: string) => mineApi.acceptInvite(t), onSuccess: () => done("Вы в команде"), onError: (e) => toast.error(e) });
  const decline = useMutation({ mutationFn: (t: string) => mineApi.declineInvite(t), onSuccess: () => done("Приглашение отклонено"), onError: (e) => toast.error(e) });
  return (
    <section className="gv-ac-panel" aria-labelledby="inv-title">
      <CardHeader title={<span id="inv-title">Приглашения</span>} description="Роль в организации активируется только после принятия приглашения." />
      {me && !me.emailVerified && <p className="gv-field-error">Чтобы принять приглашение, подтвердите email в настройках.</p>}
      <QueryState query={list} isEmpty={(d) => d.length === 0} empty={<EmptyState compact title="Приглашений нет" />}>
        {(items) => (
          <ul className="lc-list">
            {items.map((i) => (
              <li key={i.id} className="lc-list-row">
                <Avatar media={i.organization.logo} name={i.organization.name} size={44} />
                <div className="lc-grow">
                  <strong>{i.organization.name}</strong>
                  <div className="small muted">
                    Роль: {MEMBERSHIP_ROLE_LABELS[i.role as keyof typeof MEMBERSHIP_ROLE_LABELS] ?? i.role}
                    {i.invited_by ? ` · пригласил(а) ${i.invited_by.display_name}` : ""} · до {formatDate(i.expires_at)}
                  </div>
                  {i.message && <p className="small">{i.message}</p>}
                </div>
                <Button variant="primary" loading={accept.isPending} onClick={() => accept.mutate(i.token)}>
                  Принять
                </Button>
                <Button variant="link" onClick={() => decline.mutate(i.token)}>
                  Отклонить
                </Button>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </section>
  );
}

const VISIBILITY_OPTIONS: Array<{ value: DiaryVisibility; label: string }> = [
  { value: "private", label: "Только я" },
  { value: "community", label: "Участники GG Surfer" },
  { value: "public", label: "Все" },
];

function DiaryForm({ entry, onDone }: { entry: DiaryEntry | null; onDone: () => void }) {
  const spots = useQuery({ queryKey: mineKeys.spotOptions, queryFn: mineApi.spotOptions });
  const [f, setF] = useState<DiaryInput>({
    date: entry?.date ?? new Date().toISOString().slice(0, 10),
    spot_id: entry?.spot?.id ?? "",
    spot_name: entry?.spot_name ?? "",
    duration_min: entry?.duration_min ?? 90,
    board_note: entry?.board_note ?? "",
    conditions: entry?.conditions ?? "",
    mood_rating: entry?.mood_rating ?? null,
    notes: entry?.notes ?? "",
    visibility: entry?.visibility ?? "private",
  });
  const [photos, setPhotos] = useState<Media[]>(entry?.photos ?? []);
  const set = <K extends keyof DiaryInput>(k: K, v: DiaryInput[K]) => setF((x) => ({ ...x, [k]: v }));
  const save = useMutation({
    mutationFn: () => {
      const body = { ...f, spot_id: f.spot_id || null, photo_ids: photos.map((p) => p.id) };
      return entry ? mineApi.updateDiary(entry.id, body) : mineApi.createDiary(body);
    },
    onSuccess: onDone,
  });
  return (
    <form
      className="lc-form"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="lc-form-row">
        <TextInput label="Дата" type="date" required value={f.date} onChange={(e) => set("date", e.target.value)} />
        <TextInput label="Минут на воде" type="number" min={0} value={f.duration_min ?? ""} onChange={(e) => set("duration_min", e.target.value ? Number(e.target.value) : null)} />
      </div>
      <Select label="Спот" placeholder="Другое место" value={f.spot_id ?? ""} onChange={(e) => set("spot_id", e.target.value)} options={itemsOf(spots.data).map((s) => ({ value: s.id, label: s.name }))} />
      {!f.spot_id && <TextInput label="Название места" value={f.spot_name ?? ""} onChange={(e) => set("spot_name", e.target.value)} />}
      <TextInput label="Доска" value={f.board_note ?? ""} onChange={(e) => set("board_note", e.target.value)} />
      <TextInput label="Условия" value={f.conditions ?? ""} onChange={(e) => set("conditions", e.target.value)} placeholder="Волна по пояс, оффшор" />
      <RatingInput label="Впечатления" value={f.mood_rating ?? 0} onChange={(v: number) => set("mood_rating", v || null)} />
      <Textarea label="Заметки" value={f.notes ?? ""} onChange={(e) => set("notes", e.target.value)} rows={3} />
      <Select label="Кто видит запись" value={f.visibility ?? "private"} onChange={(e) => set("visibility", e.target.value as DiaryVisibility)} options={VISIBILITY_OPTIONS} />
      <MediaUploader purpose="diary_photo" maxFiles={10} value={photos} onChange={setPhotos} label="Фото" />
      {save.isError && <p className="gv-field-error" role="alert">{errText(save.error, "Не удалось сохранить запись.")}</p>}
      <Button type="submit" variant="primary" loading={save.isPending}>
        Сохранить
      </Button>
    </form>
  );
}

export function DiaryPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { me } = useMe();
  const stats = useQuery({ queryKey: mineKeys.diaryStats, queryFn: mineApi.diaryStats });
  const list = useQuery({ queryKey: mineKeys.diaryList(1), queryFn: () => mineApi.diary(1) });
  const [editing, setEditing] = useState<DiaryEntry | "new" | null>(null);
  const refresh = () => {
    setEditing(null);
    void qc.invalidateQueries({ queryKey: mineKeys.diary });
  };
  const remove = useMutation({ mutationFn: (id: string) => mineApi.deleteDiary(id), onSuccess: refresh, onError: (e) => toast.error(e) });
  const ggOn = Boolean((me?.raw?.profile as { gg_surfer_enabled?: boolean } | undefined)?.gg_surfer_enabled);
  return (
    <section className="gv-ac-panel" aria-labelledby="diary-title">
      <CardHeader
        title={<span id="diary-title">Дневник катания</span>}
        description="Дни на воде, споты и впечатления. Видимость задаётся для каждой записи; геолокация не собирается."
        actions={
          <Button variant="primary" icon="plus" onClick={() => setEditing("new")}>
            Новая запись
          </Button>
        }
      />
      {!ggOn && (
        <p className="small muted">
          GG Surfer выключен — записи видны только вам. Включить участие в сообществе можно в <Link href={routes.account.settings}>настройках</Link>.
        </p>
      )}
      {stats.data && (
        <StatStrip
          items={[
            { label: "Дней катания", value: stats.data.ride_days },
            { label: "В этом году", value: stats.data.this_year_days },
            { label: "Спотов", value: stats.data.spots_visited },
            { label: "Лучшая серия", value: `${stats.data.longest_streak_days} дн.` },
          ]}
        />
      )}
      <QueryState query={list} isEmpty={(d) => d.results.length === 0} empty={<EmptyState compact title="Записей пока нет" text="Отметьте первый день на воде." />}>
        {(data) => (
          <ul className="lc-list">
            {data.results.map((e) => (
              <li key={e.id} className="lc-list-row">
                {e.photos[0] ? <MediaImage media={e.photos[0]} alt="" className="lc-thumb" /> : null}
                <div className="lc-grow">
                  <strong>
                    {formatDate(e.date)} · {e.spot?.name ?? e.place_name ?? e.spot_name}
                  </strong>
                  <div className="small muted">
                    {[e.duration_min ? `${e.duration_min} мин` : "", e.conditions, e.board_note, e.visibility_label].filter(Boolean).join(" · ")}
                  </div>
                  {e.notes && <p className="small">{e.notes}</p>}
                </div>
                <Button variant="line" onClick={() => setEditing(e)}>
                  Изменить
                </Button>
                <Button variant="link" onClick={() => remove.mutate(e.id)}>
                  Удалить
                </Button>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
      <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing === "new" ? "Новая запись" : "Запись дневника"} size="wide">
        {editing !== null && <DiaryForm entry={editing === "new" ? null : editing} onDone={refresh} />}
      </Modal>
    </section>
  );
}
