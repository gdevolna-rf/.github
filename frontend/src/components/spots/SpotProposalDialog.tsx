"use client";
/**
 * «Предложить правку» (SPT-07/08, TZ 8.1, PUBLIC_SCREENS §4.6): typed fields from GET spots/dictionaries, wind and
 * swell direction pickers with a live rose, months, hazards, infrastructure rows with distances, source, evidence
 * photos (MediaUploader purpose spot_evidence) and a comment; live «было → предлагается» preview. The published
 * card changes only after moderation; after sending the dialog shows the proposal status.
 */
import { useId, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  ButtonLink,
  ChipGroup,
  CompassRose,
  Icon,
  MediaImage,
  MediaUploader,
  Modal,
  Select,
  StatusBadge,
  TextInput,
  Textarea,
  useToast,
} from "@/components/ui";
import { isApiError } from "@/lib/api/errors";
import {
  spotKeys,
  spotsApi,
  type EditableSpotField,
  type InfrastructureInput,
  type Proposal,
  type SpotDetail,
  type SpotDictionaries,
} from "@/lib/api/spots";
import type { Media } from "@/lib/api/types";
import { cx } from "@/lib/cx";
import { apiFieldErrors, type FormErrors } from "@/lib/forms";
import { COMPASS, COMPASS_POINTS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { buildChanges, currentValue, displayValue, initialDraft, normalize, type Draft, type DraftValue } from "./proposalDiff";

const ALL_FIELDS: EditableSpotField[] = [
  "difficulty",
  "break_type",
  "bottom_type",
  "wave_character",
  "wave_power",
  "best_tide",
  "best_wind_directions",
  "best_swell_directions",
  "season",
  "best_months",
  "water_temp_note",
  "seasonal_warning",
  "short_description",
  "description",
  "typical_conditions",
  "hazards",
  "hazard_notes",
  "entry_exit",
  "access",
  "infrastructure",
];

const FALLBACK_LABELS: Record<EditableSpotField, string> = {
  short_description: "Краткое описание",
  description: "Описание",
  difficulty: "Уровень сложности",
  bottom_type: "Дно",
  break_type: "Тип брейка",
  wave_character: "Характер волн",
  wave_power: "Мощность волн",
  season: "Сезон",
  best_months: "Лучшие месяцы",
  best_wind_directions: "Подходящий ветер",
  best_swell_directions: "Подходящий свелл",
  best_tide: "Прилив",
  typical_conditions: "Типичные условия",
  hazards: "Опасности",
  hazard_notes: "Особенности безопасности",
  entry_exit: "Вход и выход из воды",
  access: "Как добраться / ограничения доступа",
  infrastructure: "Инфраструктура",
  water_temp_note: "Температура воды",
  seasonal_warning: "Сезонное предупреждение",
};

const TEXT_LIMITS: Partial<Record<EditableSpotField, number>> = {
  short_description: 300,
  wave_character: 200,
  wave_power: 120,
  season: 120,
  best_tide: 120,
  water_temp_note: 200,
  seasonal_warning: 300,
};
const PLACEHOLDERS: Partial<Record<EditableSpotField, string>> = {
  short_description: "Что важно знать об этом месте?",
  wave_character: "Например: левая и правая, длинная",
  wave_power: "Например: мягкая у берега, мощная на рифе",
  best_tide: "Например: средний и высокий прилив",
  season: "Например: лето — осень",
  water_temp_note: "Например: 8–14 °C летом, нужен гидрокостюм 4/3",
  seasonal_warning: "Например: в мае — нерест, вход закрыт",
  access: "Подъезд, тропа, парковка, проход к воде…",
  hazard_notes: "Течения, камни, холодная вода, зоны ограниченного доступа…",
  entry_exit: "Где удобно заходить и выходить из воды",
  typical_conditions: "Какой ветер и свелл обычно работают, когда лучше ехать",
};

export interface SpotProposalDialogProps {
  open: boolean;
  onClose: () => void;
  spot: SpotDetail;
  dictionaries?: SpotDictionaries | null;
}

export function SpotProposalDialog({ open, onClose, spot, dictionaries }: SpotProposalDialogProps) {
  const dictQuery = useQuery({
    queryKey: spotKeys.dictionaries,
    queryFn: spotsApi.dictionaries,
    enabled: open && !dictionaries,
    staleTime: 3_600_000,
    initialData: dictionaries ?? undefined,
  });
  if (!open) return null;
  return <ProposalForm onClose={onClose} spot={spot} dicts={dictQuery.data ?? null} dictsLoading={dictQuery.isPending && !dictionaries} />;
}

function ProposalForm({
  onClose,
  spot,
  dicts,
  dictsLoading,
}: {
  onClose: () => void;
  spot: SpotDetail;
  dicts: SpotDictionaries | null;
  dictsLoading: boolean;
}) {
  const formId = useId().replace(/:/g, "");
  const toast = useToast();
  const queryClient = useQueryClient();
  const fields = useMemo(() => {
    const allowed = dicts?.editable_fields?.map((f) => f.field);
    return allowed?.length ? ALL_FIELDS.filter((f) => allowed.includes(f)) : ALL_FIELDS;
  }, [dicts]);
  const labelOf = (f: EditableSpotField) => dicts?.editable_fields?.find((e) => e.field === f)?.label ?? FALLBACK_LABELS[f];
  const maxOf = (f: EditableSpotField) => dicts?.editable_fields?.find((e) => e.field === f)?.max_length ?? TEXT_LIMITS[f] ?? 5000;

  const [draft, setDraft] = useState<Draft>(() => initialDraft(spot, ALL_FIELDS));
  const [comment, setComment] = useState("");
  const [source, setSource] = useState("");
  const [evidence, setEvidence] = useState<Media[]>([]);
  const [errors, setErrors] = useState<FormErrors>({});
  const [result, setResult] = useState<Proposal | null>(null);

  const set = (field: EditableSpotField, value: DraftValue) => setDraft((d) => ({ ...d, [field]: value }));
  const changes = useMemo(() => buildChanges(spot, draft, dicts ?? undefined), [spot, draft, dicts]);
  const changed = Object.keys(changes) as EditableSpotField[];

  const aliases = useMemo(() => Object.fromEntries(ALL_FIELDS.map((f) => [`changes.${f}`, f])), []);
  const mutation = useMutation({
    mutationFn: () =>
      spotsApi.propose(spot.id, {
        changes,
        comment: comment.trim(),
        source: source.trim(),
        evidence_ids: evidence.map((m) => m.id),
      }),
    onSuccess: (proposal) => {
      setResult(proposal);
      toast.success("Предложение отправлено на модерацию");
      void queryClient.invalidateQueries({ queryKey: spotKeys.detail(spot.slug) });
      void queryClient.invalidateQueries({ queryKey: ["proposals"] });
    },
    onError: (err) => {
      const mapped = apiFieldErrors(err, { ...aliases, evidence_ids: "evidence" });
      if (isApiError(err) && (err.isConflict || err.isForbidden || err.code === "no_changes")) mapped._form = err.message;
      setErrors(mapped);
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!changed.length) {
      setErrors({ _form: "Измените хотя бы одно поле — комментарий без изменений модератор не сможет применить." });
      return;
    }
    const next: FormErrors = {};
    const infra = (draft.infrastructure as InfrastructureInput[] | undefined) ?? [];
    infra.forEach((row) => {
      if (row.distance_m !== null && (row.distance_m < 0 || row.distance_m > 100_000)) next.infrastructure = "Расстояние — от 0 до 100 000 м.";
      if ((row.name ?? "").length > 120) next.infrastructure = "Название объекта — до 120 символов.";
    });
    setErrors(next);
    if (Object.keys(next).length) return;
    mutation.mutate();
  };

  if (result) {
    return (
      <Modal
        open
        onClose={onClose}
        title="Спасибо за уточнение!"
        size="wide"
        footer={
          <>
            <ButtonLink href={routes.account.proposals} variant="pill" iconRight="arrow">
              Мои предложения
            </ButtonLink>
            <Button variant="primary" onClick={onClose} data-autofocus="">
              Готово
            </Button>
          </>
        }
      >
        <div className="gv-spot-proposal-done" role="status">
          <p>
            Предложение по споту <b>{spot.name}</b> отправлено модератору. Опубликованная карточка изменится только после
            проверки — о решении придёт уведомление.
          </p>
          <p className="gv-spot-proposal-status">
            Статус: <StatusBadge domain="proposal" status={result.status?.code ?? "submitted"} />
          </p>
          <DiffList
            items={(result.changes ?? []).map((c) => ({ field: c.field, label: c.label, old: c.old_display, next: c.new_display }))}
          />
        </div>
      </Modal>
    );
  }

  const diffItems = changed.map((f) => ({
    field: f,
    label: labelOf(f),
    old: displayValue(f, normalize(f, currentValue(spot, f), dicts ?? undefined), dicts),
    next: displayValue(f, changes[f] ?? null, dicts),
  }));

  const text = (f: EditableSpotField, opts: { multiline?: boolean; rows?: number } = {}) => {
    if (!fields.includes(f)) return null;
    const max = maxOf(f);
    const common = {
      label: labelOf(f),
      value: (draft[f] as string) ?? "",
      maxLength: max,
      placeholder: PLACEHOLDERS[f],
      error: errors[f],
    };
    return opts.multiline || max > 300 ? (
      <Textarea key={f} {...common} rows={opts.rows ?? 3} onChange={(e) => set(f, e.target.value)} />
    ) : (
      <TextInput key={f} {...common} onChange={(e) => set(f, e.target.value)} />
    );
  };

  const choice = (f: "difficulty" | "bottom_type" | "break_type") =>
    fields.includes(f) ? (
      <Select
        key={f}
        label={labelOf(f)}
        value={(draft[f] as string) ?? ""}
        onChange={(e) => set(f, e.target.value)}
        options={(dicts?.[f] ?? []).map((c) => ({ value: c.code, label: c.label }))}
        placeholder={draft[f] ? undefined : "Не указано"}
        error={errors[f]}
      />
    ) : null;

  return (
    <Modal
      open
      onClose={onClose}
      title="Уточним данные спота?"
      hideTitle
      size="xl"
      footer={
        <>
          <span className="gv-spot-proposal-count" aria-live="polite">
            {changed.length ? `Изменено полей: ${changed.length}` : "Пока нет изменений"}
          </span>
          <Button variant="pill" onClick={onClose}>
            Отмена
          </Button>
          <Button variant="primary" type="submit" form={formId} loading={mutation.isPending} disabled={!changed.length} iconRight="arrow">
            Отправить на модерацию
          </Button>
        </>
      }
    >
      <div className="gv-spot-edit-head">
        <MediaImage media={spot.cover} alt="" className="gv-spot-edit-thumb" prefer="thumb" />
        <div>
          <span className="gv-spot-overline">
            <Icon name="pencil" size={12} /> ПРЕДЛОЖИТЬ ПРАВКУ
          </span>
          <h2>Уточним данные спота?</h2>
          <p>
            <b>{spot.name}</b>
            {spot.region?.name ? ` · ${spot.region.name}` : ""}
          </p>
        </div>
      </div>
      <div className="gv-spot-explain">
        <span className="gv-spot-explain-ic" aria-hidden="true">
          <Icon name="check" size={14} />
        </span>
        <div>
          <strong>Вы помогаете сделать карту точнее</strong>
          <small>
            Измените только то, что знаете. Опубликованная карточка останется прежней, пока модератор не проверит
            предложение; источник и фото помогут принять решение быстрее.
          </small>
        </div>
      </div>

      {dictsLoading ? (
        <p className="gv-spot-muted" role="status">
          Загружаем справочники…
        </p>
      ) : null}

      <form id={formId} onSubmit={submit} noValidate className="gv-spot-proposal-form">
        {errors._form && (
          <div className="gv-form-error" role="alert">
            <Icon name="alert" size={18} />
            <span>{errors._form}</span>
          </div>
        )}

        <Section num="01" title="Волна и уровень" hint="Сложность, тип брейка, дно и характер волн">
          <div className="gv-form-grid">
            {choice("difficulty")}
            {choice("break_type")}
            {choice("bottom_type")}
            {text("wave_character")}
            {text("wave_power")}
            {text("best_tide")}
          </div>
        </Section>

        <Section num="02" title="Ветер и свелл" hint="Типично благоприятные направления — откуда дует ветер и приходит свелл. Это не прогноз.">
          {fields.includes("best_wind_directions") && (
            <CompassPicker
              kind="wind"
              label={labelOf("best_wind_directions")}
              value={(draft.best_wind_directions as string[]) ?? []}
              current={currentValue(spot, "best_wind_directions") as string[]}
              onChange={(v) => set("best_wind_directions", v)}
              error={errors.best_wind_directions}
            />
          )}
          {fields.includes("best_swell_directions") && (
            <CompassPicker
              kind="swell"
              label={labelOf("best_swell_directions")}
              value={(draft.best_swell_directions as string[]) ?? []}
              current={currentValue(spot, "best_swell_directions") as string[]}
              onChange={(v) => set("best_swell_directions", v)}
              error={errors.best_swell_directions}
            />
          )}
        </Section>

        <Section num="03" title="Сезон" hint="Когда ехать и что нужно знать о сезоне">
          <div className="gv-form-grid">
            {text("season")}
            {text("water_temp_note")}
          </div>
          {fields.includes("best_months") && (
            <ChipGroup
              label={labelOf("best_months")}
              value={(draft.best_months as string[]) ?? []}
              onChange={(v) => set("best_months", v)}
              options={(dicts?.months ?? []).map((m) => ({ value: String(m.code), label: m.label }))}
            />
          )}
          {errors.best_months && <p className="gv-field-error">{errors.best_months}</p>}
          {text("seasonal_warning")}
        </Section>

        <Section num="04" title="Описание, доступ и безопасность" hint="Полезные уточнения для тех, кто едет сюда впервые">
          {text("short_description", { multiline: true, rows: 2 })}
          {text("description", { rows: 4 })}
          {text("typical_conditions")}
          {fields.includes("hazards") && (
            <ChipGroup
              label={labelOf("hazards")}
              value={(draft.hazards as string[]) ?? []}
              onChange={(v) => set("hazards", v)}
              options={(dicts?.hazards ?? []).map((h) => ({ value: h.code, label: h.label }))}
            />
          )}
          {errors.hazards && <p className="gv-field-error">{errors.hazards}</p>}
          {text("hazard_notes")}
          {text("entry_exit")}
          {text("access")}
        </Section>

        {fields.includes("infrastructure") && (
          <Section num="05" title={labelOf("infrastructure")} hint="Парковка, душ, кафе, школы, прокат — с расстоянием от спота">
            <InfrastructureEditor
              value={(draft.infrastructure as InfrastructureInput[]) ?? []}
              onChange={(v) => set("infrastructure", v)}
              types={dicts?.infrastructure_types ?? []}
              error={errors.infrastructure}
            />
          </Section>
        )}

        <Section num="06" title="Источник и доказательства" hint="Необязательно, но поможет модератору проверить предложение">
          <TextInput
            label="Источник"
            placeholder="Например: был здесь в сентябре 2026, или ссылка на публикацию"
            maxLength={300}
            value={source}
            onChange={(e) => setSource(e.target.value)}
            error={errors.source}
          />
          <MediaUploader
            purpose="spot_evidence"
            value={evidence}
            onChange={setEvidence}
            maxFiles={10}
            label="Фото-доказательства"
            hint="До 10 фото: знаки, вход в воду, состояние берега. Модератор может добавить их в галерею спота."
          />
          {errors.evidence && <p className="gv-field-error">{errors.evidence}</p>}
          <Textarea
            label="Комментарий для модератора"
            rows={3}
            maxLength={2000}
            placeholder="Например: был здесь неделю назад — лучший ветер северо-восточный, а не западный…"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            error={errors.comment}
          />
        </Section>

        <section className="gv-spot-proposal-diff" aria-labelledby={`${formId}-diff`}>
          <h3 id={`${formId}-diff`}>Было → предлагается</h3>
          {diffItems.length ? (
            <DiffList items={diffItems} />
          ) : (
            <p className="gv-spot-muted">Измените поля выше — здесь появится сравнение с опубликованной карточкой.</p>
          )}
        </section>
      </form>
    </Modal>
  );
}

function Section({ num, title, hint, children }: { num: string; title: string; hint?: string; children: ReactNode }) {
  const id = useId().replace(/:/g, "");
  return (
    <fieldset className="gv-spot-proposal-section" aria-labelledby={id}>
      <div className="gv-spot-section-head">
        <span className="gv-spot-section-num" aria-hidden="true">
          {num}
        </span>
        <div>
          <h3 id={id}>{title}</h3>
          {hint && <small>{hint}</small>}
        </div>
      </div>
      {children}
    </fieldset>
  );
}

export function DiffList({ items }: { items: Array<{ field: string; label: string; old: string; next: string }> }) {
  return (
    <ul className="gv-spot-diff">
      {items.map((i) => (
        <li key={i.field}>
          <b>{i.label}</b>
          <span className="gv-spot-diff-old">
            <span className="sr-only">Было: </span>
            {i.old}
          </span>
          <Icon name="arrow" size={14} />
          <span className="gv-spot-diff-new">
            <span className="sr-only">Предлагается: </span>
            {i.next}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function CompassPicker({
  kind,
  label,
  value,
  current,
  onChange,
  error,
}: {
  kind: "wind" | "swell";
  label: string;
  value: string[];
  current: string[];
  onChange: (value: string[]) => void;
  error?: string;
}) {
  const id = useId().replace(/:/g, "");
  const toggle = (code: string) => onChange(value.includes(code) ? value.filter((c) => c !== code) : [...value, code]);
  const currentText = current.length ? current.map((c) => COMPASS[c as keyof typeof COMPASS]?.name ?? c).join(", ") : "не указано";
  return (
    <div className="gv-spot-wind-box">
      <div className="gv-spot-wind-title">
        <span id={id}>
          <Icon name={kind === "wind" ? "waves" : "diamond"} size={14} /> {label}
        </span>
        <strong>Сейчас: {currentText}</strong>
      </div>
      <div className="gv-compass-picker">
        <div className="gv-spot-winds gv-compass-grid" role="group" aria-labelledby={id}>
          {COMPASS_POINTS.map((code) => {
            const on = value.includes(code);
            return (
              <button
                key={code}
                type="button"
                className={cx("gv-wind-choice", on && "is-picked")}
                aria-pressed={on}
                title={COMPASS[code].name}
                aria-label={COMPASS[code].name}
                onClick={() => toggle(code)}
              >
                {COMPASS[code].short}
              </button>
            );
          })}
        </div>
        <div className="gv-compass-preview" aria-hidden="true">
          <CompassRose directions={value} kind={kind} bare size={150} />
        </div>
      </div>
      <div className="gv-compass-actions">
        <button type="button" className="gv-inline-link" onClick={() => onChange([])} disabled={!value.length}>
          Очистить
        </button>
        <button type="button" className="gv-inline-link" onClick={() => onChange(current)}>
          Вернуть текущие
        </button>
      </div>
      {error && <p className="gv-field-error">{error}</p>}
    </div>
  );
}

function InfrastructureEditor({
  value,
  onChange,
  types,
  error,
}: {
  value: InfrastructureInput[];
  onChange: (value: InfrastructureInput[]) => void;
  types: Array<{ code: string; label: string }>;
  error?: string;
}) {
  const update = (i: number, patch: Partial<InfrastructureInput>) => onChange(value.map((row, n) => (n === i ? { ...row, ...patch } : row)));
  return (
    <div className="gv-infra-editor">
      {value.length === 0 && <p className="gv-spot-muted">Объектов пока нет — добавьте первый.</p>}
      <ol className="gv-infra-rows">
        {value.map((row, i) => (
          <li key={i} className="gv-infra-row">
            <Select
              label={`Объект ${i + 1}: тип`}
              value={row.type}
              onChange={(e) => update(i, { type: e.target.value })}
              options={types.map((t) => ({ value: t.code, label: t.label }))}
            />
            <TextInput label="Название" maxLength={120} value={row.name} onChange={(e) => update(i, { name: e.target.value })} />
            <TextInput
              label="Расстояние, м"
              type="number"
              inputMode="numeric"
              min={0}
              max={100000}
              value={row.distance_m ?? ""}
              onChange={(e) => update(i, { distance_m: e.target.value === "" ? null : Number(e.target.value) })}
            />
            <button
              type="button"
              className="gv-infra-remove"
              aria-label={`Удалить объект ${i + 1}`}
              title="Удалить"
              onClick={() => onChange(value.filter((_, n) => n !== i))}
            >
              <Icon name="trash" size={16} />
            </button>
          </li>
        ))}
      </ol>
      {error && <p className="gv-field-error" role="alert">{error}</p>}
      <Button
        variant="pill"
        size="sm"
        icon="plus"
        disabled={value.length >= 30}
        onClick={() => onChange([...value, { type: types[0]?.code ?? "parking", name: "", distance_m: null }])}
      >
        Добавить объект
      </Button>
    </div>
  );
}
