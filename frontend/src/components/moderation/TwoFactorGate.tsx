"use client";
/**
 * Staff 2FA gate (TZ 11 «2FA для админов/модераторов», 5.3, DATA-09, BR-04):
 *  - 2FA not enabled → setup: POST me/2fa/setup (secret for the authenticator app) → POST me/2fa/enable {code}
 *    (enabling also verifies the current session);
 *  - enabled but this session is not verified → TOTP prompt: POST auth/2fa/verify {code};
 *  - verified → children.
 * The server re-checks the role and the session mark on every moderation request (the gate is UX only).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent, type ReactNode } from "react";
import type { Me } from "@/lib/api/auth";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import { modKeys, normalizeTotp, twoFactorApi, type TwoFactorState } from "@/lib/api/moderation";
import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";

function codeError(err: unknown): string | null {
  if (!err) return null;
  if (isApiError(err)) {
    if (err.code === "two_factor_code_invalid") return "Неверный или устаревший код. Введите новый код из приложения.";
    if (err.status === 429) return err.message || "Слишком много попыток. Попробуйте через несколько минут.";
    return err.fieldError("code") ?? err.message;
  }
  return "Не удалось проверить код. Попробуйте ещё раз.";
}

function useApplyState() {
  const queryClient = useQueryClient();
  return (state: TwoFactorState) => {
    queryClient.setQueryData<Me | null | undefined>(qk.me, (prev) =>
      prev ? { ...prev, twoFactor: { enabled: state.enabled, verified: state.verified } } : prev,
    );
    void queryClient.invalidateQueries({ queryKey: qk.me, exact: true });
    void queryClient.invalidateQueries({ queryKey: modKeys.all });
  };
}

function CodeField({ value, onChange, error, autoFocus }: { value: string; onChange: (v: string) => void; error: string | null; autoFocus?: boolean }) {
  return (
    <TextInput
      label="Код из приложения"
      hint="6 цифр, обновляется каждые 30 секунд"
      inputMode="numeric"
      autoComplete="one-time-code"
      pattern="[0-9 ]*"
      maxLength={7}
      required
      value={value}
      onChange={(e) => onChange(e.target.value.replace(/[^\d ]/g, ""))}
      error={error}
      inputClassName="gv-mod-otp"
      autoFocus={autoFocus}
    />
  );
}

export function TwoFactorVerify() {
  const apply = useApplyState();
  const toast = useToast();
  const [code, setCode] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const verify = useMutation({
    mutationFn: (c: string) => twoFactorApi.verify(c),
    onSuccess: (state) => {
      toast.success("Сессия подтверждена");
      apply(state);
    },
    onError: () => setCode(""),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const c = normalizeTotp(code);
    if (c.length !== 6) {
      setLocalError("Введите 6 цифр кода.");
      return;
    }
    setLocalError(null);
    verify.mutate(c);
  };

  return (
    <section className="gv-ac-panel gv-mod-gate" aria-labelledby="mod-2fa-title">
      <span className="gv-mod-gate-icon" aria-hidden="true">
        <Icon name="lock" size={26} />
      </span>
      <h2 id="mod-2fa-title">Подтвердите вход кодом 2FA</h2>
      <p className="gv-ac-desc">
        Модерация открывается только после подтверждения этой сессии одноразовым кодом из приложения-аутентификатора
        (Google Authenticator, Aegis, 1Password). Каждое решение записывается в журнал действий.
      </p>
      <form onSubmit={submit} noValidate className="gv-mod-gate-form">
        <CodeField value={code} onChange={setCode} error={localError ?? codeError(verify.error)} autoFocus />
        <Button type="submit" variant="primary" iconRight="check" loading={verify.isPending}>
          Подтвердить
        </Button>
      </form>
    </section>
  );
}

function groupSecret(secret: string): string {
  return secret.replace(/(.{4})/g, "$1 ").trim();
}

export function TwoFactorSetup() {
  const apply = useApplyState();
  const toast = useToast();
  const secretId = useId();
  const [code, setCode] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const setup = useMutation({ mutationFn: () => twoFactorApi.setup() });
  const enable = useMutation({
    mutationFn: (c: string) => twoFactorApi.enable(c),
    onSuccess: (state) => {
      toast.success("Двухфакторная аутентификация включена");
      apply(state);
    },
    onError: () => setCode(""),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const c = normalizeTotp(code);
    if (c.length !== 6) {
      setLocalError("Введите 6 цифр кода.");
      return;
    }
    setLocalError(null);
    enable.mutate(c);
  };

  const copy = (secret: string) => {
    navigator.clipboard?.writeText(secret).then(
      () => toast.success("Ключ скопирован"),
      () => toast.error("Не удалось скопировать — выделите ключ вручную"),
    );
  };

  return (
    <section className="gv-ac-panel gv-mod-gate" aria-labelledby="mod-2fa-setup-title">
      <span className="gv-mod-gate-icon" aria-hidden="true">
        <Icon name="shield" size={26} />
      </span>
      <h2 id="mod-2fa-setup-title">Включите двухфакторную аутентификацию</h2>
      <p className="gv-ac-desc">
        Для служебных ролей 2FA обязательна. Добавьте ключ в приложение-аутентификатор и введите код, который оно
        покажет, — после этого откроется модерация.
      </p>
      <ol className="gv-mod-steps">
        <li>
          <b>Получите ключ</b>
          {!setup.data ? (
            <div className="gv-mod-step-body">
              <Button variant="soft" icon="lock" onClick={() => setup.mutate()} loading={setup.isPending}>
                Показать ключ для приложения
              </Button>
              {setup.isError && (
                <p className="gv-field-error" role="alert">
                  {isApiError(setup.error) && setup.error.code === "two_factor_already_enabled"
                    ? "2FA уже включена — обновите страницу и введите код."
                    : isApiError(setup.error)
                      ? setup.error.message
                      : "Не удалось получить ключ. Попробуйте ещё раз."}
                </p>
              )}
            </div>
          ) : (
            <div className="gv-mod-step-body">
              <p className="gv-field-hint">
                В приложении выберите «Ввести ключ вручную», тип — по времени (TOTP), 6 цифр.
              </p>
              <div className="gv-mod-secret">
                <code id={secretId} aria-label="Секретный ключ">
                  {groupSecret(setup.data.secret)}
                </code>
                <Button variant="soft" size="sm" icon="paperclip" onClick={() => copy(setup.data!.secret)} aria-describedby={secretId}>
                  Скопировать
                </Button>
              </div>
              <a className="feature-link" href={setup.data.otpauth_uri}>
                Открыть в приложении на этом устройстве
              </a>
            </div>
          )}
        </li>
        <li>
          <b>Введите код из приложения</b>
          <form onSubmit={submit} noValidate className="gv-mod-gate-form">
            <CodeField value={code} onChange={setCode} error={localError ?? codeError(enable.error)} />
            <Button type="submit" variant="primary" iconRight="check" loading={enable.isPending} disabled={!setup.data}>
              Включить и продолжить
            </Button>
          </form>
        </li>
      </ol>
    </section>
  );
}

/** Renders children only for a staff session with 2FA verified. */
export function TwoFactorGate({ me, children }: { me: Me; children: ReactNode }) {
  if (!me.twoFactor.enabled) return <TwoFactorSetup />;
  if (!me.twoFactor.verified) return <TwoFactorVerify />;
  return <>{children}</>;
}
