"use client";
/**
 * Registration — one form (ACC-01): primary type (сёрфер / инструктор / шейпер / школа / прокат) +
 * additional specialties as checkboxes + consents. No documents are required (INS-03/05, ATX-04).
 * After success follows `next_step` (school → create organization), otherwise `?next=` or /account.
 */
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { routeForNextStep, safeNext } from "@/lib/api/auth";
import type { PrimaryType, SpecialtyCode } from "@/lib/api/types";
import { useRegister } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { apiFieldErrors, validate, type FormErrors } from "@/lib/forms";
import { PRIMARY_TYPE_LABELS, SPECIALTY_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { EXTRA_SPECIALTIES, PRIMARY_TYPES, registerSchema } from "@/lib/schemas/auth";
import { Button } from "@/components/ui/Button";
import { Checkbox, TextInput } from "@/components/ui/Field";
import { Icon, type IconName } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { AuthCard, FormError } from "./AuthCard";
import { PasswordInput } from "./PasswordInput";

const PRIMARY_META: Record<PrimaryType, { icon: IconName; hint: string }> = {
  surfer: { icon: "waves", hint: "Споты, занятия, аренда, GG Surfer" },
  instructor: { icon: "clover", hint: "Карточка, расписание, ученики" },
  shaper: { icon: "ruler", hint: "Мастерская и модели досок" },
  school: { icon: "school", hint: "Организация, команда, программы" },
  rental: { icon: "board", hint: "Снаряжение и бронирования" },
};

type Values = {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  primary_type: PrimaryType;
  extra_specialties: SpecialtyCode[];
  accept_terms: boolean;
  accept_privacy: boolean;
};

export function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const register = useRegister();
  const toast = useToast();
  const [values, setValues] = useState<Values>({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    primary_type: "surfer",
    extra_specialties: [],
    accept_terms: false,
    accept_privacy: false,
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const set = <K extends keyof Values>(key: K, value: Values[K]) => setValues((v) => ({ ...v, [key]: value }));

  const extras = EXTRA_SPECIALTIES.filter((s) => s !== values.primary_type);

  const toggleExtra = (code: SpecialtyCode, on: boolean) =>
    set("extra_specialties", on ? [...values.extra_specialties, code] : values.extra_specialties.filter((c) => c !== code));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const payload = { ...values, extra_specialties: values.extra_specialties.filter((s) => s !== values.primary_type) };
    const v = validate(registerSchema, payload);
    if (v.errors) {
      setErrors(v.errors);
      const first = Object.keys(v.errors)[0];
      document.querySelector<HTMLElement>(`[name="${first}"]`)?.focus();
      return;
    }
    setErrors({});
    register.mutate(
      { ...v.data, extra_specialties: v.data.extra_specialties as SpecialtyCode[] },
      {
        onSuccess: ({ result }) => {
          toast.success("Добро пожаловать в «Гдеволну»! ♡");
          router.replace(routeForNextStep(result.next_step, safeNext(params.get("next"))));
        },
        onError: (err) => setErrors(apiFieldErrors(err)),
      },
    );
  };

  const loginHrefWithNext = params.get("next") ? `${routes.login}?next=${encodeURIComponent(safeNext(params.get("next")))}` : routes.login;

  return (
    <AuthCard
      title="Добро пожаловать в «Гдеволну»!"
      lead="Давайте познакомимся. Один аккаунт — для всех ваших направлений: их можно добавить и позже."
      footer={
        <span>
          Уже с нами? <Link href={loginHrefWithNext}>Войти</Link>
        </span>
      }
    >
      <form onSubmit={submit} noValidate>
        <FormError message={errors._form} />

        <fieldset className="gv-fieldset" aria-describedby={errors.primary_type ? "primary-error" : undefined}>
          <legend className="gv-field-label">Кто вы в нашем сообществе?</legend>
          <div className="role-list gv-role-list">
            {PRIMARY_TYPES.map((type) => {
              const selected = values.primary_type === type;
              return (
                <label key={type} className={cx("role-item", selected && "selected")}>
                  <input
                    type="radio"
                    className="sr-only"
                    name="primary_type"
                    value={type}
                    checked={selected}
                    onChange={() => set("primary_type", type)}
                  />
                  <Icon name={PRIMARY_META[type].icon} size={26} />
                  <b>{PRIMARY_TYPE_LABELS[type]}</b>
                  <small>{PRIMARY_META[type].hint}</small>
                </label>
              );
            })}
          </div>
          {errors.primary_type && (
            <p id="primary-error" className="gv-field-error" role="alert">
              {errors.primary_type}
            </p>
          )}
        </fieldset>

        <fieldset className="gv-fieldset gv-extra-box">
          <legend className="gv-field-label">Дополнительные направления</legend>
          <p>Можно выбрать несколько — они появятся в одном личном кабинете.</p>
          <div className="gv-extra-list">
            {extras.map((code) => (
              <Checkbox
                key={code}
                name="extra_specialties"
                label={SPECIALTY_LABELS[code]}
                checked={values.extra_specialties.includes(code)}
                onChange={(e) => toggleExtra(code, e.target.checked)}
              />
            ))}
          </div>
        </fieldset>

        <div className="gv-form-grid">
          <TextInput
            label="Имя"
            name="first_name"
            autoComplete="given-name"
            required
            value={values.first_name}
            onChange={(e) => set("first_name", e.target.value)}
            error={errors.first_name}
            placeholder="Как к вам обращаться"
          />
          <TextInput
            label="Фамилия"
            name="last_name"
            autoComplete="family-name"
            value={values.last_name}
            onChange={(e) => set("last_name", e.target.value)}
            error={errors.last_name}
            hint="Для инструкторов и шейперов — видна в карточке"
          />
          <TextInput
            label="Электронная почта"
            type="email"
            name="email"
            autoComplete="email"
            inputMode="email"
            required
            value={values.email}
            onChange={(e) => set("email", e.target.value)}
            error={errors.email}
            placeholder="you@example.com"
            hint="Пришлём ссылку для подтверждения"
          />
          <PasswordInput
            label="Пароль"
            name="password"
            autoComplete="new-password"
            required
            value={values.password}
            onChange={(e) => set("password", e.target.value)}
            error={errors.password}
            hint="Не короче 8 символов и не только цифры"
          />
        </div>

        <div className="notice gv-register-note">
          GG Surfer (поиск компании для катания) включается отдельно в настройках — он не меняет основную роль.
          Сертификаты и документы для регистрации не нужны.
        </div>

        <Checkbox
          name="accept_terms"
          label="Принимаю пользовательское соглашение «Гдеволны»"
          checked={values.accept_terms}
          onChange={(e) => set("accept_terms", e.target.checked)}
          error={errors.accept_terms}
        />
        <Checkbox
          name="accept_privacy"
          label="Согласен на обработку персональных данных"
          description="Публично показываются только имя, фото и сведения профессиональной карточки — без email и телефона."
          checked={values.accept_privacy}
          onChange={(e) => set("accept_privacy", e.target.checked)}
          error={errors.accept_privacy}
        />

        <div className="gv-auth-actions">
          <Button type="submit" variant="primary" iconRight="arrow" loading={register.isPending} block>
            Создать аккаунт
          </Button>
        </div>
      </form>
    </AuthCard>
  );
}
