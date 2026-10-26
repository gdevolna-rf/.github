"use client";
/**
 * Безопасность (ACC-13): статус email + повторное письмо, смена пароля, двухфакторная аутентификация (TOTP:
 * секрет и otpauth-ссылка текстом, включение и отключение кодом). Для служебных ролей 2FA обязательна.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { accountApi, type TwoFactorSetup } from "@/lib/api/account";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import type { Me } from "@/lib/api/auth";
import { apiFieldErrors, type FormErrors } from "@/lib/forms";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";

function EmailBlock({ me }: { me: Me }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  return (
    <div className="acc-setting-line">
      <div>
        <b>Электронная почта</b>
        <p className="gv-ac-muted acc-break">{me.email}</p>
      </div>
      <div className="acc-inline-actions">
        <Badge tone={me.emailVerified ? "ok" : "new"}>{me.emailVerified ? "Подтверждена" : "Не подтверждена"}</Badge>
        {!me.emailVerified && (
          <Button
            variant="soft"
            size="sm"
            loading={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await accountApi.resendVerification();
                setSent(true);
                toast.success("Письмо отправлено ещё раз — проверьте почту");
              } catch (err) {
                toast.error(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            {sent ? "Отправить ещё раз" : "Отправить письмо"}
          </Button>
        )}
      </div>
    </div>
  );
}

function PasswordForm() {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState({ old: "", next: "", repeat: "" });
  const [errors, setErrors] = useState<FormErrors>({});
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const errs: FormErrors = {};
    if (!values.old) errs.old_password = "Введите текущий пароль.";
    if (values.next.length < 8) errs.new_password = "Новый пароль — не короче 8 символов.";
    if (values.next && values.next === values.old) errs.new_password = "Новый пароль совпадает с текущим.";
    if (values.repeat !== values.next) errs.repeat = "Пароли не совпадают.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      await accountApi.changePassword(values.old, values.next);
      toast.success("Пароль изменён. Другие устройства выйдут из аккаунта.");
      setValues({ old: "", next: "", repeat: "" });
      setOpen(false);
    } catch (err) {
      setErrors(apiFieldErrors(err));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <div className="acc-setting-line">
        <div>
          <b>Пароль</b>
          <p className="gv-ac-muted">После смены пароля другие сессии завершатся, текущая останется.</p>
        </div>
        <Button variant="soft" size="sm" onClick={() => setOpen(true)}>
          Сменить пароль
        </Button>
      </div>
    );
  }
  return (
    <form className="acc-subform" onSubmit={submit} noValidate aria-labelledby="pw-title">
      <h3 id="pw-title">Смена пароля</h3>
      <div className="gv-form-grid">
        <TextInput label="Текущий пароль" type="password" autoComplete="current-password" required value={values.old} onChange={(e) => setValues((v) => ({ ...v, old: e.target.value }))} error={errors.old_password} autoFocus />
        <span aria-hidden="true" />
        <TextInput label="Новый пароль" type="password" autoComplete="new-password" required value={values.next} onChange={(e) => setValues((v) => ({ ...v, next: e.target.value }))} error={errors.new_password} hint="Не короче 8 символов, не только цифры." />
        <TextInput label="Повторите новый пароль" type="password" autoComplete="new-password" required value={values.repeat} onChange={(e) => setValues((v) => ({ ...v, repeat: e.target.value }))} error={errors.repeat} />
      </div>
      {errors._form && (
        <p className="gv-form-error" role="alert">
          {errors._form}
        </p>
      )}
      <div className="gv-ac-form-action">
        <Button type="submit" variant="primary" loading={busy}>
          Сохранить пароль
        </Button>
        <Button variant="soft" onClick={() => setOpen(false)} disabled={busy}>
          Отмена
        </Button>
      </div>
    </form>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const toast = useToast();
  return (
    <Button
      variant="soft"
      size="sm"
      icon="check"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          toast.success("Скопировано");
        } catch {
          toast.error("Не удалось скопировать — выделите текст вручную.");
        }
      }}
    >
      {label}
    </Button>
  );
}

function TwoFactorBlock({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [setup, setSetup] = useState<TwoFactorSetup | null>(null);
  const [disabling, setDisabling] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const required = Boolean((me.raw.two_factor as { required?: boolean } | undefined)?.required);
  const enabled = me.twoFactor.enabled;

  const refreshMe = () => queryClient.invalidateQueries({ queryKey: qk.me, exact: true });

  const run = async (fn: () => Promise<unknown>, success: string) => {
    if (!/^\d{6}$/.test(code.replace(/\s/g, ""))) {
      setError("Введите 6 цифр из приложения-аутентификатора.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await fn();
      toast.success(success);
      setSetup(null);
      setDisabling(false);
      setCode("");
      await refreshMe();
    } catch (err) {
      setError(isApiError(err) ? (err.fieldError("code") ?? err.message) : "Не удалось проверить код.");
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      setSetup(await accountApi.twoFactorSetup());
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };

  const codeField = (
    <TextInput
      label="Код из приложения"
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={7}
      value={code}
      onChange={(e) => setCode(e.target.value.replace(/[^\d\s]/g, ""))}
      error={error}
      autoFocus
    />
  );

  return (
    <div className="acc-2fa">
      <div className="acc-setting-line">
        <div>
          <b>Двухфакторная аутентификация</b>
          <p className="gv-ac-muted">
            Код из приложения-аутентификатора (Google Authenticator, Aegis, 1Password) при входе в служебные разделы.
            {required ? " Для вашей служебной роли она обязательна." : ""}
          </p>
        </div>
        <div className="acc-inline-actions">
          <Badge tone={enabled ? "ok" : "muted"}>{enabled ? "Включена" : "Выключена"}</Badge>
          {!enabled && !setup && (
            <Button variant="soft" size="sm" loading={busy} onClick={() => void start()}>
              Настроить
            </Button>
          )}
          {enabled && !disabling && (
            <Button variant="danger" size="sm" onClick={() => setDisabling(true)}>
              Отключить
            </Button>
          )}
        </div>
      </div>

      {setup && !enabled && (
        <form
          className="acc-subform"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => accountApi.twoFactorEnable(code.replace(/\s/g, "")), "Двухфакторная аутентификация включена");
          }}
          aria-labelledby="tfa-setup-title"
        >
          <h3 id="tfa-setup-title">Подключите приложение</h3>
          <ol className="acc-steps">
            <li>
              В приложении выберите «Ввести ключ вручную» (TOTP, 6 цифр, 30 секунд) и вставьте секрет:
              <div className="acc-secret">
                <code aria-label="Секретный ключ">{setup.secret}</code>
                <CopyButton text={setup.secret} label="Копировать" />
              </div>
            </li>
            <li>
              Или откройте ссылку настройки на телефоне:
              <div className="acc-secret">
                <code className="acc-break" aria-label="Ссылка otpauth">
                  {setup.otpauth_uri}
                </code>
                <CopyButton text={setup.otpauth_uri} label="Копировать ссылку" />
              </div>
            </li>
            <li>Введите код, который покажет приложение.</li>
          </ol>
          {codeField}
          <div className="gv-ac-form-action">
            <Button type="submit" variant="primary" loading={busy}>
              Включить 2FA
            </Button>
            <Button variant="soft" onClick={() => setSetup(null)} disabled={busy}>
              Отмена
            </Button>
          </div>
        </form>
      )}

      {enabled && disabling && (
        <form
          className="acc-subform"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => accountApi.twoFactorDisable(code.replace(/\s/g, "")), "Двухфакторная аутентификация отключена");
          }}
          aria-labelledby="tfa-off-title"
        >
          <h3 id="tfa-off-title">Отключить двухфакторную аутентификацию</h3>
          {required && (
            <p className="gv-ac-note">
              <Icon name="alert" size={14} /> Без 2FA служебные разделы (модерация, администрирование) станут недоступны.
            </p>
          )}
          {codeField}
          <div className="gv-ac-form-action">
            <Button type="submit" variant="danger" loading={busy}>
              Отключить
            </Button>
            <Button variant="soft" onClick={() => setDisabling(false)} disabled={busy}>
              Отмена
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

export function SecuritySection({ me }: { me: Me }) {
  return (
    <section id="security" className="gv-ac-panel acc-settings-section" aria-labelledby="security-title">
      <h2 id="security-title">Вход и безопасность</h2>
      <p className="gv-ac-desc">Почта, пароль и двухфакторная защита аккаунта.</p>
      <EmailBlock me={me} />
      <PasswordForm />
      <TwoFactorBlock me={me} />
    </section>
  );
}
