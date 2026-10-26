"use client";
/**
 * «Мой профиль» (ACC-07/08/14, CABINET_SCREENS §5.2): the single registration/edit form of the common profile.
 * Photo is edited only here (UX-10). Public fields and private data (phone, birth date, private contacts) are
 * separated and the private block is marked «видно только вам». The save button text follows the state and
 * «Посмотреть на сайте» opens the public view. Professional data is edited in the specialty sections.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { z } from "zod";
import { accountApi, accountKeys, profileFromRaw, type MeProfile, type ProfilePatch } from "@/lib/api/account";
import { normalizeMe } from "@/lib/api/auth";
import { qk } from "@/lib/api/keys";
import type { Media } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { apiFieldErrors, validate, type FormErrors } from "@/lib/forms";
import { RIDING_LEVEL_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Select, Textarea, TextInput } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { MediaUploader } from "@/components/ui/MediaUploader";
import { Avatar } from "@/components/ui/Avatar";
import { LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { BOARD_TYPE_OPTIONS, INTEREST_OPTIONS, LANGUAGE_OPTIONS } from "../shared/options";
import { ProfileSettingsTabs } from "../shared/ProfileSettingsTabs";
import { TagPicker } from "../shared/TagPicker";
import { publicProfileHref, todayIso } from "../shared/utils";

const HANDLE_RE = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;
const thisYear = new Date().getFullYear();

const schema = z.object({
  first_name: z.string().trim().min(1, "Укажите имя — так вас увидят в переписке и на сайте.").max(80, "Не длиннее 80 символов."),
  last_name: z.string().trim().max(80, "Не длиннее 80 символов."),
  handle: z
    .string()
    .trim()
    .toLowerCase()
    .min(3, "Адрес профиля — от 3 до 40 символов.")
    .max(40, "Адрес профиля — от 3 до 40 символов.")
    .refine((v) => HANDLE_RE.test(v) && !v.includes("--"), "Только латинские буквы, цифры и дефис (не в начале и не в конце)."),
  city: z.string().max(120, "Не длиннее 120 символов."),
  bio: z.string().max(3000, "Не длиннее 3000 символов."),
  surfing_since: z
    .string()
    .refine((v) => v === "" || (/^\d{4}$/.test(v) && Number(v) >= 1950 && Number(v) <= thisYear), `Год от 1950 до ${thisYear}.`),
  phone: z.string().regex(/^[0-9+()\-\s]{0,32}$/, "Телефон: цифры, пробелы, +, -, скобки."),
  birth_date: z.string().refine((v) => v === "" || v <= todayIso(), "Дата рождения не может быть в будущем."),
  private_contacts: z.string().max(2000, "Не длиннее 2000 символов."),
});

interface FormState {
  first_name: string;
  last_name: string;
  handle: string;
  avatar: Media[];
  region_id: string;
  city: string;
  bio: string;
  fun_facts: string[];
  surfing_since: string;
  riding_level: string;
  preferred_board_types: string[];
  favorite_spot_ids: string[];
  interests: string[];
  languages: string[];
  phone: string;
  birth_date: string;
  private_contacts: string;
}

function toForm(p: MeProfile): FormState {
  return {
    first_name: p.first_name,
    last_name: p.last_name,
    handle: p.handle,
    avatar: p.avatar ? [p.avatar] : [],
    region_id: p.region ? String(p.region.id) : "",
    city: p.city,
    bio: p.bio,
    fun_facts: p.fun_facts,
    surfing_since: p.surfing_since ? String(p.surfing_since) : "",
    riding_level: p.riding_level || "",
    preferred_board_types: p.preferred_board_types,
    favorite_spot_ids: p.favorite_spot_ids,
    interests: p.interests,
    languages: p.languages,
    phone: p.phone,
    birth_date: p.birth_date ?? "",
    private_contacts: p.private_contacts,
  };
}

/** Only changed fields go to PATCH /me (a partial update cannot overwrite a parallel change elsewhere). */
export function buildPatch(initial: FormState, form: FormState): ProfilePatch {
  const patch: ProfilePatch = {};
  const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
  if (form.first_name.trim() !== initial.first_name) patch.first_name = form.first_name.trim();
  if (form.last_name.trim() !== initial.last_name) patch.last_name = form.last_name.trim();
  if (form.handle.trim().toLowerCase() !== initial.handle) patch.handle = form.handle.trim().toLowerCase();
  const avatarId = form.avatar[0]?.id ?? null;
  if (avatarId !== (initial.avatar[0]?.id ?? null)) patch.avatar_id = avatarId;
  if (form.region_id !== initial.region_id) patch.region_id = form.region_id ? Number(form.region_id) : null;
  if (form.city.trim() !== initial.city) patch.city = form.city.trim();
  if (form.bio !== initial.bio) patch.bio = form.bio;
  if (!same(form.fun_facts, initial.fun_facts)) patch.fun_facts = form.fun_facts;
  if (form.surfing_since !== initial.surfing_since) patch.surfing_since = form.surfing_since ? Number(form.surfing_since) : null;
  if (form.riding_level !== initial.riding_level) patch.riding_level = form.riding_level as ProfilePatch["riding_level"];
  if (!same(form.preferred_board_types, initial.preferred_board_types)) patch.preferred_board_types = form.preferred_board_types;
  if (!same(form.favorite_spot_ids, initial.favorite_spot_ids)) patch.favorite_spot_ids = form.favorite_spot_ids;
  if (!same(form.interests, initial.interests)) patch.interests = form.interests;
  if (!same(form.languages, initial.languages)) patch.languages = form.languages;
  if (form.phone.trim() !== initial.phone) patch.phone = form.phone.trim();
  if (form.birth_date !== initial.birth_date) patch.birth_date = form.birth_date || null;
  if (form.private_contacts !== initial.private_contacts) patch.private_contacts = form.private_contacts;
  return patch;
}

