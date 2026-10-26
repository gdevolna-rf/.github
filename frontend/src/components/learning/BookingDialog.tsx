"use client";
/**
 * Lesson booking (INS-07, SCH-05/08/11, AT-05, F06/F07): one dialog for private instructor slots and school sessions.
 * POST /api/v1/bookings with an Idempotency-Key (one per user attempt), then opens /account/bookings/{id}.
 * Minor participants (SCH-11): participant name + guardian consent are required.
 * Server refusals (self booking, no seats, duplicate, session started) are shown inside the dialog; on «мест нет»
 * the caller may offer the waitlist (onFull).
 *
 *   <BookingButton session={slot} providerName="Иван Петров" />
 */
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLoginPrompt } from "@/components/auth/LoginPrompt";
import { Button, Checkbox, Icon, Modal, TextInput, Textarea, useToast, type ButtonVariant } from "@/components/ui";
import { newIdempotencyKey } from "@/lib/api/client";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import { learningApi, learningKeys } from "@/lib/api/learning";
import { useMe } from "@/lib/auth/hooks";
import { formatDate, formatMoney, formatTime, plural, WORDS } from "@/lib/format";
import { apiFieldErrors, type FormErrors } from "@/lib/forms";
import { routes } from "@/lib/routes";
import "../commerce/commerce.css";

/** The minimum a slot needs to be booked (works for `upcoming_slots`, `upcoming_sessions`, `/sessions/{id}`). */
export interface BookableSession {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string;
  timezone?: string | null;
  free_seats: number;
  capacity?: number | null;
  price?: string | null;
  currency?: string | null;
  spot?: { name: string } | null;
}

export interface BookingDialogProps {
  open: boolean;
  onClose: () => void;
  session: BookableSession;
  /** Instructor or school name for the summary line. */
  providerName: string;
  /** Fallback time zone when the session has none (region timezone). */
  timeZone?: string;
  /** Called when the server says there are no seats left (offer the waitlist). */
  onFull?: () => void;
}

type Field = "participant_name" | "guardian_consent" | "seats" | "customer_note";

const ALIASES: Record<string, Field> = { participant_name: "participant_name", guardian_consent: "guardian_consent", seats: "seats" };

export function sessionWhen(session: Pick<BookableSession, "starts_at" | "ends_at" | "timezone">, fallbackTz?: string): string {
  const tz = session.timezone || fallbackTz || undefined;
  return `${formatDate(session.starts_at, { timeZone: tz, style: "long" })}, ${formatTime(session.starts_at, tz)}–${formatTime(session.ends_at, tz)}`;
}

export function BookingDialog(props: BookingDialogProps) {
  const { open, onClose } = props;
  const { me, isLoading } = useMe();
  const { prompt } = useLoginPrompt();
  useEffect(() => {
    if (open && !isLoading && !me) {
      prompt("Чтобы записаться на занятие, войдите в аккаунт — заявка и переписка сохранятся в кабинете.");
      onClose();
    }
  }, [open, isLoading, me, prompt, onClose]);
  if (!open || !me) return null;
  return <BookingForm {...props} />;
}

