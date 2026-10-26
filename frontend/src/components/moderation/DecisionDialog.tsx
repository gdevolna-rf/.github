"use client";
/**
 * Decision dialog for one case action (F04/F08/F09/F14, AT-07/08, TRUST-04/07): explains the consequence,
 * asks for the comment where the API requires it, complaint measure + optional expiry for «suspended»,
 * «добавить фото в галерею» for spot proposals, and the revert conflict (409 revert_conflict → confirm force).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { isApiError } from "@/lib/api/errors";
import { modKeys, moderationApi, type CaseAction, type DecisionInput, type ModerationCaseDetail } from "@/lib/api/moderation";
import { choiceCode } from "@/lib/labels";
import { Button } from "@/components/ui/Button";
import { Checkbox, TextInput, Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { actionRule, validateDecisionText } from "./actions";
import { COMPLAINT_ACTION_HINTS, COMPLAINT_ACTION_LABELS } from "./labels";

type Measure = NonNullable<DecisionInput["complaintAction"]>;
const MEASURES: Measure[] = ["none", "warning", "hidden", "suspended"];

/** "2026-10-21T10:00" (local) → ISO with offset. */
function localToIso(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function measureAvailability(c: ModerationCaseDetail): Record<Measure, string | null> {
  const t = c.target && c.target.type === "complaint" ? c.target : null;
  const targetType = t ? choiceCode(t.target_type) : null;
  const hasOwner = Boolean(t?.target_owner);
  return {
    none: null,
    warning: hasOwner ? null : "У объекта нет владельца",
    hidden: targetType === "account" ? "Профиль нельзя скрыть — используйте ограничение" : t?.target_snapshot?.exists === false ? "Объект уже удалён" : null,
    suspended: hasOwner ? null : "У объекта нет владельца",
  };
}

export function DecisionDialog({
  c,
  action,
  onClose,
}: {
  c: ModerationCaseDetail;
  action: CaseAction | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const kind = choiceCode(c.kind) ?? "";
  const targetId = c.target?.id ?? c.target_id ?? "";
  const rule = action ? actionRule(kind, action) : null;

  const [text, setText] = useState("");
  const [textError, setTextError] = useState<string | null>(null);
  const [gallery, setGallery] = useState(false);
  const [measure, setMeasure] = useState<Measure>("none");
  const [expires, setExpires] = useState("");
  const [conflict, setConflict] = useState<string[] | null>(null);
  const [expiresError, setExpiresError] = useState<string | null>(null);

  const decide = useMutation({
    mutationFn: (input: DecisionInput) => moderationApi.decide(kind, targetId, action!, input),
    onSuccess: () => {
      toast.success(rule ? `${rule.title}: готово` : "Решение сохранено");
      void queryClient.invalidateQueries({ queryKey: modKeys.all });
      onClose();
    },
    onError: (err) => {
      if (isApiError(err) && err.code === "revert_conflict") {
        setConflict(Object.keys(err.fields));
        return;
      }
      if (isApiError(err) && err.isConflict) {
        toast.error(err.message || "Решение по кейсу уже принято — обновили данные.");
        void queryClient.invalidateQueries({ queryKey: modKeys.all });
        onClose();
      }
    },
  });

  const resetDecision = decide.reset;
  useEffect(() => {
    if (!action) return;
    setText("");
    setTextError(null);
    setGallery(false);
    setMeasure("none");
    setExpires("");
    setExpiresError(null);
    setConflict(null);
    resetDecision();
  }, [action, resetDecision]);

  if (!action || !rule) return null;

  const availability = measureAvailability(c);
  const evidenceImages =
    c.target?.type === "spot_change" ? c.target.evidence.filter((m) => m.kind === "image" && m.status === "ready").length : 0;
  const diffLabels = c.target?.type === "spot_change" ? Object.fromEntries(c.target.diff.map((d) => [d.field, d.label])) : {};

  const send = (force = false) => {
    const err = validateDecisionText(rule, text);
    setTextError(err);
    if (err) return;
    if (action === "resolve" && measure === "suspended" && expires) {
      const iso = localToIso(expires);
      if (!iso || new Date(iso).getTime() <= Date.now()) {
        setTextError(null);
        decide.reset();
        setExpiresError("Срок ограничения должен быть в будущем.");
        return;
      }
    }
    setExpiresError(null);
    decide.mutate({
      text,
      addEvidenceToGallery: gallery,
      force,
      complaintAction: measure,
      expiresAt: action === "resolve" && measure === "suspended" ? localToIso(expires) : null,
    });
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(false);
  };

  const apiErr = isApiError(decide.error) && decide.error.code !== "revert_conflict" ? decide.error : null;
  const serverFieldError = apiErr ? apiErr.fieldError(rule.field) ?? apiErr.fieldError("note") ?? apiErr.fieldError("comment") : undefined;
  const formId = `decision-${action}`;

  return (
    <Modal
      open
      onClose={onClose}
      title={rule.title}
      description={rule.description}
      size="wide"
      footer={
        conflict ? (
          <>
            <Button variant="pill" onClick={onClose}>
              Отмена
            </Button>
            <Button variant="danger" icon="refresh" loading={decide.isPending} onClick={() => send(true)}>
              Откатить всё равно
            </Button>
          </>
        ) : (
          <>
            <Button variant="pill" onClick={onClose} disabled={decide.isPending}>
              Отмена
            </Button>
            <Button type="submit" form={formId} variant={rule.tone === "danger" ? "danger" : "primary"} loading={decide.isPending}>
              {rule.confirm}
            </Button>
          </>
        )
      }
    >
      {conflict ? (
        <div className="gv-mod-conflict" role="alert">
          <Icon name="alert" size={22} />
          <div>
            <h3>После этой правки карточку уже меняли</h3>
            <p>
              Поля {conflict.map((f) => `«${diffLabels[f] ?? f}»`).join(", ")} изменились после одобрения. Откат вернёт их к значениям
              до правки и перезапишет более поздние изменения.
            </p>
          </div>
        </div>
      ) : (
        <form id={formId} onSubmit={submit} noValidate className="gv-mod-decision">
          {apiErr && !serverFieldError && (
            <div className="gv-form-error" role="alert">
              <Icon name="alert" size={18} />
              <span>{apiErr.message}</span>
            </div>
          )}
          {action === "resolve" && (
            <fieldset className="gv-mod-measures">
              <legend>Мера</legend>
              {MEASURES.map((m) => {
                const disabledReason = availability[m];
                return (
                  <label key={m} className={disabledReason ? "is-disabled" : undefined}>
                    <input type="radio" name="measure" value={m} checked={measure === m} disabled={Boolean(disabledReason)} onChange={() => setMeasure(m)} />
                    <span>
                      <b>{COMPLAINT_ACTION_LABELS[m]}</b>
                      <small>{disabledReason ?? COMPLAINT_ACTION_HINTS[m]}</small>
                    </span>
                  </label>
                );
              })}
            </fieldset>
          )}
          {action === "resolve" && measure === "suspended" && (
            <TextInput
              label="Ограничить до"
              type="datetime-local"
              value={expires}
              onChange={(e) => setExpires(e.target.value)}
              hint="Пусто — бессрочно (можно снять вручную в сводке аккаунта)"
              error={expiresError ?? apiErr?.fieldError("expires_at")}
            />
          )}
          {action === "approve" && kind === "spot_change" && evidenceImages > 0 && (
            <Checkbox
              label="Добавить фото-доказательства в галерею спота"
              description={`${evidenceImages} фото станут публичными с подписью «Фото от участника». При откате правки они будут убраны.`}
              checked={gallery}
              onChange={(e) => setGallery(e.target.checked)}
            />
          )}
          <Textarea
            label={rule.fieldLabel}
            required={rule.required}
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={rule.maxLength}
            rows={rule.maxLength > 300 ? 5 : 3}
            placeholder={rule.placeholder}
            error={textError ?? serverFieldError}
            data-autofocus
          />
        </form>
      )}
    </Modal>
  );
}
