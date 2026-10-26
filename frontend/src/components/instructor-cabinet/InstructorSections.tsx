"use client";
/**
 * Подразделы кабинета инструктора: расписание (школы + частные слоты, INS-07/AT-06/F11), ученики (SCH-10),
 * сертификаты (INS-03/04, TRUST-03) и статистика (MET-04).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ik, instructorApi, type CertificateOwn } from "@/lib/api/instructorCabinet";
import type { Media } from "@/lib/api/types";
import { isApiError } from "@/lib/api/errors";
import {
  Button,
  CertificateBadge,
  EmptyState,
  MediaUploader,
  Modal,
  QueryState,
  Select,
  TextInput,
  Toggle,
  useToast,
} from "@/components/ui";
import { ScheduleBoard } from "@/components/learning-cabinet/ScheduleBoard";
import { ParticipantList, SessionCard } from "@/components/learning-cabinet/SessionCard";
import { CancelSessionModal, CompleteSessionModal, RescheduleSessionModal } from "@/components/learning-cabinet/SessionActionModals";
import { StudentsBoard } from "@/components/learning-cabinet/StudentsBoard";
import { MetricsPanel } from "@/components/learning-cabinet/MetricsPanel";
import { FormAlert } from "@/components/learning-cabinet/FormAlert";
import { todayIn, zonedToUtcIso } from "@/components/learning-cabinet/time";
import type { ScheduleItem } from "@/lib/api/learningCabinet";
import { useInstructorProfile, useInstructorZone, useOffers } from "./hooks";

type SessionAction = { kind: "complete" | "reschedule" | "cancel"; session: ScheduleItem } | null;

function NewSlotForm({ zone, onDone }: { zone: string; onDone: () => void }) {
  const offers = useOffers();
  const toast = useToast();
  const [offerId, setOfferId] = useState("");
  const [date, setDate] = useState(todayIn(zone));
  const [time, setTime] = useState("09:00");
  const create = useMutation({
    mutationFn: () => instructorApi.sessions.create({ offer_id: offerId, starts_at: zonedToUtcIso(date, time, zone) }),
    onSuccess: () => {
      toast.success("Слот добавлен в расписание");
      onDone();
    },
  });
  const active = (offers.data ?? []).filter((o) => o.is_active !== false);
  if (offers.isSuccess && active.length === 0) {
    return <FormAlert tone="info">Чтобы открыть слоты для записи, сначала создайте предложение во вкладке «Предложения».</FormAlert>;
  }
  return (
    <form
      className="lc-inline-form"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <Select
        label="Предложение"
        placeholder="Выберите предложение"
        required
        value={offerId}
        onChange={(e) => setOfferId(e.target.value)}
        options={active.map((o) => ({ value: o.id, label: `${o.title} · ${o.duration_min} мин` }))}
      />
      <TextInput label="Дата" type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
      <TextInput label="Начало" type="time" required value={time} onChange={(e) => setTime(e.target.value)} hint={zone} />
      <Button type="submit" variant="primary" loading={create.isPending} disabled={!offerId}>
        Добавить слот
      </Button>
      {create.isError && (
        <FormAlert>
          {isApiError(create.error) && create.error.code === "instructor_busy"
            ? `${create.error.message} Выберите другое время — двойная запись инструктора запрещена.`
            : isApiError(create.error)
              ? create.error.message
              : "Не удалось добавить слот."}
        </FormAlert>
      )}
    </form>
  );
}

export function InstructorSchedule() {
  const profile = useInstructorProfile();
  const zone = useInstructorZone(profile.data);
  const qc = useQueryClient();
  const [action, setAction] = useState<SessionAction>(null);
  const [showForm, setShowForm] = useState(false);
  const refresh = () => {
    setAction(null);
    void qc.invalidateQueries({ queryKey: ik.scheduleAll });
  };
  const close = () => setAction(null);

  return (
    <>
      <ScheduleBoard<ScheduleItem>
        viewTz={zone}
        queryKey={(from, to) => ik.schedule(from, to, zone)}
        fetcher={(from, to) => instructorApi.schedule({ from, to, tz: zone }).then((r) => r.results)}
        emptyTitle="Занятий в этом периоде нет"
        emptyText="Здесь появляются и уроки школ, где вы в команде, и ваши частные слоты."
        toolbarExtra={
          profile.data ? (
            <Button variant="soft" icon="plus" onClick={() => setShowForm((v) => !v)} aria-expanded={showForm}>
              Новый слот
            </Button>
          ) : null
        }
        renderSession={(s) => {
          const active = s.status === "scheduled" || s.status === "in_progress";
          const isPrivate = s.kind === "private";
          return (
            <SessionCard
              session={s}
              showKind
              actions={
                active ? (
                  <>
                    <Button variant="soft" onClick={() => setAction({ kind: "complete", session: s })}>
                      Провести
                    </Button>
                    {isPrivate && (
                      <>
                        <Button variant="line" onClick={() => setAction({ kind: "reschedule", session: s })}>
                          Перенести
                        </Button>
                        <Button variant="link" onClick={() => setAction({ kind: "cancel", session: s })}>
                          Отменить
                        </Button>
                      </>
                    )}
                  </>
                ) : null
              }
            >
              <ParticipantList participants={s.participants} />
            </SessionCard>
          );
        }}
      />
      {showForm && (
        <section className="gv-ac-panel" aria-label="Новый слот частного занятия">
          <h3>Новый слот частного занятия</h3>
          <NewSlotForm
            zone={zone}
            onDone={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </section>
      )}
      {action?.kind === "complete" && (
        <CompleteSessionModal session={action.session} participants={action.session.participants} open onClose={close} onDone={refresh} />
      )}
      {action?.kind === "reschedule" && <RescheduleSessionModal session={action.session} open onClose={close} onDone={refresh} />}
      {action?.kind === "cancel" && <CancelSessionModal session={action.session} open onClose={close} onDone={refresh} />}
    </>
  );
}

export function InstructorStudents() {
  return (
    <StudentsBoard
      queryKey={(q, repeat, page) => ik.students(q, repeat, page)}
      fetcher={(q) => instructorApi.students(q)}
      inlineNotes
      emptyText="Ученики появятся после первых проведённых занятий."
    />
  );
}

const CERT_STATUS: Record<CertificateOwn["status"], { badge: "uploaded" | "verified" | "none"; text: string }> = {
  uploaded: { badge: "uploaded", text: "Загружен, ждёт проверки модератором" },
  verified: { badge: "verified", text: "Проверен модератором" },
  rejected: { badge: "none", text: "Отклонён модератором" },
  revoked: { badge: "none", text: "Отозван модератором" },
};

function CertificateUpload({ onDone }: { onDone: () => void }) {
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [issuer, setIssuer] = useState("");
  const [issuedOn, setIssuedOn] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [allowScan, setAllowScan] = useState(false);
  const [doc, setDoc] = useState<Media[]>([]);
  const upload = useMutation({
    mutationFn: () =>
      instructorApi.certificates.upload({
        title,
        issuer,
        issued_on: issuedOn || null,
        valid_until: validUntil || null,
        document_id: doc[0].id,
        allow_public_scan: allowScan,
      }),
    onSuccess: () => {
      toast.success("Сертификат отправлен на проверку");
      onDone();
    },
  });
  return (
    <form
      className="lc-form"
      onSubmit={(e) => {
        e.preventDefault();
        upload.mutate();
      }}
    >
      <TextInput label="Название сертификата" required value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
      <TextInput label="Кем выдан" value={issuer} onChange={(e) => setIssuer(e.target.value)} maxLength={200} />
      <div className="lc-form-row">
        <TextInput label="Дата выдачи" type="date" value={issuedOn} onChange={(e) => setIssuedOn(e.target.value)} />
        <TextInput label="Действует до" type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} />
      </div>
      <MediaUploader
        purpose="certificate"
        kind="document"
        maxFiles={1}
        value={doc}
        onChange={setDoc}
        label="Скан или фото сертификата"
        hint="PDF, JPG, PNG или WebP. Файл закрытый: его видите вы и модератор. Личные данные на документе можно закрыть."
      />
      <label className="lc-toggle-line">
        <Toggle checked={allowScan} onChange={setAllowScan} label="Показывать скан на публичной карточке после проверки" />
        <span>Показывать скан на публичной карточке после проверки</span>
      </label>
      {upload.isError && <FormAlert>{isApiError(upload.error) ? upload.error.message : "Не удалось отправить сертификат."}</FormAlert>}
      <Button type="submit" variant="primary" loading={upload.isPending} disabled={!title || doc.length === 0}>
        Отправить на проверку
      </Button>
    </form>
  );
}

export function InstructorCertificates() {
  const qc = useQueryClient();
  const toast = useToast();
  const list = useQuery({ queryKey: ik.certificates, queryFn: instructorApi.certificates.list });
  const [adding, setAdding] = useState(false);
  const refresh = () => void qc.invalidateQueries({ queryKey: ik.all });
  const remove = useMutation({ mutationFn: (id: string) => instructorApi.certificates.remove(id), onSuccess: refresh, onError: (e) => toast.error(e) });
  const toggleScan = useMutation({
    mutationFn: (c: CertificateOwn) => instructorApi.certificates.update(c.id, { allow_public_scan: !c.allow_public_scan }),
    onSuccess: refresh,
    onError: (e) => toast.error(e),
  });
  const openScan = useMutation({
    mutationFn: (id: string) => instructorApi.certificates.scanUrl(id),
    onSuccess: (r) => window.open(r.url, "_blank", "noopener"),
    onError: (e) => toast.error(e),
  });
  const summary = useMemo(() => {
    const statuses = (list.data ?? []).map((c) => c.status);
    return statuses.includes("verified") ? "verified" : statuses.includes("uploaded") ? "uploaded" : "none";
  }, [list.data]);

  return (
    <section className="gv-ac-panel" aria-labelledby="cert-title">
      <div className="gv-card-head">
        <div className="gv-card-head-text">
          <h3 id="cert-title">Сертификаты</h3>
          <p className="gv-ac-desc">
            Сертификат необязателен для публикации карточки. Значок «проверен» появляется только после решения модератора и
            подтверждает документ, а не гарантирует безопасность занятий.
          </p>
        </div>
        <div className="gv-card-head-actions">
          <CertificateBadge status={summary} />
          <Button variant="primary" icon="plus" onClick={() => setAdding(true)}>
            Загрузить
          </Button>
        </div>
      </div>
      <QueryState
        query={list}
        isEmpty={(d) => d.length === 0}
        empty={<EmptyState compact title="Сертификатов пока нет" text="На карточке будет «Сертификат не указан». Это нормально." />}
      >
        {(items) => (
          <ul className="lc-list">
            {items.map((c) => (
              <li key={c.id} className="lc-list-row">
                <div>
                  <strong>{c.title}</strong>
                  {c.issuer && <span className="muted"> · {c.issuer}</span>}
                  <div className="small muted">{CERT_STATUS[c.status].text}</div>
                  {c.moderator_comment && <div className="small">Комментарий модератора: {c.moderator_comment}</div>}
                </div>
                <div className="lc-list-actions">
                  <CertificateBadge status={CERT_STATUS[c.status].badge} compact />
                  <Button variant="link" onClick={() => openScan.mutate(c.id)}>
                    Скан
                  </Button>
                  <label className="lc-toggle-line small">
                    <Toggle checked={c.allow_public_scan} onChange={() => toggleScan.mutate(c)} label="Скан публично" />
                    <span>Скан публично</span>
                  </label>
                  <Button variant="link" onClick={() => remove.mutate(c.id)} loading={remove.isPending && remove.variables === c.id}>
                    Удалить
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
      <Modal open={adding} onClose={() => setAdding(false)} title="Загрузка сертификата" size="wide">
        <CertificateUpload
          onDone={() => {
            setAdding(false);
            refresh();
          }}
        />
      </Modal>
    </section>
  );
}

export function InstructorStats() {
  const profile = useInstructorProfile();
  const zone = useInstructorZone(profile.data);
  return (
    <MetricsPanel
      scope="instructor"
      timeZone={zone}
      title="Статистика инструктора"
      stripKeys={["profile_views", "bookings_confirmed", "unique_students", "repeat_students", "completed_lessons", "rating"]}
    />
  );
}
