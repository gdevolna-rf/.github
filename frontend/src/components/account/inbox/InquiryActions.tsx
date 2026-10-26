"use client";
/**
 * Inquiry status actions from the server's `actions` (SHO-05, ATX-28): one vocabulary (labels.ts
 * INQUIRY_ACTIONS) and one set of dialogs everywhere — list rows, the inquiry page, the chat.
 *   accept   → «Взять в работу» (instant)
 *   complete → «Завершить»: agreed amount + «сумма подтверждена» (MET-07, ATX-29)
 *   decline  → «Отказать»: reason for the client
 *   cancel   → «Отменить обращение» (client): reason for the provider
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { inboxApi, inboxKeys, type InquiryAction, type InquiryDetail, type InquiryStatus } from "@/lib/api/account-inbox";
import { qk } from "@/lib/api/keys";
import { INQUIRY_ACTIONS, statusLabel } from "@/lib/labels";
import { cx } from "@/lib/cx";
import { Button } from "@/components/ui/Button";
import { Checkbox, TextInput } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { DialogError, ReasonDialog } from "../shared/ReasonDialog";

const ORDER: InquiryAction[] = ["accept", "complete", "decline", "cancel"];

export interface InquiryActionTarget {
  id: string;
  status: InquiryStatus;
  actions: InquiryAction[];
  agreed_amount?: string | null;
  currency?: string;
  subject?: string;
}

export function InquiryActions({ inquiry, size = "md", className, onChanged }: {
  inquiry: InquiryActionTarget;
  size?: "sm" | "md";
  className?: string;
  onChanged?: (detail: InquiryDetail) => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [dialog, setDialog] = useState<InquiryAction | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [amount, setAmount] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  const actions = ORDER.filter((a) => inquiry.actions.includes(a));
  if (!actions.length) return null;

  const apply = async (action: InquiryAction, body: Parameters<typeof inboxApi.action>[2] = {}) => {
    const detail = await inboxApi.action(inquiry.id, action, body);
    queryClient.setQueryData(inboxKeys.detail(inquiry.id), detail);
    void queryClient.invalidateQueries({ queryKey: ["inquiries", "list"] });
    void queryClient.invalidateQueries({ queryKey: ["inquiries", "count"] });
    void queryClient.invalidateQueries({ queryKey: qk.counters });
    if (detail.conversation_id) void queryClient.invalidateQueries({ queryKey: inboxKeys.conversation(detail.conversation_id) });
    toast.success(`Статус обращения: ${statusLabel("inquiry", detail.status)}`);
    onChanged?.(detail);
    return detail;
  };

  const accept = async () => {
    setAccepting(true);
    try {
      await apply("accept");
    } catch (err) {
      toast.error(err, { action: { label: "Повторить", onClick: () => void accept() } });
    } finally {
      setAccepting(false);
    }
  };

  return (
    <div className={cx("acc-actions", className)} role="group" aria-label="Действия по обращению">
      {actions.map((a) => {
        if (a === "accept")
          return (
            <Button key={a} variant="primary" size={size === "sm" ? "sm" : undefined} loading={accepting} onClick={() => void accept()}>
              {INQUIRY_ACTIONS.accept}
            </Button>
          );
        if (a === "complete")
          return (
            <Button
              key={a}
              variant="soft"
              size={size === "sm" ? "sm" : undefined}
              icon="check"
              onClick={() => {
                setAmount(inquiry.agreed_amount ? String(Number(inquiry.agreed_amount)) : "");
                setConfirmed(false);
                setDialog("complete");
              }}
            >
              {INQUIRY_ACTIONS.complete}
            </Button>
          );
        return (
          <Button key={a} variant="danger" size={size === "sm" ? "sm" : undefined} onClick={() => setDialog(a)}>
            {INQUIRY_ACTIONS[a]}
          </Button>
        );
      })}

      <ReasonDialog
        open={dialog === "decline"}
        onClose={() => setDialog(null)}
        title="Отказать по обращению?"
        description="Клиент получит уведомление. Переписка останется в истории, но писать в неё будет нельзя."
        reasonPlaceholder="Например: в эти даты мастерская занята"
        confirmLabel={INQUIRY_ACTIONS.decline}
        onConfirm={(reason) => apply("decline", { reason })}
      />
      <ReasonDialog
        open={dialog === "cancel"}
        onClose={() => setDialog(null)}
        title="Отменить обращение?"
        description="Исполнитель получит уведомление. История переписки сохранится."
        reasonPlaceholder="Например: планы изменились"
        confirmLabel={INQUIRY_ACTIONS.cancel}
        onConfirm={(reason) => apply("cancel", { reason })}
      />
      <ReasonDialog
        open={dialog === "complete"}
        onClose={() => setDialog(null)}
        title="Завершить обращение?"
        description="Укажите итоговую сумму сделки, если она была. В статистику выручки попадают только подтверждённые суммы."
        withReason={false}
        confirmLabel={INQUIRY_ACTIONS.complete}
        confirmVariant="primary"
        onConfirm={async () => {
          const value = amount.trim().replace(",", ".").replace(/\s/g, "");
          if (value && !/^\d{1,10}(\.\d{1,2})?$/.test(value)) throw new DialogError("Сумма — число в рублях, например 15000 или 15000,50.");
          if (confirmed && !value) throw new DialogError("Укажите сумму, чтобы подтвердить её.");
          return apply("complete", { agreed_amount: value || null, amount_confirmed: confirmed });
        }}
      >
        <TextInput
          label="Сумма сделки, ₽"
          inputMode="decimal"
          placeholder="0 — если без оплаты"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          hint="Необязательно. Можно 0, если сделка без оплаты."
          data-autofocus
        />
        <Checkbox
          label="Сумма получена — подтверждаю"
          description="Только подтверждённые суммы учитываются в выручке."
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
      </ReasonDialog>
    </div>
  );
}