const FIELD_ALIASES: Record<string, string> = { region_id: "region_id", avatar_id: "avatar", favorite_spot_ids: "favorite_spot_ids" };

export function ProfileForm() {
  const { me } = useMe();
  const queryClient = useQueryClient();
  const toast = useToast();
  const profile = useMemo(() => profileFromRaw(me?.raw), [me]);
  const initial = useMemo(() => toForm(profile), [profile]);
  const [form, setForm] = useState<FormState>(initial);
  const [errors, setErrors] = useState<FormErrors>({});
  const [saving, setSaving] = useState(false);
  const [baseline, setBaseline] = useState<FormState>(initial);

  // A fresh /me (another tab saved, realtime) resets the form only when the user has no unsaved edits.
  const patch = useMemo(() => buildPatch(baseline, form), [baseline, form]);
  const dirty = Object.keys(patch).length > 0;
  useEffect(() => {
    if (!dirty) {
      setForm(initial);
      setBaseline(initial);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial]);

  // Warn before leaving with unsaved changes
  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [dirty]);

  const regions = useQuery({ queryKey: accountKeys.regions, queryFn: accountApi.regions, staleTime: 60 * 60_000 });
  const spots = useQuery({ queryKey: accountKeys.spotOptions, queryFn: accountApi.spots, staleTime: 10 * 60_000 });

  if (!me) return <LoadingState label="Загружаем профиль…" />;

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    if (errors[key as string]) setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const firstFill = !profile.region && !profile.bio && !profile.avatar && profile.interests.length === 0;
  const pub = publicProfileHref(me);
  const handleChanged = form.handle.trim().toLowerCase() !== baseline.handle;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!dirty || saving) return;
    const checked = validate(schema, form);
    if (checked.errors) {
      setErrors(checked.errors);
      toast.error("Проверьте выделенные поля");
      requestAnimationFrame(() => document.querySelector<HTMLElement>(".acc-profile [aria-invalid='true']")?.focus());
      return;
    }
    setSaving(true);
    setErrors({});
    try {
      const raw = await accountApi.updateProfile(patch);
      const next = normalizeMe(raw);
      queryClient.setQueryData(qk.me, next);
      const fresh = toForm(profileFromRaw(next.raw));
      setBaseline(fresh);
      setForm(fresh);
      toast.success(firstFill ? "Профиль заполнен — добро пожаловать!" : "Профиль сохранён");
    } catch (err) {
      const fieldErrors = apiFieldErrors(err, FIELD_ALIASES);
      setErrors(fieldErrors);
      toast.error(err, { action: { label: "Повторить", onClick: () => document.querySelector<HTMLFormElement>(".acc-profile")?.requestSubmit() } });
    } finally {
      setSaving(false);
    }
  };

  const regionOptions = (regions.data ?? []).map((r) => ({ value: String(r.id), label: r.name }));
  if (form.region_id && !regionOptions.some((o) => o.value === form.region_id) && profile.region) {
    regionOptions.unshift({ value: String(profile.region.id), label: profile.region.name });
  }
  const spotOptions = (spots.data?.results ?? []).map((s) => ({
    value: String(s.id),
    label: s.region?.name ? `${s.name} · ${s.region.name}` : s.name,
  }));

  const saveLabel = !dirty ? "Изменений нет" : firstFill ? "Завершить профиль" : "Сохранить изменения";

  return (
    <>
      <ProfileSettingsTabs />
      <form className="gv-ac-panel acc-profile" onSubmit={onSubmit} noValidate aria-labelledby="profile-title">
        <h2 id="profile-title">Мой профиль</h2>
        <p className="gv-ac-desc">
          Имя, регион и фотография общие для всех подключённых направлений. Профессиональные сведения редактируются в
          соответствующих разделах.
        </p>

        <section className="acc-form-section" aria-labelledby="profile-photo">
          <h3 id="profile-photo">Фото профиля</h3>
          <div className="acc-avatar-row">
            <Avatar media={form.avatar[0] ?? null} name={form.first_name || me.displayName} size={86} />
            <div className="acc-avatar-uploader">
              <MediaUploader
                purpose="avatar"
                maxFiles={1}
                value={form.avatar}
                onChange={(items) => set("avatar", items.slice(-1))}
                label="Фотография"
                hint="JPG, PNG или WebP до 15 МБ. Фото меняется только здесь — в шапке сайта оно не редактируется."
              />
              {errors.avatar && (
                <p className="gv-field-error" role="alert">
                  {errors.avatar}
                </p>
              )}
            </div>
          </div>
        </section>

        <section className="acc-form-section" aria-labelledby="profile-public">
          <h3 id="profile-public">
            <Icon name="users" size={16} /> Публичные сведения
          </h3>
          <p className="gv-ac-muted">Эти данные видят другие участники в анкете GG Surfer и в переписке.</p>
          <div className="gv-form-grid">
            <TextInput label="Имя" required autoComplete="given-name" value={form.first_name} maxLength={80} onChange={(e) => set("first_name", e.target.value)} error={errors.first_name} />
            <TextInput label="Фамилия" autoComplete="family-name" value={form.last_name} maxLength={80} onChange={(e) => set("last_name", e.target.value)} error={errors.last_name} />
            <TextInput
              label="Адрес профиля (имя пользователя)"
              required
              value={form.handle}
              maxLength={40}
              autoCapitalize="none"
              spellCheck={false}
              onChange={(e) => set("handle", e.target.value)}
              error={errors.handle}
              hint={
                handleChanged && baseline.handle
                  ? `Старый адрес @${baseline.handle} продолжит открывать ваш профиль — ссылки не сломаются.`
                  : "Латинские буквы, цифры и дефис, 3–40 символов. Связи заявок и записей сохраняются при смене."
              }
            />
            <Select
              label="Регион"
              placeholder={regions.isPending ? "Загружаем регионы…" : "Регион не указан"}
              options={regionOptions}
              value={form.region_id}
              onChange={(e) => set("region_id", e.target.value)}
              error={errors.region_id ?? (regions.isError ? "Не удалось загрузить регионы — обновите страницу." : undefined)}
            />
            <TextInput label="Город" autoComplete="address-level2" value={form.city} maxLength={120} onChange={(e) => set("city", e.target.value)} error={errors.city} />
            <TextInput
              label="Катаюсь с (год)"
              inputMode="numeric"
              placeholder={String(thisYear - 2)}
              value={form.surfing_since}
              maxLength={4}
              onChange={(e) => set("surfing_since", e.target.value.replace(/\D/g, ""))}
              error={errors.surfing_since}
            />
            <Select
              label="Уровень катания"
              placeholder="Не указан"
              options={Object.entries(RIDING_LEVEL_LABELS).map(([value, label]) => ({ value, label }))}
              value={form.riding_level}
              onChange={(e) => set("riding_level", e.target.value)}
              error={errors.riding_level}
            />
          </div>
          <Textarea label="О себе" value={form.bio} maxLength={3000} rows={4} placeholder="Где катаетесь, что ищете в сообществе, чем можете помочь на берегу…" onChange={(e) => set("bio", e.target.value)} error={errors.bio} />
          <TagPicker
            label="Забавные факты"
            variant="list"
            presets={[]}
            value={form.fun_facts}
            onChange={(v) => set("fun_facts", v)}
            max={10}
            maxLength={200}
            customLabel="Добавить факт"
            customPlaceholder="Например: однажды видел косаток прямо с доски"
            error={errors.fun_facts}
          />
          <TagPicker label="Предпочитаемые доски" presets={BOARD_TYPE_OPTIONS} value={form.preferred_board_types} onChange={(v) => set("preferred_board_types", v)} max={12} maxLength={40} customLabel="Другая доска" error={errors.preferred_board_types} />
          <TagPicker
            label="Любимые споты"
            presets={spotOptions}
            value={form.favorite_spot_ids}
            onChange={(v) => set("favorite_spot_ids", v)}
            max={50}
            allowCustom={false}
            hint={spots.isError ? "Не удалось загрузить споты — обновите страницу." : spotOptions.length === 0 && !spots.isPending ? "В каталоге пока нет спотов." : undefined}
            error={errors.favorite_spot_ids}
          />
          <TagPicker label="Интересы" presets={INTEREST_OPTIONS} value={form.interests} onChange={(v) => set("interests", v)} max={20} maxLength={60} customLabel="Свой интерес" error={errors.interests} />
          <TagPicker label="Языки общения" presets={LANGUAGE_OPTIONS} value={form.languages} onChange={(v) => set("languages", v)} max={10} allowCustom={false} error={errors.languages} />
        </section>

        <fieldset className="acc-private" aria-describedby="private-note">
          <legend>
            <Icon name="lock" size={15} /> Закрытые данные — видны только вам
          </legend>
          <p id="private-note" className="gv-ac-muted">
            Не показываются в публичной анкете, каталогах и переписке. Нужны для связи по бронированиям и поздравлений
            (если вы их включили в настройках).
          </p>
          <div className="gv-form-grid">
            <TextInput label="Электронная почта" value={me.email} readOnly hint={me.emailVerified ? "Подтверждена" : "Не подтверждена — письмо можно отправить повторно в «Настройках»."} />
            <TextInput label="Телефон" type="tel" autoComplete="tel" value={form.phone} maxLength={32} placeholder="+7 900 000-00-00" onChange={(e) => set("phone", e.target.value)} error={errors.phone} />
            <TextInput label="Дата рождения" type="date" max={todayIso()} value={form.birth_date} onChange={(e) => set("birth_date", e.target.value)} error={errors.birth_date} hint="Дата не раскрывается: в GG Surfer можно показать только возраст." />
          </div>
          <Textarea label="Контакты для исполнителей" value={form.private_contacts} maxLength={2000} rows={2} placeholder="Например, телеграм для связи по броням" onChange={(e) => set("private_contacts", e.target.value)} error={errors.private_contacts} />
        </fieldset>

        {errors._form && (
          <p className="gv-form-error" role="alert">
            {errors._form}
          </p>
        )}

        <div className="gv-sticky-actions acc-form-actions">
          {pub.href ? (
            <ButtonLink href={pub.href} variant="soft" icon="external" target="_blank" rel="noopener">
              Посмотреть на сайте
            </ButtonLink>
          ) : (
            <span className="acc-hint-inline" title={pub.reason}>
              <Icon name="info" size={14} /> {pub.reason}
            </span>
          )}
          <ButtonLink href={routes.account.specialties} variant="soft" iconRight="arrow">
            Управление направлениями
          </ButtonLink>
          {dirty && (
            <Button variant="soft" onClick={() => setForm(baseline)} disabled={saving}>
              Отменить изменения
            </Button>
          )}
          <Button type="submit" variant="primary" loading={saving} disabled={!dirty}>
            {saveLabel}
          </Button>
        </div>
      </form>
    </>
  );
}
