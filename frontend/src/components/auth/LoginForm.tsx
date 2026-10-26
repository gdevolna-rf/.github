"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { safeNext } from "@/lib/api/auth";
import { useLogin, useMe } from "@/lib/auth/hooks";
import { apiFieldErrors, validate, type FormErrors } from "@/lib/forms";
import { loginSchema } from "@/lib/schemas/auth";
import { routes } from "@/lib/routes";
import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { AuthCard, FormError } from "./AuthCard";
import { PasswordInput } from "./PasswordInput";

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const { me } = useMe();
  const login = useLogin();
  const toast = useToast();
  const [values, setValues] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState<FormErrors>({});

  // Already logged in → go on.
  useEffect(() => {
    if (me && !login.isPending) router.replace(next);
  }, [me, next, router, login.isPending]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const v = validate(loginSchema, values);
    if (v.errors) return setErrors(v.errors);
    setErrors({});
    login.mutate(v.data, {
      onSuccess: (user) => {
        toast.success(user ? `С возвращением, ${user.firstName || user.displayName}!` : "Вы вошли");
        router.replace(next);
      },
      onError: (err) => setErrors(apiFieldErrors(err)),
    });
  };

  const registerHref = params.get("next") ? `${routes.register}?next=${encodeURIComponent(next)}` : routes.register;

  return (
    <AuthCard
      narrow
      title="Вход в «Гдеволну»"
      lead="Войдите, чтобы писать инструкторам и шейперам, бронировать занятия и аренду, сохранять избранное."
      footer={
        <>
          <span>
            Впервые здесь? <Link href={registerHref}>Создать аккаунт</Link>
          </span>
          <Link href={routes.resetPassword}>Забыли пароль?</Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate>
        <FormError message={errors._form} />
        <TextInput
          label="Электронная почта"
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          required
          value={values.email}
          onChange={(e) => setValues({ ...values, email: e.target.value })}
          error={errors.email}
          placeholder="you@example.com"
        />
        <PasswordInput
          label="Пароль"
          name="password"
          autoComplete="current-password"
          required
          value={values.password}
          onChange={(e) => setValues({ ...values, password: e.target.value })}
          error={errors.password}
        />
        <div className="gv-auth-actions">
          <Button type="submit" variant="primary" iconRight="arrow" loading={login.isPending} block>
            Войти
          </Button>
        </div>
      </form>
    </AuthCard>
  );
}
