"use client";
/**
 * /reset-password            → request a link (POST auth/password-reset {email}); always the same success text
 *                              (no account enumeration).
 * /reset-password?uid=&token= → set a new password (POST auth/password-reset/confirm).
 */
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { authApi } from "@/lib/api/auth";
import { apiFieldErrors, validate, type FormErrors } from "@/lib/forms";
import { routes } from "@/lib/routes";
import { resetConfirmSchema, resetRequestSchema } from "@/lib/schemas/auth";
import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { SuccessState } from "@/components/ui/States";
import { AuthCard, FormError } from "./AuthCard";
import { PasswordInput } from "./PasswordInput";

function RequestForm() {
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const v = validate(resetRequestSchema, { email });
    if (v.errors) return setErrors(v.errors);
    setErrors({});
    setPending(true);
    authApi
      .requestPasswordReset(v.data.email)
      .then(() => setSent(true))
      .catch((err) => setErrors(apiFieldErrors(err)))
      .finally(() => setPending(false));
  };

  if (sent) {
    return (
      <SuccessState
        title="Проверьте почту"
        text={`Если аккаунт с адресом ${email} существует, мы отправили на него ссылку для смены пароля.`}
        action={{ label: "Вернуться ко входу", href: routes.login }}
      />
    );
  }
  return (
    <form onSubmit={submit} noValidate>
      <FormError message={errors._form} />
      <TextInput
        label="Электронная почта"
        type="email"
        name="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={errors.email}
        placeholder="you@example.com"
      />
      <Button type="submit" variant="primary" block loading={pending} iconRight="arrow">
        Отправить ссылку
      </Button>
    </form>
  );
}

function ConfirmForm({ uid, token }: { uid: string; token: string }) {
  const [values, setValues] = useState({ new_password: "", repeat: "" });
  const [errors, setErrors] = useState<FormErrors>({});
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const v = validate(resetConfirmSchema, values);
    if (v.errors) return setErrors(v.errors);
    setErrors({});
    setPending(true);
    authApi
      .confirmPasswordReset({ uid, token, new_password: v.data.new_password })
      .then(() => setDone(true))
      .catch((err) => setErrors(apiFieldErrors(err, { token: "_form", uid: "_form" })))
      .finally(() => setPending(false));
  };

  if (done) {
    return <SuccessState title="Пароль изменён" text="Теперь войдите с новым паролем." action={{ label: "Войти", href: routes.login }} />;
  }
  return (
    <form onSubmit={submit} noValidate>
      <FormError message={errors._form} />
      <PasswordInput
        label="Новый пароль"
        name="new_password"
        autoComplete="new-password"
        required
        value={values.new_password}
        onChange={(e) => setValues({ ...values, new_password: e.target.value })}
        error={errors.new_password}
        hint="Не короче 8 символов и не только цифры"
      />
      <PasswordInput
        label="Повторите пароль"
        name="repeat"
        autoComplete="new-password"
        required
        value={values.repeat}
        onChange={(e) => setValues({ ...values, repeat: e.target.value })}
        error={errors.repeat}
      />
      <Button type="submit" variant="primary" block loading={pending} iconRight="arrow">
        Сохранить пароль
      </Button>
    </form>
  );
}

export function ResetPassword() {
  const params = useSearchParams();
  const uid = params.get("uid");
  const token = params.get("token");
  const confirming = Boolean(uid && token);
  return (
    <AuthCard
      narrow
      title={confirming ? "Новый пароль" : "Восстановление доступа"}
      lead={confirming ? "Придумайте новый пароль для входа в «Гдеволну»." : "Укажите почту аккаунта — пришлём ссылку для смены пароля."}
      footer={<Link href={routes.login}>← Вернуться ко входу</Link>}
    >
      {confirming ? <ConfirmForm uid={uid!} token={token!} /> : <RequestForm />}
    </AuthCard>
  );
}
