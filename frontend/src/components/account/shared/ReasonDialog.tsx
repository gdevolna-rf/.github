"use client";
/**
 * Confirmation dialog with an optional / required reason (decline, cancel, no-show…). Replaces the prototype's
 * native confirm()/prompt() (SHAPERS_SCREENS §8). The action runs inside; errors stay in the dialog with the
 * server message so the user can fix the text or retry (ATX-25).
 */
import { useEffect, useState, type ReactNode } from "react";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { Button, type ButtonVariant } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";

/** Throw from `onConfirm` to show a client-side validation message inside the dialog. */
export class DialogError extends Error {}

export interface ReasonDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  /** Show the reason field. */
  withReason?: boolean;
  reasonRequired?: boolean;
  reasonLabel?: string;
  reasonPlaceholder?: string;
  maxLength?: number;
  confirmLabel: string;
  confirmVariant?: ButtonVariant;
  cancelLabel?: string;
  onConfirm: (reason: string) => Promise<unknown>;
  children?: ReactNode;
}

export function ReasonDialog({
  open,
  onClose,
  title,
  description,
  withReason = true,
  reasonRequired = false,
  reasonLabel = "Причина",
  reasonPlaceholder,
  maxLength = 300,
  confirmLabel,
  confirmVariant = "danger",
  cancelLabel = "Не сейчас",
  onConfirm,
  children,
}: ReasonDialogProps) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setReason("");
      setError(null);
      setBusy(false);
    }
  }, [open]);

  const submit = async () => {
    const text = reason.trim();
    if (withReason && reasonRequired && !text) {
      setError("Укажите причину — её увидит другая сторона.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onConfirm(text);
      onClose();
    } catch (err) {
      setError(
        err instanceof DialogError ? err.message : isApiError(err) ? (err.fieldError("reason") ?? err.message) : errorMessage(err),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={busy ? () => undefined : onClose}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="soft" onClick={onClose} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button variant={confirmVariant} onClick={() => void submit()} loading={busy}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <form
        className="acc-dialog-form"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        {children}
        {withReason && (
          <Textarea
            label={reasonLabel}
            required={reasonRequired}
            hint={reasonRequired ? "Обязательно. Причину увидит другая сторона." : "Необязательно. Причину увидит другая сторона."}
            value={reason}
            maxLength={maxLength}
            rows={3}
            placeholder={reasonPlaceholder}
            onChange={(e) => setReason(e.target.value)}
            error={error}
            data-autofocus
          />
        )}
        {!withReason && error && (
          <p className="gv-field-error" role="alert">
            {error}
          </p>
        )}
      </form>
    </Modal>
  );
}