function BookingForm({ onClose, session, providerName, timeZone, onFull }: BookingDialogProps) {
  const formId = useId().replace(/:/g, "");
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { me } = useMe();
  const keyRef = useRef(newIdempotencyKey());

  const maxSeats = Math.max(1, Math.min(session.free_seats || 1, 10));
  const [seats, setSeats] = useState(1);
  const [minor, setMinor] = useState(false);
  const [participant, setParticipant] = useState("");
  const [consent, setConsent] = useState(false);
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<FormErrors<Field>>({});
  const [blocked, setBlocked] = useState<{ message: string; full?: boolean } | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      learningApi.bookLesson(
        {
          lesson_session_id: session.id,
          seats,
          participant_name: participant.trim(),
          participant_is_minor: minor,
          guardian_consent: minor ? consent : false,
          customer_note: note.trim(),
        },
        keyRef.current,
      ),
    onSuccess: (booking) => {
      void queryClient.invalidateQueries({ queryKey: qk.bookings });
      void queryClient.invalidateQueries({ queryKey: qk.counters });
      void queryClient.invalidateQueries({ queryKey: learningKeys.all });
      toast.success("Заявка отправлена — ждите подтверждения");
      onClose();
      router.push(routes.account.booking(booking.id));
    },
    onError: (err) => {
      if (isApiError(err)) {
        if (err.code === "no_seats") {
          setBlocked({ message: err.message, full: true });
          return;
        }
        if (err.isForbidden || err.isConflict || err.isNotFound) {
          setBlocked({ message: err.message });
          return;
        }
      }
      setErrors(apiFieldErrors(err, ALIASES));
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next: FormErrors<Field> = {};
    if (minor && !participant.trim()) next.participant_name = "Укажите имя ученика.";
    if (minor && !consent) next.guardian_consent = "Нужно согласие законного представителя.";
    setErrors(next);
    if (Object.keys(next).length) return;
    mutation.mutate();
  };

  const tz = session.timezone || timeZone || undefined;
  const price = session.price ? formatMoney(session.price, session.currency || "RUB") : null;

  return (
    <Modal
      open
      onClose={onClose}
      title="Запись на занятие"
      size="wide"
      footer={
        blocked ? (
          <>
            <Button variant="pill" onClick={onClose}>
              Закрыть
            </Button>
            {blocked.full && onFull ? (
              <Button
                variant="primary"
                onClick={() => {
                  onClose();
                  onFull();
                }}
                data-autofocus=""
              >
                Встать в лист ожидания
              </Button>
            ) : null}
          </>
        ) : (
          <>
            <Button variant="pill" onClick={onClose}>
              Отмена
            </Button>
            <Button variant="primary" type="submit" form={formId} loading={mutation.isPending} iconRight="arrow">
              Отправить заявку
            </Button>
          </>
        )
      }
    >
      <div className="lesson-book-preview gv-booking-summary">
        <div>
          <b className="gv-clamp-2" title={session.title}>
            {session.title}
          </b>
          <p className="small">
            {providerName} · {sessionWhen(session, timeZone)}
            {session.spot?.name ? ` · ${session.spot.name}` : ""}
          </p>
          <p className="small">
            {tz ? `Время местное (${tz.replace(/_/g, " ")}). ` : ""}
            Свободно {session.free_seats} {plural(session.free_seats, WORDS.seat)}
            {price ? ` · ${price} за место` : ""}
          </p>
        </div>
      </div>

      {blocked ? (
        <div className="gv-form-error" role="alert">
          <Icon name="alert" size={18} />
          <span>{blocked.message}</span>
        </div>
      ) : (
        <form id={formId} onSubmit={submit} onChange={() => (keyRef.current = newIdempotencyKey())} noValidate>
          {errors._form && (
            <div className="gv-form-error" role="alert">
              <Icon name="alert" size={18} />
              <span>{errors._form}</span>
            </div>
          )}
          <div className="gv-form-grid">
            <TextInput
              label="Мест"
              type="number"
              min={1}
              max={maxSeats}
              value={seats}
              onChange={(e) => setSeats(Math.min(maxSeats, Math.max(1, Number(e.target.value) || 1)))}
              error={errors.seats}
              hint={maxSeats > 1 ? `До ${maxSeats}` : undefined}
              data-autofocus=""
            />
            <TextInput
              label="Имя ученика"
              maxLength={160}
              value={participant}
              required={minor}
              placeholder={me?.displayName ?? ""}
              onChange={(e) => setParticipant(e.target.value)}
              error={errors.participant_name}
              hint={minor ? "Обязательно для несовершеннолетнего." : "Если пусто — запишем вас."}
            />
          </div>
          <Checkbox
            label="Записываю несовершеннолетнего"
            description="Запись ребёнка оформляет родитель или другой законный представитель."
            checked={minor}
            onChange={(e) => setMinor(e.target.checked)}
          />
          {minor && (
            <Checkbox
              label="Я законный представитель и даю согласие на участие ребёнка в занятии"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              error={errors.guardian_consent}
            />
          )}
          <Textarea
            label="Пара слов инструктору"
            rows={3}
            maxLength={2000}
            placeholder="Уровень, опыт, нужен ли гидрокостюм и доска…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <p className="lesson-form-note">
            После отправки заявка ожидает подтверждения. Оплата на этом этапе не списывается — условия уточняются в
            переписке.
          </p>
        </form>
      )}
    </Modal>
  );
}

/** Trigger + dialog: guests get the login prompt. */
export function BookingButton({
  session,
  providerName,
  timeZone,
  onFull,
  label = "Записаться",
  variant = "primary",
  className,
  block,
  size,
}: Omit<BookingDialogProps, "open" | "onClose"> & {
  label?: string;
  variant?: ButtonVariant;
  className?: string;
  block?: boolean;
  size?: "sm" | "md";
}) {
  const [open, setOpen] = useState(false);
  const { me, isLoading } = useMe();
  const { prompt } = useLoginPrompt();
  return (
    <>
      <Button
        variant={variant}
        className={className}
        block={block}
        size={size}
        icon="calendar"
        aria-label={`${label}: ${session.title}, ${sessionWhen(session, timeZone)}`}
        onClick={() => {
          if (!me) {
            if (!isLoading) prompt("Чтобы записаться на занятие, войдите в аккаунт — заявка и переписка сохранятся в кабинете.");
            return;
          }
          setOpen(true);
        }}
      >
        {label}
      </Button>
      <BookingDialog open={open} onClose={() => setOpen(false)} session={session} providerName={providerName} timeZone={timeZone} onFull={onFull} />
    </>
  );
}
