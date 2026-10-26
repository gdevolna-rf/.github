"use client";
/**
 * Session actions shared by the instructor and school cabinets:
 *  - reschedule (weather and other reasons, students are notified — SCH-05), 409 instructor_busy shown inline (F11);
 *  - cancel with a reason (bookings are cancelled and notified — F13);
 *  - complete with no-shows (fact, not plan — TZ §10; assigned instructor, owner or manager).
 */
import { useEffect, useState } from "react";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { sessionsApi, type LessonSession, type SessionParticipant } from "@/lib/api/learningCabinet";
import { Button } from "@/components/ui/Button";
import { Checkbox, TextInput, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { ChipGroup } from "@/components/ui/Chip";
import { LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { FormAlert } from "./FormAlert";
import { durationMinutes, formatDay, timeRange, tzLabel, zonedParts, zonedToUtcIso } from "./time";
import { isoDateInZone } from "@/lib/format";

const RESCHEDULE_REASONS = ["Погода: нет волны или шторм", "Болезнь инструктора", "Просьба учеников", "Другое"] as const;

function SessionSummary({ session }: { session: LessonSession }) {
  const day = isoDateInZone(session.starts_at, session.timezone);
  return (
    <p className="lc-modal-summary">
      <b>{session.title}</b>
      <span>
        {formatDay(day, "weekday")}, {timeRange(session.starts_at, session.ends_at, session.timezone)} · {tzLabel(session.timezone, session.starts_at)}
      </span>
    </p>
  );
}

/** Reschedule: new date/time in the session zone + reason. `submit` lets the private-slot editor reuse the form. */
export function RescheduleSessionModal({
  session,
  open,
  onClose,
  onDone,
}: {
  session: LessonSession;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const tz = session.timezone;
  const initial = zonedParts(session.starts_at, tz);
  const [date, setDate] = useState(initial.date);
  const [time, setTime] = useState(initial.time);
  const [duration, setDuration] = useState(String(durationMinutes(session.starts_at, session.ends_at)));
  const [reasonKind, setReasonKind] = useState<string[]>([RESCHEDULE_REASONS[0]]);
  const [reasonText, setReasonText] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!open) return;
    const p = zonedParts(session.starts_at, tz);
    setDate(p.date);
    setTime(p.time);
    setDuration(String(durationMinutes(session.starts_at, session.ends_at)));
    setError(null);
  }, [open, session.starts_at, session.ends_at, tz]);

  const submit = async () => {
    const minutes = Number(duration);
    if (!date || !time) return setError(new Error("Укажите дату и время."));
    if (!Number.isFinite(minutes) || minutes < 15 || minutes > 1440) return setError(new Error("Длительность — от 15 минут до 24 часов."));
    const kind = reasonKind[0] ?? "Другое";
    const reason = [kind === "Другое" ? "" : kind, reasonText.trim()].filter(Boolean).join(". ").slice(0, 300);
    const starts = zonedToUtcIso(date, time, tz);
    const ends = new Date(new Date(starts).getTime() + minutes * 60000).toISOString();
    setPending(true);
    setError(null);
    try {
      await sessionsApi.reschedule(session.id, { starts_at: starts, ends_at: ends, reason });
      toast.success("Занятие перенесено — записанные ученики получат уведомление");
      onClose();
      onDone();
    } catch (err) {
      setError(err);
    } finally {
      setPending(false);
    }
  };

  const message = error ? (isApiError(error) || !(error instanceof Error) ? errorMessage(error) : error.message) : null;

  return (
    <Modal
      open={open}
      onClose={() => !pending && onClose()}
      title="Перенести занятие"
      size="wide"
      footer={
        <>
          <Button variant="primary" onClick={() => void submit()} loading={pending}>
            Перенести
          </Button>
          <Button variant="soft" onClick={onClose} disabled={pending}>
            Отмена
          </Button>
        </>
      }
    >
      <SessionSummary session={session} />
      <div className="gv-form-grid lc-form-grid-3">
        <TextInput label="Новая дата" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        <TextInput label="Начало" type="time" value={time} onChange={(e) => setTime(e.target.value)} required hint={`Время по месту: ${tzLabel(tz, session.starts_at)}`} />
        <TextInput label="Длительность, мин" type="number" min={15} max={1440} step={5} value={duration} onChange={(e) => setDuration(e.target.value)} />
      </div>
      <ChipGroup label="Причина переноса" multiple={false} value={reasonKind} onChange={(v) => setReasonKind(v.length ? v : ["Другое"])} options={RESCHEDULE_REASONS.map((r) => ({ value: r, label: r }))} />
      <Textarea label="Комментарий для учеников" value={reasonText} onChange={(e) => setReasonText(e.target.value)} maxLength={240} rows={2} placeholder="Например: переносим на утро — ожидается ветер с берега" />
      <FormAlert tone="info">Записанные ученики получат уведомление о новом времени и причине. Пересечение с другими занятиями инструктора сервер не допустит.</FormAlert>
      {message && <FormAlert title={isApiError(error) && error.isConflict ? "Время занято" : undefined}>{message}</FormAlert>}
    </Modal>
  );
}

