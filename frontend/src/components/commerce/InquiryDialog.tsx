"use client";
/**
 * «Написать» / «Оставить заявку» (MSG-03/09, AT-01, AT-03, SHP-11, SHO-06): one dialog for every inquiry kind.
 * POST /api/v1/inquiries with an Idempotency-Key (one key per user attempt, so a manual retry never creates a
 * duplicate), then navigates to the created conversation /account/inquiries/{id}.
 *
 *   const [open, setOpen] = useState(false);
 *   <InquiryDialog open={open} onClose={() => setOpen(false)} kind="lesson"
 *     providerAccountId={account.id} providerName="Иван Петров" />
 *
 *   // or the ready-made trigger (handles the guest login prompt):
 *   <InquiryButton kind="program" targetType="school_program" targetId={p.id} providerName={school.name}>
 *     Написать школе
 *   </InquiryButton>
 *
 * Variants: `detailsVariant="repair"` — problem + board + desired date + photos (MediaUploader purpose
 * repair_photo); `"custom_order"` — board parameters, desired date, budget, comment. Guests get the login prompt;
 * the server's refusals (self inquiry, blocked, provider not available) are shown inside the dialog.
 */
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLoginPrompt } from "@/components/auth/LoginPrompt";
import { Button, Icon, MediaUploader, Modal, TextInput, Textarea, useToast, type ButtonVariant, type IconName } from "@/components/ui";
import { createInquiry, type InquiryCreateInput, type InquiryKind, type InquiryTargetType } from "@/lib/api/actions";
import { newIdempotencyKey } from "@/lib/api/client";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import type { Media } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { apiFieldErrors, type FormErrors } from "@/lib/forms";
import { INQUIRY_KIND_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import "./commerce.css";

export interface InquiryDialogProps {
  open: boolean;
  onClose: () => void;
  kind: InquiryKind;
  /** Object of the inquiry (board model, offer, program, session, item…). Or pass a provider id instead. */
  targetType?: InquiryTargetType;
  targetId?: string;
  providerAccountId?: string;
  providerOrganizationId?: string;
  /** Shown in the title: «Написать: Иван Петров». */
  providerName: string;
  /** Overrides the dialog title. */
  title?: string;
  /** Context line under the title, e.g. «Модель: Fish 5'8"» or «Занятие 21 октября, 10:00». */
  contextLabel?: string;
  detailsVariant?: "repair" | "custom_order";
  /** Initial message text. */
  defaultMessage?: string;
  /** Called after creation; return `false` to stay on the page instead of opening the conversation. */
  onCreated?: (inquiry: { id: string }) => void | boolean;
}

type Field = "message" | "problem" | "board" | "desired_date" | "budget" | "length" | "volume" | "weight" | "comment";

const PLACEHOLDERS: Partial<Record<InquiryKind, string>> = {
  lesson: "Здравствуйте! Хочу записаться на занятие. Мой уровень — …, удобные даты — …",
  program: "Здравствуйте! Интересует программа. Расскажите, пожалуйста, о ближайших датах.",
  board_purchase: "Здравствуйте! Интересует эта доска. Подскажите, пожалуйста, …",
  custom_order: "Здравствуйте! Хочу заказать доску под себя.",
  repair: "Здравствуйте! Нужен ремонт доски.",
  rental: "Здравствуйте! Хочу взять в аренду на даты …",
  general: "Здравствуйте! …",
};

function todayIso(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Server field names (`details.problem`) → form fields. */
const FIELD_ALIASES: Record<string, Field> = {
  "details.problem": "problem",
  "details.desired_date": "desired_date",
  "details.budget": "budget",
  "details.photo_ids": "problem",
  "details.board": "board",
  target_type: "message",
  target_id: "message",
};

export function InquiryDialog(props: InquiryDialogProps) {
  const { open, onClose } = props;
  const { me, isLoading } = useMe();
  const { prompt } = useLoginPrompt();

  // Guests never see the form: the login prompt replaces it (UX: no silent failures).
  useEffect(() => {
    if (open && !isLoading && !me) {
      prompt("Чтобы написать исполнителю, войдите в аккаунт — переписка сохранится в разделе «Обращения».");
      onClose();
    }
  }, [open, isLoading, me, prompt, onClose]);

  if (!open || !me) return null;
  return <InquiryForm {...props} />;
}

function InquiryForm({
  onClose,
  kind,
  targetType,
  targetId,
  providerAccountId,
  providerOrganizationId,
  providerName,
  title,
  contextLabel,
  detailsVariant,
  defaultMessage,
  onCreated,
}: InquiryDialogProps) {
  const formId = useId().replace(/:/g, "");
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { me } = useMe();
  // One key per attempt: the automatic and the manual retry reuse it; editing the form starts a new attempt.
  const keyRef = useRef<string>(newIdempotencyKey());

  const [message, setMessage] = useState(defaultMessage ?? "");
  const [problem, setProblem] = useState("");
  const [board, setBoard] = useState("");
  const [desiredDate, setDesiredDate] = useState("");
  const [budget, setBudget] = useState("");
  const [length, setLength] = useState("");
  const [volume, setVolume] = useState("");
  const [weight, setWeight] = useState("");
  const [comment, setComment] = useState("");
  const [photos, setPhotos] = useState<Media[]>([]);
  const [errors, setErrors] = useState<FormErrors<Field>>({});
  const [blocked, setBlocked] = useState<string | null>(null);

  const touch = () => {
    keyRef.current = newIdempotencyKey();
  };

  const mutation = useMutation({
    mutationFn: (body: InquiryCreateInput) => createInquiry(body, keyRef.current),
    onSuccess: (inquiry) => {
      void queryClient.invalidateQueries({ queryKey: qk.inquiries });
      void queryClient.invalidateQueries({ queryKey: qk.counters });
      toast.success("Обращение отправлено — продолжите разговор в «Обращениях»");
      const stay = onCreated?.({ id: inquiry.id }) === false;
      onClose();
      if (!stay) router.push(routes.account.inquiry(inquiry.id));
    },
    onError: (err) => {
      if (isApiError(err) && (err.isForbidden || err.code === "self_inquiry" || err.code === "blocked" || err.code === "repair_not_offered" || err.code === "invalid_target" || err.isNotFound)) {
        // AT-03: «Нельзя отправить обращение самому себе…» — shown as is, the form is not retryable.
        setBlocked(err.message);
        return;
      }
      setErrors(apiFieldErrors(err, FIELD_ALIASES));
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next: FormErrors<Field> = {};
    const text = message.trim();
    if (!text) next.message = "Напишите сообщение исполнителю.";
    if (detailsVariant === "repair" && !problem.trim()) next.problem = "Опишите проблему с доской.";
    if (desiredDate && desiredDate < todayIso()) next.desired_date = "Дата не может быть в прошлом.";
    if (budget && !(Number(budget.replace(",", ".")) >= 0)) next.budget = "Укажите сумму числом.";
    setErrors(next);
    if (Object.keys(next).length) return;

    const body: InquiryCreateInput = { kind, message: text };
    if (targetType && targetId) {
      body.target_type = targetType;
      body.target_id = targetId;
    } else if (providerAccountId) body.provider_account_id = providerAccountId;
    else if (providerOrganizationId) body.provider_organization_id = providerOrganizationId;

    if (detailsVariant === "repair") {
      body.details = {
        problem: problem.trim(),
        board: board.trim(),
        desired_date: desiredDate || null,
        photo_ids: photos.map((p) => p.id),
      };
    } else if (detailsVariant === "custom_order") {
      const params: Record<string, string> = {};
      if (length.trim()) params["Длина"] = length.trim();
      if (volume.trim()) params["Объём, л"] = volume.trim();
      if (weight.trim()) params["Вес райдера, кг"] = weight.trim();
      body.details = {
        params,
        desired_date: desiredDate || null,
        budget: budget ? budget.replace(",", ".").replace(/\s/g, "") : null,
        comment: comment.trim(),
      };
    }
    mutation.mutate(body);
  };

  const heading = title ?? `Написать: ${providerName}`;
  const kindLabel = INQUIRY_KIND_LABELS[kind] ?? "Обращение";
  const ownName = me?.displayName;

  return (
    <Modal
      open
      onClose={onClose}
      title={heading}
      size={detailsVariant ? "wide" : "default"}
      description={
        <>
          <span className="gv-inquiry-kind">{kindLabel}</span>
          {contextLabel ? <span className="gv-inquiry-context"> · {contextLabel}</span> : null}
        </>
      }
      footer={
        blocked ? (
          <Button variant="primary" onClick={onClose} data-autofocus="">
            Понятно
          </Button>
        ) : (
          <>
            <Button variant="pill" onClick={onClose}>
              Отмена
            </Button>
            <Button variant="primary" type="submit" form={formId} loading={mutation.isPending} iconRight="send">
              Отправить
            </Button>
          </>
        )
      }
    >
      {blocked ? (
        <div className="gv-form-error" role="alert">
          <Icon name="alert" size={18} />
          <span>{blocked}</span>
        </div>
      ) : (
        <form id={formId} onSubmit={submit} onChange={touch} noValidate className="gv-inquiry-form">
          {errors._form && (
            <div className="gv-form-error" role="alert">
              <Icon name="alert" size={18} />
              <span>
                {errors._form}
                {isApiError(mutation.error) && mutation.error.retryable ? " Нажмите «Отправить» ещё раз." : ""}
              </span>
            </div>
          )}

          {detailsVariant === "repair" && (
            <>
              <Textarea
                label="Что случилось с доской"
                required
                rows={4}
                maxLength={2000}
                value={problem}
                onChange={(e) => setProblem(e.target.value)}
                error={errors.problem}
                hint="Где повреждение, какого размера, попадала ли вода внутрь."
                data-autofocus=""
              />
              <div className="gv-form-grid">
                <TextInput
                  label="Доска"
                  placeholder="Например, Fish 5′8″, эпоксид"
                  maxLength={200}
                  value={board}
                  onChange={(e) => setBoard(e.target.value)}
                  error={errors.board}
                />
                <TextInput
                  label="Желаемая дата"
                  type="date"
                  min={todayIso()}
                  value={desiredDate}
                  onChange={(e) => setDesiredDate(e.target.value)}
                  error={errors.desired_date}
                />
              </div>
              <MediaUploader
                purpose="repair_photo"
                value={photos}
                onChange={setPhotos}
                maxFiles={10}
                label="Фото повреждения"
                hint="До 10 фото: общий план и крупно место повреждения."
              />
            </>
          )}

          {detailsVariant === "custom_order" && (
            <>
              <div className="gv-form-grid">
                <TextInput label="Длина" placeholder="Например, 6′2″" maxLength={40} value={length} onChange={(e) => setLength(e.target.value)} />
                <TextInput label="Объём, л" inputMode="decimal" placeholder="Например, 38" maxLength={20} value={volume} onChange={(e) => setVolume(e.target.value)} />
                <TextInput label="Ваш вес, кг" inputMode="numeric" maxLength={10} value={weight} onChange={(e) => setWeight(e.target.value)} />
                <TextInput
                  label="Бюджет, ₽"
                  inputMode="decimal"
                  maxLength={12}
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  error={errors.budget}
                />
                <TextInput
                  label="Желаемая дата"
                  type="date"
                  min={todayIso()}
                  value={desiredDate}
                  onChange={(e) => setDesiredDate(e.target.value)}
                  error={errors.desired_date}
                />
              </div>
              <Textarea label="Пожелания к доске" rows={3} maxLength={1000} value={comment} onChange={(e) => setComment(e.target.value)} />
            </>
          )}

          <Textarea
            label="Сообщение"
            required
            rows={detailsVariant ? 3 : 5}
            maxLength={4000}
            placeholder={PLACEHOLDERS[kind] ?? PLACEHOLDERS.general}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            error={errors.message}
            hint={ownName ? `Отправится от имени «${ownName}». Ответ придёт в «Обращения» и уведомления.` : undefined}
            {...(detailsVariant ? {} : { "data-autofocus": "" })}
          />
        </form>
      )}
    </Modal>
  );
}

export interface InquiryButtonProps extends Omit<InquiryDialogProps, "open" | "onClose"> {
  children?: ReactNode;
  variant?: ButtonVariant;
  icon?: IconName;
  className?: string;
  block?: boolean;
  size?: "sm" | "md";
}

/** Trigger + dialog in one: guests get the login prompt instead of the form. */
export function InquiryButton({ children, variant = "primary", icon = "chat", className, block, size, ...dialog }: InquiryButtonProps) {
  const [open, setOpen] = useState(false);
  const { me, isLoading } = useMe();
  const { prompt } = useLoginPrompt();
  const onClick = () => {
    if (!me) {
      if (!isLoading) prompt("Чтобы написать исполнителю, войдите в аккаунт — переписка сохранится в разделе «Обращения».");
      return;
    }
    setOpen(true);
  };
  return (
    <>
      <Button variant={variant} icon={icon} className={className} block={block} size={size} onClick={onClick}>
        {children ?? "Написать"}
      </Button>
      <InquiryDialog {...dialog} open={open} onClose={() => setOpen(false)} />
    </>
  );
}
