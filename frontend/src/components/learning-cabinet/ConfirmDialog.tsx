"use client";
/**
 * Confirmation dialog for destructive or important actions (delete, revoke access, cancel a session…).
 * The server error (if any) is shown inside the dialog so the user can retry (ATX-25). Local to the learning
 * cabinets — the UI kit has no confirm dialog yet.
 */
import { useState, type ReactNode } from "react";
import { errorMessage } from "@/lib/api/errors";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { FormAlert } from "./FormAlert";

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "danger" | "primary";
  onConfirm: () => Promise<unknown>;
  onClose: () => void;
  /** called after onConfirm resolved (dialog closes itself) */
  onDone?: () => void;
}

export function ConfirmDialog({ open, title, children, confirmLabel, cancelLabel = "Отмена", tone = "danger", onConfirm, onClose, onDone }: ConfirmDialogProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const close = () => {
    if (pending) return;
    setError(null);
    onClose();
  };

  const confirm = async () => {
    setPending(true);
    setError(null);
    try {
      await onConfirm();
      setPending(false);
      onClose();
      onDone?.();
    } catch (err) {
      setPending(false);
      setError(err);
    }
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title={title}
      footer={
        <>
          <Button variant={tone === "danger" ? "danger" : "primary"} onClick={() => void confirm()} loading={pending} data-autofocus>
            {confirmLabel}
          </Button>
          <Button variant="soft" onClick={close} disabled={pending}>
            {cancelLabel}
          </Button>
        </>
      }
    >
      {children}
      {error ? <FormAlert>{errorMessage(error)}</FormAlert> : null}
    </Modal>
  );
}