export function CancelSessionModal({ session, open, onClose, onDone }: { session: LessonSession; open: boolean; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) {
      setReason("");
      setError(null);
    }
  }, [open]);

  const submit = async () => {
    if (reason.trim().length < 2) return setError("Укажите причину отмены — её увидят записанные ученики.");
    setPending(true);
    setError(null);
    try {
      await sessionsApi.cancel(session.id, reason.trim());
      toast.success("Занятие отменено, записанные ученики уведомлены");
      onClose();
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={() => !pending && onClose()}
      title="Отменить занятие"
      footer={
        <>
          <Button variant="danger" onClick={() => void submit()} loading={pending}>
            Отменить занятие
          </Button>
          <Button variant="soft" onClick={onClose} disabled={pending}>
            Не отменять
          </Button>
        </>
      }
    >
      <SessionSummary session={session} />
      <Textarea label="Причина отмены" required value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} rows={3} placeholder="Например: шторм, занятие перенесём — напишем отдельно" data-autofocus />
      <FormAlert tone="warn">Все записи на занятие будут отменены, ученики получат уведомление. История занятия сохранится.</FormAlert>
      {error && <FormAlert>{error}</FormAlert>}
    </Modal>
  );
}

/**
 * Complete with no-shows: confirmed participants are marked «проведено», checked ones — «неявка».
 * `participants` may be loading (school view fetches bookings) → pass `loading`.
 */
export function CompleteSessionModal({
  session,
  participants,
  loading,
  loadError,
  open,
  onClose,
  onDone,
}: {
  session: LessonSession;
  participants: SessionParticipant[];
  loading?: boolean;
  loadError?: unknown;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [noShow, setNoShow] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const started = new Date(session.starts_at).getTime() <= Date.now();
  const markable = participants.filter((p) => p.status === "confirmed" || p.status === "in_progress");

  useEffect(() => {
    if (open) {
      setNoShow([]);
      setError(null);
    }
  }, [open]);

  const submit = async () => {
    setPending(true);
    setError(null);
    try {
      const res = await sessionsApi.complete(session.id, noShow);
      const done = res.completed_booking_ids.length;
      const missed = res.no_show_booking_ids.length;
      toast.success(`Занятие проведено: пришли ${done}, неявок ${missed}`);
      onClose();
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={() => !pending && onClose()}
      title="Отметить занятие проведённым"
      size="wide"
      footer={
        <>
          <Button variant="primary" onClick={() => void submit()} loading={pending} disabled={!started || loading}>
            Занятие проведено
          </Button>
          <Button variant="soft" onClick={onClose} disabled={pending}>
            Отмена
          </Button>
        </>
      }
    >
      <SessionSummary session={session} />
      {!started && <FormAlert tone="warn">Отметить проведение можно только после начала занятия.</FormAlert>}
      {loading ? (
        <LoadingState variant="inline" label="Загружаем участников…" />
      ) : loadError ? (
        <FormAlert>{errorMessage(loadError)}</FormAlert>
      ) : markable.length ? (
        <fieldset className="gv-fieldset lc-noshow">
          <legend className="gv-field-label">Кто не пришёл? Остальные подтверждённые записи будут отмечены как проведённые.</legend>
          {markable.map((p) => (
            <Checkbox
              key={p.booking_id}
              label={`${p.name}${p.seats > 1 ? ` × ${p.seats}` : ""}`}
              description={p.status === "in_progress" ? "Занятие уже начато — неявку отметить нельзя" : p.participant_is_minor ? "Несовершеннолетний участник" : undefined}
              checked={noShow.includes(p.booking_id)}
              disabled={p.status === "in_progress"}
              onChange={(e) => setNoShow((list) => (e.target.checked ? [...list, p.booking_id] : list.filter((id) => id !== p.booking_id)))}
            />
          ))}
        </fieldset>
      ) : (
        <FormAlert tone="info">Подтверждённых записей нет — занятие будет отмечено проведённым без участников.</FormAlert>
      )}
      {error && <FormAlert>{error}</FormAlert>}
    </Modal>
  );
}
