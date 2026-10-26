"use client";
/**
 * Workshop registration / edit form (SHP-01…05, SHO-09, TZ 21.1): one form for both — the CTA reads
 * «Зарегистрироваться как шейпер» only until the workshop exists (`created` from PUT me/workshop), then
 * «Сохранить изменения». The shaper code (SKU prefix) is sent only when the user changes it, so saving the
 * profile never drops it (CABINET_NOTES, prototype bug #1). Custom board types and materials (SHP-05) and
 * publication live here too.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import { isApiError } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import { shaperApi, shaperKeys, type Workshop } from "@/lib/api/shaper";
import { cx } from "@/lib/cx";
import { Button } from "@/components/ui/Button";
import { ChipGroup } from "@/components/ui/Chip";
import { Select, Textarea, TextInput } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { MediaUploader } from "@/components/ui/MediaUploader";
import { useToast } from "@/components/ui/Toast";
import { ToggleRow } from "@/components/ui/Toggle";
import { CustomTypesManager, MaterialsManager } from "./CatalogManagers";
import { validateWorkshop, workshopDraft, workshopFieldErrors, workshopInput, type WorkshopDraft, type WorkshopField } from "./draft";
import { RoundPhotoField } from "./RoundPhotoField";
import { WorkshopPublishBox } from "./WorkshopPublishBox";
import { shaperRoutes } from "./routes";

export const SERVICE_OPTIONS = [
  "Готовые доски",
  "Индивидуальные заказы",
  "Шейпинг по размерам клиента",
  "Покраска и аэрография",
  "Подбор доски",
  "Обучение шейпингу",
];

export const LEAD_TIME_OPTIONS = ["До 2 недель", "2–4 недели", "1–2 месяца", "2–3 месяца", "По договорённости"];

function Section({ title, icon, children, className }: { title: string; icon: Parameters<typeof Icon>[0]["name"]; children: React.ReactNode; className?: string }) {
  return (
    <section className={cx("card", className)} aria-label={title}>
      <h3>
        <Icon name={icon} className="ic" size={19} />
        {title}
      </h3>
      {children}
    </section>
  );
}

export function WorkshopForm({ workshop, organization }: { workshop: Workshop | null; organization?: string | null }) {
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const creating = !workshop;
  const readOnly = Boolean(workshop && !workshop.can_manage);
  const [draft, setDraft] = useState<WorkshopDraft>(() => workshopDraft(workshop));
  const [errors, setErrors] = useState<Partial<Record<WorkshopField | "_form", string>>>({});
  const [customService, setCustomService] = useState("");
  const regions = useQuery({ queryKey: shaperKeys.regions, queryFn: shaperApi.regions, staleTime: 3_600_000 });

  const set = <K extends WorkshopField>(key: K, value: WorkshopDraft[K]) => {
    setDraft((d) => ({ ...d, [key]: value }));
    setErrors((e) => (e[key] || e._form ? { ...e, [key]: undefined, _form: undefined } : e));
  };

  const payload = useMemo(() => workshopInput(draft, workshop), [draft, workshop]);
  const dirty = creating || Object.keys(payload).length > 0;

  const save = useMutation({
    mutationFn: () => shaperApi.saveWorkshop(payload, organization),
    onSuccess: (saved) => {
      qc.setQueryData(shaperKeys.workshop(organization), saved);
      void qc.invalidateQueries({ queryKey: shaperKeys.all });
      setErrors({});
      if (saved.created || creating) {
        void qc.invalidateQueries({ queryKey: qk.me });
        toast.success("Мастерская зарегистрирована — кабинет шейпера готов");
        router.push(shaperRoutes.panel(organization));
        return;
      }
      setDraft(workshopDraft(saved));
      toast.success("Изменения сохранены");
    },
    onError: (err) => {
      if (isApiError(err) && Object.keys(err.fields).length) {
        setErrors({ ...workshopFieldErrors(err.fields), _form: err.message });
      } else {
        setErrors({ _form: isApiError(err) ? err.message : "Не удалось сохранить. Попробуйте ещё раз." });
      }
      toast.error(err, isApiError(err) && err.retryable ? { action: { label: "Повторить", onClick: () => save.mutate() } } : undefined);
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const problems = validateWorkshop(draft);
    if (Object.keys(problems).length) {
      setErrors({ ...problems, _form: "Проверьте отмеченные поля." });
      const first = Object.keys(problems)[0];
      document.getElementById(`ws-${first}`)?.focus();
      return;
    }
    if (!dirty) {
      toast.info("Изменений нет — всё уже сохранено");
      return;
    }
    save.mutate();
  };

  const regionOptions = (regions.data ?? []).map((r) => ({ value: String(r.id), label: r.name }));
  if (draft.region_id && !regionOptions.some((o) => o.value === draft.region_id) && workshop?.region) {
    regionOptions.unshift({ value: String(workshop.region.id), label: workshop.region.name });
  }
  const serviceOptions = [...SERVICE_OPTIONS, ...draft.services.filter((s) => !SERVICE_OPTIONS.includes(s))].map((s) => ({ value: s, label: s }));
  const leadOptions = [...LEAD_TIME_OPTIONS, ...(draft.lead_time && !LEAD_TIME_OPTIONS.includes(draft.lead_time) ? [draft.lead_time] : [])].map((v) => ({ value: v, label: v }));
  const codeLocked = Boolean(workshop && workshop.models_count > 0);

  return (
    <form className="gv-sc-workshop-form" onSubmit={submit} noValidate aria-label={creating ? "Регистрация мастерской" : "Профиль мастерской"}>
      {creating ? (
        <div className="gv-ac-note gv-sc-intro">
          <Icon name="ruler" size={16} /> Заполните профиль мастерской — после регистрации откроются «Мои доски», артикулы и
          статистика. Это то же направление «Шейпер» вашего аккаунта, повторно регистрироваться не нужно.
        </div>
      ) : null}
      {readOnly && (
        <div className="gv-ac-note" role="note">
          <Icon name="lock" size={14} /> Изменять профиль мастерской могут владелец и менеджер. Вы видите его в режиме просмотра.
        </div>
      )}
      <fieldset className="gv-sc-fieldset" disabled={readOnly || save.isPending}>
        <legend className="sr-only">{creating ? "Регистрация мастерской" : "Профиль мастерской"}</legend>
        <div className="form-grid">
          <div className="form-column">
            <Section title="Основная информация" icon="monitor">
              <div className="gv-sc-identity-row">
                <RoundPhotoField value={draft.logo} onChange={(m) => set("logo", m)} name={draft.name} disabled={readOnly} />
              </div>
              <div className="gv-sc-fields">
                <TextInput
                  id="ws-name"
                  label="Название мастерской"
                  required
                  maxLength={90}
                  placeholder="Например, Kamchatka Boards"
                  value={draft.name}
                  onChange={(e) => set("name", e.target.value)}
                  error={errors.name}
                />
                <TextInput
                  id="ws-shaper_code"
                  label="Код шейпера (начало артикула)"
                  maxLength={6}
                  placeholder={creating ? "Подберём автоматически" : undefined}
                  value={draft.shaper_code}
                  onChange={(e) => set("shaper_code", e.target.value.toUpperCase())}
                  error={errors.shaper_code}
                  readOnly={codeLocked}
                  hint={
                    codeLocked
                      ? "Код закреплён за артикулами ваших досок (GV-" + (draft.shaper_code || "КОД") + "-…) и не меняется при сохранении профиля."
                      : "2–6 латинских букв или цифр. Входит во все артикулы: GV-" + (draft.shaper_code || "КОД") + "-FSH-5P10-W2050-001."
                  }
                />
                <div className="form-row">
                  <Select
                    id="ws-region_id"
                    label="Регион"
                    placeholder={regions.isPending ? "Загружаем регионы…" : "Выберите регион"}
                    options={regionOptions}
                    value={draft.region_id}
                    onChange={(e) => set("region_id", e.target.value)}
                    error={errors.region_id ?? (regions.isError ? "Не удалось загрузить регионы — обновите страницу." : undefined)}
                    hint="Нужен для публикации"
                  />
                  <TextInput id="ws-city" label="Город" maxLength={120} value={draft.city} onChange={(e) => set("city", e.target.value)} error={errors.city} />
                </div>
                <TextInput
                  id="ws-specialization"
                  label="Специализация"
                  maxLength={300}
                  placeholder="Например, шортборды и фиши для холодной воды"
                  value={draft.specialization}
                  onChange={(e) => set("specialization", e.target.value)}
                  error={errors.specialization}
                  hint="Нужна для публикации · видна в карточке шейпера"
                />
                <TextInput
                  id="ws-experience_since"
                  label="В шейпинге с (год)"
                  inputMode="numeric"
                  maxLength={4}
                  placeholder="2015"
                  value={draft.experience_since}
                  onChange={(e) => set("experience_since", e.target.value.replace(/\D/g, ""))}
                  error={errors.experience_since}
                  className="gv-sc-half"
                />
                <Textarea
                  id="ws-short_description"
                  label="Коротко о мастерской"
                  maxLength={300}
                  rows={2}
                  value={draft.short_description}
                  onChange={(e) => set("short_description", e.target.value)}
                  error={errors.short_description}
                  hint="Одна-две фразы для карточки в каталоге"
                />
                <Textarea
                  id="ws-description"
                  label="О мастерской и философии"
                  maxLength={5000}
                  rows={5}
                  placeholder="Расскажите о себе, мастерской и подходе к созданию досок…"
                  value={draft.description}
                  onChange={(e) => set("description", e.target.value)}
                  error={errors.description}
                />
              </div>
            </Section>
            <Section title="Типы досок" icon="board">
              {workshop ? (
                <CustomTypesManager workshopId={workshop.id} disabled={readOnly} />
              ) : (
                <p className="form-help">
                  Стандартные типы (шортборд, фиш, ган, лонгборд, SUP…) доступны сразу. Свои типы — например, «Мини-малибу» —
                  можно добавить после регистрации: они сразу появятся в форме каждой модели.
                </p>
              )}
            </Section>
          </div>
          <div className="form-column">
            <Section title="Услуги и сроки" icon="truck">
              <ChipGroup
                label="Услуги"
                options={serviceOptions}
                value={draft.services}
                onChange={(v) => set("services", v)}
              />
              <div className="gv-sc-inline-form gv-sc-add-service">
                <TextInput
                  label="Своя услуга"
                  placeholder="Например, ремонт вмятин"
                  maxLength={80}
                  value={customService}
                  onChange={(e) => setCustomService(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      const v = customService.trim();
                      if (v && !draft.services.includes(v)) set("services", [...draft.services, v]);
                      setCustomService("");
                    }
                  }}
                />
                <Button
                  variant="soft"
                  icon="plus"
                  disabled={!customService.trim() || draft.services.length >= 20}
                  onClick={() => {
                    const v = customService.trim();
                    if (v && !draft.services.includes(v)) set("services", [...draft.services, v]);
                    setCustomService("");
                  }}
                >
                  Добавить
                </Button>
              </div>
              {errors.services && (
                <p className="gv-field-error" role="alert">
                  {errors.services}
                </p>
              )}
              <Select
                id="ws-lead_time"
                label="Срок изготовления"
                placeholder="Выберите срок"
                options={leadOptions}
                value={draft.lead_time}
                onChange={(e) => set("lead_time", e.target.value)}
                error={errors.lead_time}
              />
              <ToggleRow
                title="Делаю ремонт"
                description="Принимаю доски на ремонт и восстановление — признак виден в каталоге и в фильтре «Ремонт»"
                checked={draft.does_repair}
                onChange={(v) => set("does_repair", v)}
                disabled={readOnly}
              />
              {draft.does_repair && (
                <Textarea
                  id="ws-repair_note"
                  label="Что ремонтируете"
                  maxLength={300}
                  rows={2}
                  placeholder="Например, вмятины, трещины, замена плавниковых боксов"
                  value={draft.repair_note}
                  onChange={(e) => set("repair_note", e.target.value)}
                  error={errors.repair_note}
                />
              )}
            </Section>
            <Section title="Материалы" icon="box">
              {workshop ? (
                <MaterialsManager workshopId={workshop.id} disabled={readOnly} />
              ) : (
                <p className="form-help">Стандартные материалы доступны сразу, свои можно добавить после регистрации.</p>
              )}
            </Section>
            <Section title="Обложка и промо-видео" icon="photo">
              <MediaUploader
                purpose="org_cover"
                maxFiles={1}
                label="Обложка мастерской"
                hint="JPG, PNG или WebP до 15 МБ · одно фото для шапки профиля"
                value={draft.cover ? [draft.cover] : []}
                onChange={(items) => set("cover", items[0] ?? null)}
                video={{
                  purpose: "promo_video",
                  label: "Промо-видео (один ролик о вас и мастерской)",
                  value: draft.promo_video,
                  onChange: (m) => set("promo_video", m),
                }}
                disabled={readOnly}
              />
              {(errors.cover || errors.promo_video) && (
                <p className="gv-field-error" role="alert">
                  {errors.cover ?? errors.promo_video}
                </p>
              )}
            </Section>
          </div>
        </div>
        <div className="reg-bottom">
          <Section title="Контакты и соцсети" icon="link">
            <div className="gv-sc-contacts">
              <TextInput id="ws-phone" label="Телефон" type="tel" maxLength={32} placeholder="+7 900 000 00 00" value={draft.phone} onChange={(e) => set("phone", e.target.value)} error={errors.phone} />
              <TextInput id="ws-email" label="Email" type="email" maxLength={254} placeholder="workshop@example.ru" value={draft.email} onChange={(e) => set("email", e.target.value)} error={errors.email} />
              <TextInput id="ws-address" label="Адрес мастерской" maxLength={300} value={draft.address} onChange={(e) => set("address", e.target.value)} error={errors.address} />
              <TextInput id="ws-website" label="Сайт" type="url" placeholder="https://" maxLength={200} value={draft.website} onChange={(e) => set("website", e.target.value)} error={errors.website} />
              <TextInput id="ws-telegram" label="Telegram" placeholder="@мастерская" maxLength={300} value={draft.telegram} onChange={(e) => set("telegram", e.target.value)} error={errors.telegram} />
              <TextInput id="ws-vk" label="VK" placeholder="vk.com/…" maxLength={300} value={draft.vk} onChange={(e) => set("vk", e.target.value)} />
              <TextInput id="ws-youtube" label="Видео-канал" placeholder="Ссылка на канал" maxLength={300} value={draft.youtube} onChange={(e) => set("youtube", e.target.value)} />
            </div>
            <p className="form-help">Телефон и email не показываются в публичном профиле — клиенты пишут вам через обращения.</p>
          </Section>
          {workshop ? (
            <WorkshopPublishBox workshop={workshop} organization={organization} dirty={dirty} />
          ) : (
            <Section title="Публикация" icon="sparkle">
              <p className="form-help">
                После регистрации мастерская сохранится как черновик. Опубликуйте её, когда заполните регион и специализацию —
                тогда она появится в каталоге «По шейперам».
              </p>
            </Section>
          )}
        </div>
      </fieldset>
      {errors._form && (
        <p className="gv-sc-form-error" role="alert">
          <Icon name="alert" size={15} /> {errors._form}
        </p>
      )}
      {!readOnly && (
        <div className="gv-sticky-actions gv-sc-sticky">
          {!creating && dirty && <span className="gv-sc-dirty">Есть несохранённые изменения</span>}
          <Button type="submit" variant="primary" loading={save.isPending} className="gv-sc-cta">
            {creating ? "Зарегистрироваться как шейпер" : "Сохранить изменения"}
          </Button>
        </div>
      )}
    </form>
  );
}
