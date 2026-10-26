"use client";
/**
 * «Пожаловаться» (TRUST-07, MSG-13): opens a complaint dialog → POST /api/v1/complaints.
 * Guests get the login prompt; repeated complaint (409 complaint_exists) and «на себя» (self_complaint) show the
 * server message. Use on any public object:
 *
 *   <ReportButton targetType="spot" targetId={spot.id} />
 *   <ReportButton targetType="review" targetId={review.id} variant="icon" label="Пожаловаться на отзыв" />
 */
import { useId, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { useLoginPrompt } from "@/components/auth/LoginPrompt";
import { Button, Icon, IconButton, Modal, Select, Textarea, useToast } from "@/components/ui";
import { COMPLAINT_REASONS, createComplaint, type ComplaintReason, type ComplaintTargetType } from "@/lib/api/actions";
import { isApiError } from "@/lib/api/errors";
import { useMe } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import "./trust.css";
import { apiFieldErrors, type FormErrors } from "@/lib/forms";

export interface ReportButtonProps {
  targetType: ComplaintTargetType;
  targetId: string;
  /** Button text / accessible name. Default «Пожаловаться». */
  label?: string;
  /** link = small text button with an icon (default); icon = round icon button. */
  variant?: "link" | "icon";
  className?: string;
}

const TARGET_TITLES: Record<ComplaintTargetType, string> = {
  spot: "спот",
  account: "пользователя",
  review: "отзыв",
  message: "сообщение",
  board_model: "модель доски",
  inventory_item: "объявление",
  organization: "организацию",
  media: "фото или видео",
  club_event: "событие",
};

export function ReportButton({ targetType, targetId, label = "Пожаловаться", variant = "link", className }: ReportButtonProps) {
  const { me, isLoading } = useMe();
  const { prompt } = useLoginPrompt();
  const [open, setOpen] = useState(false);

  const onOpen = () => {
    if (!me) {
      if (!isLoading) prompt("Чтобы отправить жалобу модераторам, войдите в аккаунт.");
      return;
    }
    setOpen(true);
  };

  return (
    <>
      {variant === "icon" ? (
        <IconButton icon="alert" label={label} shape="round" iconSize={18} className={className} onClick={onOpen} />
      ) : (
        <button type="button" className={cx("gv-report-link", className)} onClick={onOpen}>
          <Icon name="alert" size={15} />
          <span>{label}</span>
        </button>
      )}
      {open && (
        <ReportDialog targetType={targetType} targetId={targetId} onClose={() => setOpen(false)} />
      )}
    </>
  );
}

export function ReportDialog({
  targetType,
  targetId,
  onClose,
}: {
  targetType: ComplaintTargetType;
  targetId: string;
  onClose: () => void;
}) {
  const formId = useId().replace(/:/g, "");
  const toast = useToast();
  const [reason, setReason] = useState<ComplaintReason | "">("");
  const [text, setText] = useState("");
  const [errors, setErrors] = useState<FormErrors<"reason" | "text">>({});
  const [done, setDone] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createComplaint,
    onSuccess: () => {
      toast.success("Жалоба отправлена модераторам");
      setDone("Спасибо! Модераторы рассмотрят жалобу. Решение появится в уведомлениях.");
    },
    onError: (err) => {
      if (isApiError(err) && (err.code === "complaint_exists" || err.code === "self_complaint")) {
        setErrors({ _form: err.message });
        return;
      }
      setErrors(apiFieldErrors(err));
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next: FormErrors<"reason" | "text"> = {};
    if (!reason) next.reason = "Выберите причину.";
    if (reason === "other" && !text.trim()) next.text = "Опишите причину жалобы.";
    setErrors(next);
    if (Object.keys(next).length || !reason) return;
    mutation.mutate({ target_type: targetType, target_id: targetId, reason, text: text.trim() });
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={`Пожаловаться на ${TARGET_TITLES[targetType]}`}
      description={done ? undefined : "Жалобу увидят только модераторы. Автор материала не узнает, кто её отправил."}
      footer={
        done ? (
          <Button variant="primary" onClick={onClose} data-autofocus="">
            Готово
          </Button>
        ) : (
          <>
            <Button variant="pill" onClick={onClose}>
              Отмена
            </Button>
            <Button variant="primary" type="submit" form={formId} loading={mutation.isPending}>
              Отправить жалобу
            </Button>
          </>
        )
      }
    >
      {done ? (
        <p className="gv-report-done" role="status">
          <Icon name="check" size={18} /> {done}
        </p>
      ) : (
        <form id={formId} onSubmit={submit} noValidate>
          {errors._form && (
            <div className="gv-form-error" role="alert">
              <Icon name="alert" size={18} />
              <span>{errors._form}</span>
            </div>
          )}
          <Select
            label="Причина"
            required
            placeholder="Выберите причину"
            value={reason}
            onChange={(e) => setReason(e.target.value as ComplaintReason | "")}
            options={COMPLAINT_REASONS}
            error={errors.reason}
            data-autofocus=""
          />
          <Textarea
            label="Подробности"
            hint={reason === "other" ? "Обязательно для причины «Другое»." : "Необязательно: что именно не так."}
            required={reason === "other"}
            value={text}
            maxLength={2000}
            rows={4}
            onChange={(e) => setText(e.target.value)}
            error={errors.text}
          />
        </form>
      )}
    </Modal>
  );
}
