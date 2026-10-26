"use client";
/** Вкладки кабинета школы (SCH-03..13, F05, F15, AT-06/09, ATX-18/35). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { orgApi, sk, type Member, type OrgManage, type Program, type ProgramInput } from "@/lib/api/schoolCabinet";
import { sessionsApi, type ManagedSession, type SessionParticipant } from "@/lib/api/learningCabinet";
import { isApiError } from "@/lib/api/errors";
import type { Media } from "@/lib/api/types";
import { qk } from "@/lib/api/keys";
import { routes } from "@/lib/routes";
import { formatDate, formatMoney } from "@/lib/format";
import { MEMBERSHIP_ROLE_LABELS } from "@/lib/labels";
import { useMe } from "@/lib/auth/hooks";
import {
  Avatar,
  Button,
  ButtonLink,
  Card,
  CardHeader,
  Checkbox,
  ChipGroup,
  EmptyState,
  MediaUploader,
  Modal,
  QueryState,
  Rating,
  Select,
  StatStrip,
  StatusBadge,
  Textarea,
  TextInput,
  useToast,
} from "@/components/ui";
import { ScheduleBoard } from "@/components/learning-cabinet/ScheduleBoard";
import { SessionCard } from "@/components/learning-cabinet/SessionCard";
import { CancelSessionModal, CompleteSessionModal, RescheduleSessionModal } from "@/components/learning-cabinet/SessionActionModals";
import { StudentsBoard } from "@/components/learning-cabinet/StudentsBoard";
import { MetricsPanel } from "@/components/learning-cabinet/MetricsPanel";
import { FormAlert } from "@/components/learning-cabinet/FormAlert";
import { useRegionZones, useRegions, useSpots } from "@/components/learning-cabinet/hooks";
import { AGE_CATEGORY_OPTIONS, LANGUAGE_OPTIONS, LESSON_FORMAT_OPTIONS, LEVEL_OPTIONS, OFFER_FORMAT_OPTIONS } from "@/components/learning-cabinet/dictionaries";
import { addDays, todayIn, zonedToUtcIso } from "@/components/learning-cabinet/time";
import { DEFAULT_TIME_ZONE } from "@/lib/format";

const errText = (e: unknown, fallback: string) => (isApiError(e) ? e.message : fallback);

function useOrgZone(org: OrgManage | null) {
  const zoneOf = useRegionZones();
  return zoneOf(org?.region?.slug) ?? DEFAULT_TIME_ZONE;
}

const MISSING_LABELS: Record<string, string> = {
  name: "название",
  description: "описание",
  region: "регион",
  spots_or_address: "спот или адрес",
};

// ── Обзор ─────────────────────────────────────────────────────────────────────────────────────────────
export function OrgOverview({ id, org, role }: { id: string; org: OrgManage | null; role: string | null }) {
  const zone = useOrgZone(org);
  const today = todayIn(zone);
  const sessions = useQuery({
    queryKey: sk.sessions(id, today, addDays(today, 7), zone),
    queryFn: () => orgApi.sessions.list(id, { from: today, to: addDays(today, 7), tz: zone }),
    enabled: Boolean(org),
  });
  if (!org) {
    return (
      <Card variant="panel">
        <CardHeader title={`Вы в команде как «${MEMBERSHIP_ROLE_LABELS[role as keyof typeof MEMBERSHIP_ROLE_LABELS] ?? role}»`} />
        <p>Назначенные вам занятия школы видны в едином расписании инструктора.</p>
        <ButtonLink href={`${routes.account.instructor}/schedule`} variant="primary" iconRight="arrow">
          Моё расписание
        </ButtonLink>
      </Card>
    );
  }
  const upcoming = (sessions.data ?? []).filter((s) => s.status === "scheduled");
  return (
    <div className="lc-stack">
      <StatStrip
        items={[
          { label: "Команда", value: org.members_count },
          { label: "Приглашения", value: org.pending_invites_count },
          { label: "Занятий за 7 дней", value: sessions.isPending ? "…" : upcoming.length },
          { label: "Рейтинг", value: org.rating_count ? `${org.rating_avg} (${org.rating_count})` : "—" },
        ]}
      />
      {org.missing_fields.length > 0 && (
        <FormAlert tone="warn" title="Профиль не готов к публикации">
          Заполните: {org.missing_fields.map((f) => MISSING_LABELS[f] ?? f).join(", ")}.{" "}
          <Link href={`${routes.account.org(id)}/profile`}>Профиль школы →</Link>
        </FormAlert>
      )}
      <Card variant="panel">
        <CardHeader title="Ближайшие занятия" actions={<ButtonLink href={`${routes.account.org(id)}/schedule`} variant="link">Расписание →</ButtonLink>} />
        <QueryState query={sessions} isEmpty={() => upcoming.length === 0} empty={<EmptyState compact title="На неделю занятий нет" />}>
          {() => (
            <div className="lc-stack">
              {upcoming.slice(0, 5).map((s) => (
                <SessionCard key={s.id} session={s} showInstructor showKind={false} summary={s.bookings_summary} waitlistCount={s.waitlist_count} />
              ))}
            </div>
          )}
        </QueryState>
      </Card>
    </div>
  );
}

// ── Профиль ───────────────────────────────────────────────────────────────────────────────────────────
export function OrgProfileTab({ id, org }: { id: string; org: OrgManage }) {
  const qc = useQueryClient();
  const toast = useToast();
  const regions = useRegions();
  const [f, setF] = useState(() => ({
    name: org.name,
    short_description: org.short_description,
    description: org.description,
    region_id: org.region ? String(org.region.id) : "",
    city: org.city,
    address: org.address,
    phone: org.phone,
    email: org.email,
    website: org.website,
    price_from: org.price_from ?? "",
    formats: org.formats,
    languages: org.languages,
    spot_ids: org.spots.map((s) => s.id),
  }));
  const [logo, setLogo] = useState<Media[]>(org.logo ? [org.logo] : []);
  const [cover, setCover] = useState<Media[]>(org.cover ? [org.cover] : []);
  const [gallery, setGallery] = useState<Media[]>(org.gallery);
  const regionSlug = regions.data?.find((r) => String(r.id) === f.region_id)?.slug;
  const allSpots = useSpots();
  const regionSpots = (allSpots.data ?? []).filter((s) => !regionSlug || s.region?.slug === regionSlug || f.spot_ids.includes(s.id));
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const refresh = (data: OrgManage) => {
    qc.setQueryData(sk.manage(id), data);
    void qc.invalidateQueries({ queryKey: qk.me });
  };
  const save = useMutation({
    mutationFn: () =>
      orgApi.update(id, {
        ...f,
        region_id: f.region_id ? Number(f.region_id) : null,
        price_from: f.price_from || null,
        logo_id: logo[0]?.id ?? null,
        cover_id: cover[0]?.id ?? null,
        gallery_ids: gallery.map((m) => m.id),
      }),
    onSuccess: (data) => {
      refresh(data);
      toast.success("Профиль сохранён");
    },
  });
  const submit = useMutation({
    mutationFn: () => orgApi.submit(id),
    onSuccess: (data) => {
      refresh(data);
      toast.success("Отправлено на проверку модератору");
    },
  });
  return (
    <form
      className="lc-form"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <TextInput label="Название" required value={f.name} onChange={(e) => set("name", e.target.value)} maxLength={160} />
      <TextInput label="Кратко" value={f.short_description} onChange={(e) => set("short_description", e.target.value)} maxLength={300} />
      <Textarea label="Описание" value={f.description} onChange={(e) => set("description", e.target.value)} rows={5} maxLength={5000} />
      <div className="lc-form-row">
        <Select
          label="Регион"
          placeholder="Выберите регион"
          value={f.region_id}
          onChange={(e) => set("region_id", e.target.value)}
          options={(regions.data ?? []).map((r) => ({ value: String(r.id), label: r.name }))}
        />
        <TextInput label="Город" value={f.city} onChange={(e) => set("city", e.target.value)} />
      </div>
      <TextInput label="Адрес" value={f.address} onChange={(e) => set("address", e.target.value)} />
      {regionSpots.length > 0 && (
        <ChipGroup label="Споты занятий" value={f.spot_ids} onChange={(v) => set("spot_ids", v)} options={regionSpots.map((s) => ({ value: s.id, label: s.name }))} />
      )}
      <ChipGroup label="Форматы обучения" value={f.formats} onChange={(v) => set("formats", v)} options={LESSON_FORMAT_OPTIONS} />
      <ChipGroup label="Языки" value={f.languages} onChange={(v) => set("languages", v)} options={LANGUAGE_OPTIONS} />
      <div className="lc-form-row">
        <TextInput label="Телефон" value={f.phone} onChange={(e) => set("phone", e.target.value)} hint="Виден только в кабинете" />
        <TextInput label="Email" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} />
      </div>
      <div className="lc-form-row">
        <TextInput label="Сайт" type="url" value={f.website} onChange={(e) => set("website", e.target.value)} />
        <TextInput label="Стоимость от, ₽" inputMode="decimal" value={f.price_from} onChange={(e) => set("price_from", e.target.value)} />
      </div>
      <MediaUploader purpose="org_logo" maxFiles={1} value={logo} onChange={setLogo} label="Логотип" />
      <MediaUploader purpose="org_cover" maxFiles={1} value={cover} onChange={setCover} label="Обложка" />
      <MediaUploader purpose="org_gallery" maxFiles={10} value={gallery} onChange={setGallery} label="Фотографии школы" hint="До 10 фото" />
      {save.isError && <FormAlert>{errText(save.error, "Не удалось сохранить профиль.")}</FormAlert>}
      {submit.isError && <FormAlert>{errText(submit.error, "Не удалось отправить на проверку.")}</FormAlert>}
      <div className="lc-form-actions">
        <Button type="submit" variant="primary" loading={save.isPending}>
          Сохранить изменения
        </Button>
        {(org.status === "draft" || org.status === "archived") && (
          <Button type="button" variant="line" loading={submit.isPending} onClick={() => submit.mutate()}>
            Отправить на проверку
          </Button>
        )}
        <StatusBadge domain="organization" status={org.status} />
      </div>
    </form>
  );
}

// ── Программы ─────────────────────────────────────────────────────────────────────────────────────────
const emptyProgram: ProgramInput = { title: "", price: "", format: "group", age_category: "all", duration_min: 120, sessions_count: 1, max_group_size: 8, level: "beginner", equipment_included: true, description: "" };

function ProgramForm({ id, program, onDone }: { id: string; program: Program | null; onDone: () => void }) {
  const [f, setF] = useState<ProgramInput>(program ? { ...program, price: program.price } : emptyProgram);
  const set = <K extends keyof ProgramInput>(k: K, v: ProgramInput[K]) => setF((x) => ({ ...x, [k]: v }));
  const save = useMutation({
    mutationFn: () => (program ? orgApi.programs.update(id, program.id, f) : orgApi.programs.create(id, f)),
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
      <TextInput label="Название" required value={f.title} onChange={(e) => set("title", e.target.value)} />
      <Textarea label="Описание" value={f.description ?? ""} onChange={(e) => set("description", e.target.value)} rows={3} />
      <div className="lc-form-row">
        <Select label="Уровень" value={f.level ?? ""} onChange={(e) => set("level", e.target.value)} options={LEVEL_OPTIONS} />
        <Select label="Возраст" value={f.age_category ?? "all"} onChange={(e) => set("age_category", e.target.value as ProgramInput["age_category"])} options={AGE_CATEGORY_OPTIONS} />
        <Select label="Формат" value={f.format ?? "group"} onChange={(e) => set("format", e.target.value as ProgramInput["format"])} options={OFFER_FORMAT_OPTIONS} />
      </div>
      <div className="lc-form-row">
        <TextInput label="Длительность, мин" type="number" min={15} value={f.duration_min ?? 120} onChange={(e) => set("duration_min", Number(e.target.value))} />
        <TextInput label="Занятий в курсе" type="number" min={1} value={f.sessions_count ?? 1} onChange={(e) => set("sessions_count", Number(e.target.value))} />
        <TextInput label="Макс. в группе" type="number" min={1} value={f.max_group_size ?? 8} onChange={(e) => set("max_group_size", Number(e.target.value))} />
        <TextInput label="Цена, ₽" required inputMode="decimal" value={f.price} onChange={(e) => set("price", e.target.value)} />
      </div>
      <Checkbox label="Снаряжение включено" checked={Boolean(f.equipment_included)} onChange={(e) => set("equipment_included", e.target.checked)} />
      {save.isError && <FormAlert>{errText(save.error, "Не удалось сохранить программу.")}</FormAlert>}
      <Button type="submit" variant="primary" loading={save.isPending}>
        Сохранить
      </Button>
    </form>
  );
}

export function ProgramsTab({ id }: { id: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const list = useQuery({ queryKey: sk.programs(id), queryFn: () => orgApi.programs.list(id) });
  const [editing, setEditing] = useState<Program | "new" | null>(null);
  const refresh = () => {
    setEditing(null);
    void qc.invalidateQueries({ queryKey: sk.org(id) });
  };
  const remove = useMutation({ mutationFn: (pid: string) => orgApi.programs.remove(id, pid), onSuccess: refresh, onError: (e) => toast.error(e) });
  return (
    <div className="lc-stack">
      <div className="lc-toolbar">
        <Button variant="primary" icon="plus" onClick={() => setEditing("new")}>
          Новая программа
        </Button>
      </div>
      <QueryState query={list} isEmpty={(d) => d.length === 0} empty={<EmptyState compact title="Программ пока нет" text="Опишите уровни, длительность, стоимость и размер группы." />}>
        {(items) => (
          <ul className="lc-list">
            {items.map((p) => (
              <li key={p.id} className="lc-list-row">
                <div className="lc-grow">
                  <strong>{p.title}</strong> {!p.is_active && <span className="muted">(в архиве)</span>}
                  <div className="small muted">
                    {p.duration_min} мин · до {p.max_group_size} чел. · {p.sessions_count} зан. · {formatMoney(p.price, p.currency)} · ближайших занятий: {p.upcoming_sessions}
                  </div>
                </div>
                <Button variant="line" onClick={() => setEditing(p)}>
                  Изменить
                </Button>
                <Button variant="link" onClick={() => remove.mutate(p.id)}>
                  Удалить
                </Button>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
      <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing === "new" ? "Новая программа" : "Программа"} size="wide">
        {editing !== null && <ProgramForm id={id} program={editing === "new" ? null : editing} onDone={refresh} />}
      </Modal>
    </div>
  );
}

// ── Расписание ────────────────────────────────────────────────────────────────────────────────────────
function useTeachers(id: string) {
  return useQuery({ queryKey: sk.members(id, "active"), queryFn: () => orgApi.members(id, "active") });
}

function NewSessionForm({ id, zone, onDone }: { id: string; zone: string; onDone: () => void }) {
  const programs = useQuery({ queryKey: sk.programs(id), queryFn: () => orgApi.programs.list(id) });
  const teachers = useTeachers(id);
  const spots = useSpots();
  const [programId, setProgramId] = useState("");
  const [instructorId, setInstructorId] = useState("");
  const [spot, setSpot] = useState("");
  const [date, setDate] = useState(addDays(todayIn(zone), 1));
  const [time, setTime] = useState("10:00");
  const create = useMutation({
    mutationFn: () =>
      orgApi.sessions.create(id, {
        program_id: programId || null,
        instructor_id: instructorId || null,
        spot_slug: spot || null,
        starts_at: zonedToUtcIso(date, time, zone),
      }),
    onSuccess: onDone,
  });
  return (
    <form
      className="lc-form"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <Select label="Программа" required placeholder="Выберите программу" value={programId} onChange={(e) => setProgramId(e.target.value)} options={(programs.data ?? []).filter((p) => p.is_active).map((p) => ({ value: p.id, label: p.title }))} />
      <Select
        label="Инструктор"
        placeholder="Назначить позже"
        value={instructorId}
        onChange={(e) => setInstructorId(e.target.value)}
        options={(teachers.data ?? []).map((m) => ({ value: m.account.id, label: `${m.account.display_name} · ${MEMBERSHIP_ROLE_LABELS[m.role]}` }))}
      />
      <Select label="Спот" placeholder="Без спота" value={spot} onChange={(e) => setSpot(e.target.value)} options={(spots.data ?? []).map((s) => ({ value: s.slug, label: s.name }))} />
      <div className="lc-form-row">
        <TextInput label="Дата" type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
        <TextInput label="Начало" type="time" required value={time} onChange={(e) => setTime(e.target.value)} hint={zone} />
      </div>
      {create.isError && <FormAlert>{errText(create.error, "Не удалось создать занятие.")}</FormAlert>}
      <Button type="submit" variant="primary" loading={create.isPending} disabled={!programId}>
        Создать занятие
      </Button>
    </form>
  );
}

type Action = { kind: "complete" | "reschedule" | "cancel" | "assign"; session: ManagedSession } | null;

function AssignModal({ id, session, onClose, onDone }: { id: string; session: ManagedSession; onClose: () => void; onDone: () => void }) {
  const teachers = useTeachers(id);
  const [value, setValue] = useState(session.instructor?.id ?? "");
  const assign = useMutation({ mutationFn: () => sessionsApi.assign(session.id, value || null), onSuccess: onDone });
  return (
    <Modal
      open
      onClose={onClose}
      title="Назначить инструктора"
      footer={
        <Button variant="primary" loading={assign.isPending} onClick={() => assign.mutate()}>
          Назначить
        </Button>
      }
    >
      <Select label="Инструктор" placeholder="Без инструктора" value={value} onChange={(e) => setValue(e.target.value)} options={(teachers.data ?? []).map((m) => ({ value: m.account.id, label: m.account.display_name }))} />
      {assign.isError && <FormAlert>{errText(assign.error, "Не удалось назначить.")}</FormAlert>}
    </Modal>
  );
}

function CompleteWithParticipants({ id, session, onClose, onDone }: { id: string; session: ManagedSession; onClose: () => void; onDone: () => void }) {
  const bookings = useQuery({ queryKey: sk.sessionBookings(id, session.id), queryFn: () => orgApi.sessions.bookings(id, session) });
  const participants: SessionParticipant[] = (bookings.data ?? [])
    .filter((b) => b.status === "confirmed" || b.status === "in_progress")
    .map((b) => ({ booking_id: b.id, status: b.status, seats: b.seats, name: b.participant_name || b.customer.display_name, participant_is_minor: b.participant_is_minor, customer: b.customer }));
  return <CompleteSessionModal session={session} participants={participants} loading={bookings.isPending} loadError={bookings.error} open onClose={onClose} onDone={onDone} />;
}

export function ScheduleTab({ id, org }: { id: string; org: OrgManage }) {
  const zone = useOrgZone(org);
  const qc = useQueryClient();
  const [action, setAction] = useState<Action>(null);
  const [creating, setCreating] = useState(false);
  const close = () => setAction(null);
  const refresh = () => {
    setAction(null);
    setCreating(false);
    void qc.invalidateQueries({ queryKey: sk.sessionsAll(id) });
  };
  return (
    <>
      <ScheduleBoard<ManagedSession>
        viewTz={zone}
        queryKey={(from, to) => sk.sessions(id, from, to, zone)}
        fetcher={(from, to) => orgApi.sessions.list(id, { from, to, tz: zone })}
        emptyTitle="Занятий в этом периоде нет"
        toolbarExtra={
          <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
            Новое занятие
          </Button>
        }
        renderSession={(s) => {
          const active = s.status === "scheduled" || s.status === "in_progress";
          return (
            <SessionCard
              session={s}
              showInstructor
              showKind={false}
              summary={s.bookings_summary}
              waitlistCount={s.waitlist_count}
              actions={
                active ? (
                  <>
                    <Button variant="soft" onClick={() => setAction({ kind: "assign", session: s })}>
                      Инструктор
                    </Button>
                    <Button variant="line" onClick={() => setAction({ kind: "reschedule", session: s })}>
                      Перенести
                    </Button>
                    <Button variant="line" onClick={() => setAction({ kind: "complete", session: s })}>
                      Провести
                    </Button>
                    <Button variant="link" onClick={() => setAction({ kind: "cancel", session: s })}>
                      Отменить
                    </Button>
                  </>
                ) : null
              }
            />
          );
        }}
      />
      <Modal open={creating} onClose={() => setCreating(false)} title="Новое занятие" size="wide">
        <NewSessionForm id={id} zone={zone} onDone={refresh} />
      </Modal>
      {action?.kind === "assign" && <AssignModal id={id} session={action.session} onClose={close} onDone={refresh} />}
      {action?.kind === "complete" && <CompleteWithParticipants id={id} session={action.session} onClose={close} onDone={refresh} />}
      {action?.kind === "reschedule" && <RescheduleSessionModal session={action.session} open onClose={close} onDone={refresh} />}
      {action?.kind === "cancel" && <CancelSessionModal session={action.session} open onClose={close} onDone={refresh} />}
    </>
  );
}

// ── Ученики ───────────────────────────────────────────────────────────────────────────────────────────
export function StudentsTab({ id }: { id: string }) {
  return (
    <StudentsBoard
      queryKey={(q, repeat, page) => sk.students(id, q, repeat, page)}
      fetcher={(q) => orgApi.students(id, q)}
      organizationId={id}
      inlineNotes={false}
      canManage
      emptyText="Ученики появятся после записей на занятия школы."
    />
  );
}

// ── Команда ───────────────────────────────────────────────────────────────────────────────────────────
const ROLE_OPTIONS = (["manager", "instructor", "staff"] as const).map((r) => ({ value: r, label: MEMBERSHIP_ROLE_LABELS[r] }));

export function TeamTab({ id, org, role }: { id: string; org: OrgManage | null; role: string | null }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { me } = useMe();
  const isOwner = role === "owner";
  const canInvite = role === "owner" || role === "manager";
  const members = useQuery({ queryKey: sk.members(id, "active"), queryFn: () => orgApi.members(id, "active") });
  const invites = useQuery({ queryKey: sk.invites(id), queryFn: () => orgApi.invites(id), enabled: canInvite });
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"manager" | "instructor" | "staff">("instructor");
  const refresh = () => void qc.invalidateQueries({ queryKey: sk.org(id) });
  const onError = (e: unknown) => toast.error(e);
  const changeRole = useMutation({ mutationFn: (v: { m: Member; role: string }) => orgApi.updateMember(id, v.m.id, { role: v.role as Member["role"] }), onSuccess: refresh, onError });
  const revoke = useMutation({
    mutationFn: (m: Member) => orgApi.revokeMember(id, m.id),
    onSuccess: () => {
      toast.success("Доступ отозван. История занятий и обращений сохранена.");
      refresh();
    },
    onError,
  });
  const invite = useMutation({
    mutationFn: () => orgApi.invite(id, { email, role: inviteRole }),
    onSuccess: () => {
      setEmail("");
      toast.success("Приглашение отправлено");
      refresh();
    },
    onError,
  });
  const revokeInvite = useMutation({ mutationFn: (inviteId: string) => orgApi.revokeInvite(inviteId), onSuccess: refresh, onError });
  const transfer = useMutation({
    mutationFn: (accountId: string) => orgApi.transferOwnership(id, accountId),
    onSuccess: () => {
      toast.success("Владение передано");
      void qc.invalidateQueries({ queryKey: qk.me });
      refresh();
    },
    onError,
  });
  const leave = useMutation({
    mutationFn: () => orgApi.leave(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.me });
      window.location.assign(routes.account.orgs);
    },
    onError,
  });
  return (
    <div className="lc-stack">
      <QueryState query={members} isEmpty={(d) => d.length === 0}>
        {(items) => (
          <ul className="lc-list">
            {items.map((m) => {
              const self = m.account.id === me?.id;
              return (
                <li key={m.id} className="lc-list-row">
                  <Avatar media={m.account.avatar} name={m.account.display_name} size={40} />
                  <div className="lc-grow">
                    <strong>{m.account.display_name}</strong> {self && <span className="muted">(вы)</span>}
                    <div className="small muted">с {formatDate(m.joined_at)}</div>
                  </div>
                  {isOwner && m.role !== "owner" ? (
                    <Select label="Роль" hideLabel value={m.role} onChange={(e) => changeRole.mutate({ m, role: e.target.value })} options={ROLE_OPTIONS} />
                  ) : (
                    <span className="gv-tag">{MEMBERSHIP_ROLE_LABELS[m.role]}</span>
                  )}
                  {isOwner && m.role !== "owner" && (
                    <Button variant="link" onClick={() => transfer.mutate(m.account.id)}>
                      Передать владение
                    </Button>
                  )}
                  {canInvite && m.role !== "owner" && !self && (isOwner || m.role === "instructor" || m.role === "staff") && (
                    <Button variant="link" onClick={() => revoke.mutate(m)}>
                      Отозвать доступ
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </QueryState>
      {canInvite && (
        <Card variant="panel">
          <CardHeader title="Пригласить в команду" description="Приглашение адресуется аккаунту по email; роль активируется после принятия." />
          <form
            className="lc-inline-form"
            onSubmit={(e) => {
              e.preventDefault();
              invite.mutate();
            }}
          >
            <TextInput label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            <Select label="Роль" value={inviteRole} onChange={(e) => setInviteRole(e.target.value as typeof inviteRole)} options={isOwner ? ROLE_OPTIONS : ROLE_OPTIONS.filter((o) => o.value !== "manager")} />
            <Button type="submit" variant="primary" loading={invite.isPending}>
              Пригласить
            </Button>
          </form>
          {(invites.data ?? []).length > 0 && (
            <ul className="lc-list">
              {(invites.data ?? []).map((i) => (
                <li key={i.id} className="lc-list-row">
                  <span className="lc-grow">
                    {i.email} · {MEMBERSHIP_ROLE_LABELS[i.role]} · до {formatDate(i.expires_at)}
                  </span>
                  <Button variant="link" onClick={() => revokeInvite.mutate(i.id)}>
                    Отозвать
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
      {!isOwner && (
        <div>
          <Button variant="danger" loading={leave.isPending} onClick={() => leave.mutate()}>
            Выйти из организации
          </Button>
        </div>
      )}
      {org === null && !canInvite && <p className="small muted">Управление командой доступно владельцу и менеджерам.</p>}
    </div>
  );
}

// ── Оборудование, обращения, аналитика, отзывы ────────────────────────────────────────────────────────
export function EquipmentTab({ id }: { id: string }) {
  const list = useQuery({ queryKey: sk.inventory(id), queryFn: () => orgApi.inventory(id) });
  return (
    <div className="lc-stack">
      <div className="lc-toolbar">
        <ButtonLink href={`${routes.account.rental}?organization=${id}`} variant="primary" icon="plus">
          Управлять инвентарём
        </ButtonLink>
      </div>
      <QueryState query={list} isEmpty={(d) => d.results.length === 0} empty={<EmptyState compact title="Оборудования пока нет" text="Доски и гидрокостюмы школы для занятий и аренды." />}>
        {(data) => (
          <ul className="lc-list">
            {data.results.map((i) => (
              <li key={i.id} className="lc-list-row">
                <div className="lc-grow">
                  <strong>{i.title}</strong>
                  <div className="small muted">
                    {i.kind_label} {i.size && `· ${i.size}`} · {i.condition_label}
                  </div>
                </div>
                <span className="gv-tag">{i.status_label}</span>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </div>
  );
}

export function InquiriesTab({ id }: { id: string }) {
  const list = useQuery({ queryKey: sk.inquiries(id), queryFn: () => orgApi.inquiries(id) });
  return (
    <div className="lc-stack">
      <div className="lc-toolbar">
        <ButtonLink href={`${routes.account.inquiries}?organization=${id}`} variant="primary" iconRight="arrow">
          Все обращения школы
        </ButtonLink>
        <ButtonLink href={`${routes.account.bookings}?box=provider&organization=${id}`} variant="line">
          Записи учеников
        </ButtonLink>
      </div>
      <QueryState query={list} isEmpty={(d) => d.results.length === 0} empty={<EmptyState compact title="Обращений пока нет" />}>
        {(data) => (
          <ul className="lc-list">
            {data.results.map((q) => (
              <li key={q.id} className="lc-list-row">
                <Link className="lc-grow" href={routes.account.inquiry(q.id)}>
                  <strong>{q.subject}</strong>
                  <div className="small muted">
                    {q.counterpart?.name} · {q.last_message?.body ?? q.kind_label}
                  </div>
                </Link>
                {q.unread_count > 0 && <span className="gv-count">{q.unread_count}</span>}
                <span className="gv-tag">{q.status_label}</span>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </div>
  );
}

export function AnalyticsTab({ id, org }: { id: string; org: OrgManage }) {
  const zone = useOrgZone(org);
  return (
    <MetricsPanel
      scope="school"
      organizationId={id}
      timeZone={zone}
      title="Аналитика школы"
      stripKeys={["fill_rate", "sessions_completed", "attendance", "repeat_students", "conversion", "rating"]}
    />
  );
}

export function ReviewsTab({ id }: { id: string }) {
  const [page] = useState(1);
  const list = useQuery({ queryKey: sk.reviews(id, page), queryFn: () => orgApi.reviews(id, page) });
  return (
    <QueryState query={list} isEmpty={(d) => d.results.length === 0} empty={<EmptyState compact title="Отзывов пока нет" text="Отзывы оставляют ученики после завершённых занятий; публикуются после модерации." />}>
      {(data) => (
        <ul className="lc-list">
          {data.results.map((r) => (
            <li key={r.id} className="lc-list-row">
              <Avatar media={r.author.avatar} name={r.author.display_name} size={40} />
              <div className="lc-grow">
                <strong>{r.author.display_name}</strong> <Rating value={r.rating} />
                <p>{r.text}</p>
                <div className="small muted">
                  {r.context_label} {r.published_at && `· ${formatDate(r.published_at)}`}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </QueryState>
  );
}
