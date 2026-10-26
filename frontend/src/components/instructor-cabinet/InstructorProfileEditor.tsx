"use client";
/**
 * Instructor card editor (INS-01/02/12, ACC-15, F03, ATX-04): publication panel with the checklist of missing
 * fields (server `publish_check` / 400 publish_requirements), gallery manager, the card form with a sticky save
 * bar (ATX-22) and a live «Как это видит клиент» preview. Name and photo come from the common profile (ACC-07).
 */
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { ik, instructorApi, type InstructorOwn } from "@/lib/api/instructorCabinet";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import { useMe } from "@/lib/auth/hooks";
import { apiFieldErrors, validate } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";
import { routes } from "@/lib/routes";
import { StatusBadge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { CertificateBadge } from "@/components/ui/CertificateBadge";
import { ChipGroup } from "@/components/ui/Chip";
import { Select, TextInput, Textarea } from "@/components/ui/Field";
import { IconButton } from "@/components/ui/IconButton";
import { QueryState } from "@/components/ui/QueryState";
import { LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { CURRENCY_OPTIONS, LANGUAGE_OPTIONS, LESSON_FORMAT_OPTIONS, LEVEL_OPTIONS } from "@/components/learning-cabinet/dictionaries";
import { FormAlert } from "@/components/learning-cabinet/FormAlert";
import { useBoardTypes, useRegions, useSpots } from "@/components/learning-cabinet/hooks";
import { InstructorCardPreview } from "./InstructorCardPreview";
import { InstructorMediaManager } from "./InstructorMediaManager";
import { useInstructorProfile } from "./hooks";
import { instructorPaths } from "./paths";
import {
  checklistItems,
  experienceYears,
  FIELD_ALIASES,
  formToInput,
  isSameForm,
  MAX_FUN_FACTS,
  profileSchema,
  profileToForm,
  type ChecklistItem,
  type ProfileErrors,
  type ProfileForm,
} from "./profileForm";

function Checklist({ items, title }: { items: ChecklistItem[]; title: string }) {
  if (!items.length) return null;
  return (
    <FormAlert tone="warn" title={title}>
      <ul className="lc-checklist">
        {items.map((i) => (
          <li key={i.key}>
            {i.href ? (
              <Link href={i.href}>{i.label}</Link>
            ) : i.field ? (
              <a href={`#ins-field-${i.field}`}>{i.label}</a>
            ) : (
              i.label
            )}
            {i.message && i.message !== i.label ? <small> — {i.message}</small> : null}
          </li>
        ))}
      </ul>
    </FormAlert>
  );
}

function PublishPanel({ profile, dirty }: { profile: InstructorOwn; dirty: boolean }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<"publish" | "unpublish" | null>(null);
  const [serverMissing, setServerMissing] = useState<ChecklistItem[]>([]);
  const missing = checklistItems(profile.publish_check?.missing);
  const published = profile.status === "published";

  const run = async (action: "publish" | "unpublish") => {
    setPending(action);
    setServerMissing([]);
    try {
      const updated = action === "publish" ? await instructorApi.publish() : await instructorApi.unpublish();
      queryClient.setQueryData(ik.profile, updated);
      void queryClient.invalidateQueries({ queryKey: qk.me });
      toast.success(action === "publish" ? "Карточка опубликована — её видно в каталоге" : "Карточка снята с публикации");
    } catch (err) {
      if (isApiError(err) && Object.keys(err.fields).length) setServerMissing(checklistItems(err.fields));
      toast.error(err);
    } finally {
      setPending(null);
    }
  };

  return (
    <section className="gv-ac-card lc-publish" aria-labelledby="ins-publish-title">
      <div className="lc-publish-row">
        <div className="lc-publish-main">
          <h3 id="ins-publish-title">Публикация карточки</h3>
          <div className="lc-session-tags">
            <StatusBadge domain="publication" status={profile.status} />
            <CertificateBadge status={profile.certificate_status} audience="owner" />
          </div>
          <small>
            {published
              ? `Опубликована ${profile.published_at ? formatDateTime(profile.published_at) : ""} — карточку видят в каталоге инструкторов.`
              : profile.status === "hidden"
                ? "Карточка скрыта модератором. Обратитесь в поддержку."
                : "Черновик: карточку видите только вы."}
          </small>
        </div>
        <div className="gv-card-head-actions">
          {published ? (
            <Button variant="soft" onClick={() => void run("unpublish")} loading={pending === "unpublish"}>
              Снять с публикации
            </Button>
          ) : (
            <Button variant="primary" onClick={() => void run("publish")} loading={pending === "publish"} disabled={dirty || profile.status === "hidden"} title={dirty ? "Сначала сохраните изменения" : undefined}>
              Опубликовать
            </Button>
          )}
          {published && profile.handle && (
            <ButtonLink href={routes.instructor(profile.handle)} variant="soft" iconRight="external">
              Посмотреть на сайте
            </ButtonLink>
          )}
        </div>
      </div>
      {dirty && !published && <p className="lc-muted">Есть несохранённые изменения — сохраните карточку перед публикацией.</p>}
      {serverMissing.length ? (
        <Checklist items={serverMissing} title="Сервер не опубликовал карточку — заполните:" />
      ) : !published ? (
        <Checklist items={missing} title="Для публикации заполните:" />
      ) : null}
      <p className="lc-footnote">
        Сертификат для публикации не нужен — его можно загрузить позже в разделе <Link href={instructorPaths.certificates}>«Сертификаты»</Link>.
      </p>
    </section>
  );
}

function FunFacts({ value, onChange, error }: { value: string[]; onChange: (v: string[]) => void; error?: string }) {
  return (
    <fieldset className="gv-fieldset lc-facts" id="ins-field-fun_facts">
      <legend className="gv-field-label">Забавные факты (до {MAX_FUN_FACTS})</legend>
      {value.map((fact, i) => (
        <div key={i} className="lc-fact-row">
          <TextInput
            label={`Факт ${i + 1}`}
            hideLabel
            value={fact}
            maxLength={200}
            placeholder={i === 0 ? "Например: катаюсь круглый год, даже в −10 °C" : "Ещё один факт"}
            onChange={(e) => onChange(value.map((x, j) => (j === i ? e.target.value : x)))}
          />
          <IconButton icon="close" shape="round" iconSize={16} label={`Удалить факт ${i + 1}`} onClick={() => onChange(value.length > 1 ? value.filter((_, j) => j !== i) : [""])} />
        </div>
      ))}
      {value.length < MAX_FUN_FACTS && (
        <Button variant="link" size="sm" icon="plus" onClick={() => onChange([...value, ""])}>
          Добавить факт
        </Button>
      )}
      {error && <p className="gv-field-error">{error}</p>}
    </fieldset>
  );
}

function Editor({ profile }: { profile: InstructorOwn | null }) {
  const { me } = useMe();
  const toast = useToast();
  const queryClient = useQueryClient();
  const regions = useRegions();
  const spots = useSpots();
  const boardTypes = useBoardTypes();
  const initial = useMemo(() => profileToForm(profile, { regionSlug: me?.region?.slug ?? null }), [profile, me?.region?.slug]);
  const [form, setForm] = useState<ProfileForm>(initial);
  const [errors, setErrors] = useState<ProfileErrors>({});
  const [saving, setSaving] = useState(false);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const dirty = !isSameForm(form, initial) || !profile;

  useEffect(() => setForm(initial), [initial]);

  // warn before leaving with unsaved changes
  useEffect(() => {
    if (!dirty || !profile) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [dirty, profile]);

  const set = <K extends keyof ProfileForm>(key: K, value: ProfileForm[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    if (errors[key]) setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const regionOptions = (regions.data ?? []).map((r) => ({ value: r.slug, label: r.name }));
  const spotOptions = (spots.data ?? [])
    .filter((s) => !form.regions.length || (s.region && form.regions.includes(s.region.slug)) || form.spots.includes(s.slug))
    .map((s) => ({ value: s.slug, label: s.name }));
  const boardOptions = (boardTypes.data ?? []).filter((b) => !b.is_custom).map((b) => ({ value: b.code, label: b.name }));

  const save = async () => {
    const v = validate(profileSchema, form);
    if (v.errors) {
      setErrors(v.errors as ProfileErrors);
      toast.error("Проверьте поля формы");
      return;
    }
    setSaving(true);
    setErrors({});
    setChecklist([]);
    try {
      const updated = await instructorApi.save(formToInput(form), !profile);
      queryClient.setQueryData(ik.profile, updated);
      void queryClient.invalidateQueries({ queryKey: qk.me });
      toast.success(profile ? "Карточка сохранена" : "Карточка создана — осталось опубликовать");
    } catch (err) {
      if (isApiError(err) && err.code === "publish_requirements") {
        setChecklist(checklistItems(err.fields));
      } else {
        setErrors(apiFieldErrors(err, FIELD_ALIASES) as ProfileErrors);
      }
      toast.error(err, { action: { label: "Повторить", onClick: () => void save() } });
    } finally {
      setSaving(false);
    }
  };

  const regionNames = form.regions.map((slug) => regions.data?.find((r) => r.slug === slug)?.name).filter((x): x is string => Boolean(x));
  const spotNames = form.spots.map((slug) => spots.data?.find((s) => s.slug === slug)?.name ?? profile?.spots.find((s) => s.slug === slug)?.name).filter((x): x is string => Boolean(x));
  const boardNames = form.board_types.map((code) => boardTypes.data?.find((b) => b.code === code)?.name).filter((x): x is string => Boolean(x));
  const photo = profile?.media.find((m) => m.media.kind === "image")?.media ?? profile?.avatar ?? me?.avatar ?? null;
  const name = profile?.display_name || me?.displayName || "Инструктор";
  const years = experienceYears(form);

  return (
    <div className="lc-editor">
      {profile ? (
        <PublishPanel profile={profile} dirty={dirty} />
      ) : (
        <FormAlert tone="info" title="Карточка ещё не создана">
          Заполните поля и сохраните — карточка появится как черновик. Опубликовать можно, когда будут заполнены регион, формат, цена и описание. Сертификат не обязателен.
        </FormAlert>
      )}
      {profile && <InstructorMediaManager items={profile.media} />}
      <div className="lc-editor-grid">
        <form
          className="lc-editor-form"
          aria-labelledby="ins-form-title"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <h3 id="ins-form-title" className="lc-section-title">
            Карточка инструктора
          </h3>
          <p className="gv-ac-note">
            Имя, фамилия и фото берутся из <Link href={routes.account.profile}>общего профиля</Link> — сейчас: <b>{name}</b>.
          </p>
          <div id="ins-field-headline">
            <TextInput label="Коротко о себе" value={form.headline} onChange={(e) => set("headline", e.target.value)} maxLength={200} error={errors.headline} placeholder="Инструктор по сёрфингу на Камчатке, учу с нуля" hint="Первая строка карточки в каталоге" />
          </div>
          <Textarea label="О себе — с душой" value={form.about} onChange={(e) => set("about", e.target.value)} maxLength={4000} rows={5} error={errors.about} placeholder="Как проходят занятия, кого учите, что важно знать перед первым уроком" />
          <FunFacts value={form.fun_facts} onChange={(v) => set("fun_facts", v)} error={errors.fun_facts} />

          <h4 className="lc-subtitle">Где проходят занятия</h4>
          <div id="ins-field-regions">
            {regions.isPending ? <LoadingState variant="inline" label="Загружаем регионы…" /> : <ChipGroup label="Регионы *" options={regionOptions} value={form.regions} onChange={(v) => set("regions", v)} />}
            {errors.regions && <p className="gv-field-error" role="alert">{errors.regions}</p>}
          </div>
          <div id="ins-field-spots">
            {spots.isPending ? (
              <LoadingState variant="inline" label="Загружаем споты…" />
            ) : spotOptions.length ? (
              <ChipGroup label="Споты" options={spotOptions} value={form.spots} onChange={(v) => set("spots", v)} />
            ) : (
              <p className="gv-field-hint">В выбранных регионах пока нет спотов в каталоге — добавьте их позже или опишите места в «О себе».</p>
            )}
            {errors.spots && <p className="gv-field-error" role="alert">{errors.spots}</p>}
          </div>

          <h4 className="lc-subtitle">Опыт и уровень</h4>
          <div className="gv-form-grid">
            <TextInput label="Катаюсь с (год)" inputMode="numeric" value={form.surfing_since} onChange={(e) => set("surfing_since", e.target.value.replace(/\D/g, "").slice(0, 4))} error={errors.surfing_since} placeholder="2016" />
            <TextInput
              label="Преподаю с (год)"
              inputMode="numeric"
              value={form.teaching_since}
              onChange={(e) => set("teaching_since", e.target.value.replace(/\D/g, "").slice(0, 4))}
              error={errors.teaching_since}
              placeholder="2019"
              hint={years !== null ? `Опыт в карточке: ${years} лет` : undefined}
            />
            <Select label="Мой уровень катания" placeholder="Не указан" value={form.riding_level} onChange={(e) => set("riding_level", e.target.value)} options={LEVEL_OPTIONS} />
          </div>

          <h4 className="lc-subtitle">Занятия</h4>
          <div id="ins-field-formats">
            <ChipGroup label="Форматы *" options={LESSON_FORMAT_OPTIONS} value={form.formats} onChange={(v) => set("formats", v)} />
            {errors.formats && <p className="gv-field-error" role="alert">{errors.formats}</p>}
          </div>
          <ChipGroup label="Уровни учеников" options={LEVEL_OPTIONS} value={form.student_levels} onChange={(v) => set("student_levels", v)} />
          {boardTypes.isPending ? <LoadingState variant="inline" label="Загружаем типы досок…" /> : <ChipGroup label="Доски на занятиях" options={boardOptions} value={form.board_types} onChange={(v) => set("board_types", v)} />}
          <ChipGroup label="Языки занятий" options={LANGUAGE_OPTIONS} value={form.languages} onChange={(v) => set("languages", v)} />
          <div className="gv-form-grid" id="ins-field-price_from">
            <TextInput label="Цена «от»" inputMode="decimal" value={form.price_from} onChange={(e) => set("price_from", e.target.value)} error={errors.price_from} placeholder="3500" hint="Или добавьте активное предложение с ценой" />
            <Select label="Валюта" value={form.currency} onChange={(e) => set("currency", e.target.value)} options={CURRENCY_OPTIONS} />
          </div>
          <TextInput label="Как с вами договориться" value={form.contact_note} onChange={(e) => set("contact_note", e.target.value)} maxLength={300} error={errors.contact_note} placeholder="Пишите в чат на сайте — отвечаю в течение дня" hint="Контакты не публикуются — ученики пишут через сообщения ГДеволны" />

          {errors._form && <FormAlert>{errors._form}</FormAlert>}
          {checklist.length > 0 && <Checklist items={checklist} title="Опубликованная карточка должна оставаться заполненной:" />}
          <div className="gv-sticky-actions lc-save-bar">
            <span className="lc-muted" aria-live="polite">
              {dirty ? (profile ? "Есть несохранённые изменения" : "Карточка ещё не сохранена") : "Все изменения сохранены"}
            </span>
            <Button type="button" variant="soft" onClick={() => setForm(initial)} disabled={!dirty || saving || !profile}>
              Отменить
            </Button>
            <Button type="submit" variant="primary" loading={saving}>
              {profile ? "Сохранить карточку" : "Создать карточку"}
            </Button>
          </div>
        </form>
        <InstructorCardPreview
          form={form}
          name={name}
          photo={photo}
          regionNames={regionNames}
          spotNames={spotNames}
          boardNames={boardNames}
          certificate={profile?.certificate_status ?? "none"}
          ratingAvg={profile?.rating_avg ?? 0}
          ratingCount={profile?.rating_count ?? 0}
          effectivePrice={profile?.effective_price_from ?? null}
        />
      </div>
    </div>
  );
}

export function InstructorProfileEditor() {
  const query = useInstructorProfile();
  return (
    <QueryState query={query} loading={<LoadingState variant="skeleton" lines={8} label="Загружаем карточку…" />}>
      {(profile) => <Editor profile={profile} />}
    </QueryState>
  );
}
