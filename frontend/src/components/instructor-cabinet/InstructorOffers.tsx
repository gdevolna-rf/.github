"use client";
/**
 * Offers (INS-08): individual / group lesson objects — level, duration, price, capacity, spot, equipment, rules.
 * Create / edit in a modal, archive (offers with sessions are archived by the server, history stays), delete.
 * Each active offer links to «Добавить слот» in the schedule.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ik, instructorApi, type Offer, type OfferInput } from "@/lib/api/instructorCabinet";
import { isApiError } from "@/lib/api/errors";
import { apiFieldErrors, type FormErrors } from "@/lib/forms";
import { formatDuration, formatMoney, plural } from "@/lib/format";
import { RIDING_LEVEL_LABELS } from "@/lib/labels";
import { Tag } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Checkbox, Select, TextInput, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { QueryState } from "@/components/ui/QueryState";
import { EmptyState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ConfirmDialog } from "@/components/learning-cabinet/ConfirmDialog";
import { CURRENCY_OPTIONS, LEVEL_OPTIONS, OFFER_FORMAT_LABELS, OFFER_FORMAT_OPTIONS } from "@/components/learning-cabinet/dictionaries";
import { FormAlert } from "@/components/learning-cabinet/FormAlert";
import { useSpots } from "@/components/learning-cabinet/hooks";
import { useInstructorProfile, useOffers } from "./hooks";
import { instructorPaths } from "./paths";

interface OfferForm {
  title: string;
  description: string;
  format: "individual" | "group";
  level: string;
  duration_min: string;
  price: string;
  currency: string;
  capacity: string;
  spot_slug: string;
  equipment_included: boolean;
  equipment_note: string;
  rules: string;
  is_active: boolean;
}

const EMPTY: OfferForm = {
  title: "",
  description: "",
  format: "individual",
  level: "",
  duration_min: "90",
  price: "",
  currency: "RUB",
  capacity: "1",
  spot_slug: "",
  equipment_included: true,
  equipment_note: "",
  rules: "",
  is_active: true,
};

function toForm(o: Offer): OfferForm {
  return {
    title: o.title,
    description: o.description,
    format: o.format,
    level: o.level,
    duration_min: String(o.duration_min),
    price: String(Number(o.price)),
    currency: o.currency,
    capacity: String(o.capacity),
    spot_slug: o.spot?.slug ?? "",
    equipment_included: o.equipment_included,
    equipment_note: o.equipment_note,
    rules: o.rules,
    is_active: o.is_active,
  };
}

/** Client checks mirroring OfferSerializer (server stays the authority). */
export function validateOffer(f: OfferForm): FormErrors<keyof OfferForm> {
  const e: FormErrors<keyof OfferForm> = {};
  if (!f.title.trim()) e.title = "Укажите название";
  const price = Number(f.price.replace(",", "."));
  if (!f.price.trim() || !Number.isFinite(price) || price < 0) e.price = "Укажите цену числом";
  const duration = Number(f.duration_min);
  if (!Number.isInteger(duration) || duration < 15 || duration > 1440) e.duration_min = "От 15 минут до 24 часов";
  const capacity = Number(f.capacity);
  if (!Number.isInteger(capacity) || capacity < 1 || capacity > 100) e.capacity = "От 1 до 100 учеников";
  else if (f.format === "individual" && capacity > 2) e.capacity = "Индивидуальное занятие — не больше 2 учеников";
  return e;
}

function toInput(f: OfferForm): OfferInput {
  return {
    title: f.title.trim(),
    description: f.description.trim(),
    format: f.format,
    level: f.level,
    duration_min: Number(f.duration_min),
    price: f.price.trim().replace(",", "."),
    currency: f.currency,
    capacity: Number(f.capacity),
    spot_slug: f.spot_slug || null,
    equipment_included: f.equipment_included,
    equipment_note: f.equipment_note.trim(),
    rules: f.rules.trim(),
    is_active: f.is_active,
  };
}

function OfferModal({ offer, open, onClose }: { offer: Offer | null; open: boolean; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const profile = useInstructorProfile();
  const spots = useSpots();
  const [form, setForm] = useState<OfferForm>(offer ? toForm(offer) : EMPTY);
  const [errors, setErrors] = useState<FormErrors<keyof OfferForm>>({});
  const [pending, setPending] = useState(false);
  const set = <K extends keyof OfferForm>(k: K, v: OfferForm[K]) => setForm((f) => ({ ...f, [k]: v }));

  const mySpots = new Set((profile.data?.spots ?? []).map((s) => s.slug));
  const regions = new Set((profile.data?.regions ?? []).map((r) => r.slug));
  const spotOptions = (spots.data ?? [])
    .filter((s) => mySpots.has(s.slug) || (s.region && regions.has(s.region.slug)) || s.slug === form.spot_slug)
    .map((s) => ({ value: s.slug, label: s.name }));

  const submit = async () => {
    const e = validateOffer(form);
    setErrors(e);
    if (Object.keys(e).length) return;
    setPending(true);
    try {
      if (offer) await instructorApi.offers.update(offer.id, toInput(form));
      else await instructorApi.offers.create(toInput(form));
      await queryClient.invalidateQueries({ queryKey: ik.offers });
      void queryClient.invalidateQueries({ queryKey: ik.profile });
      toast.success(offer ? "Предложение сохранено" : "Предложение добавлено");
      onClose();
    } catch (err) {
      setErrors(apiFieldErrors(err, { spot_slug: "spot_slug" }) as FormErrors<keyof OfferForm>);
    } finally {
      setPending(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={() => !pending && onClose()}
      title={offer ? "Редактирование предложения" : "Новое предложение"}
      size="wide"
      footer={
        <>
          <Button variant="primary" onClick={() => void submit()} loading={pending}>
            Сохранить
          </Button>
          <Button variant="soft" onClick={onClose} disabled={pending}>
            Отмена
          </Button>
        </>
      }
    >
      <TextInput label="Название" required value={form.title} onChange={(e) => set("title", e.target.value)} maxLength={160} error={errors.title} placeholder="Индивидуальное занятие для новичков" data-autofocus />
      <Textarea label="Описание" value={form.description} onChange={(e) => set("description", e.target.value)} maxLength={2000} rows={3} placeholder="Как проходит занятие, что входит" />
      <div className="gv-form-grid">
        <Select
          label="Формат"
          value={form.format}
          onChange={(e) => {
            const format = e.target.value as OfferForm["format"];
            setForm((f) => ({ ...f, format, capacity: format === "individual" && Number(f.capacity) > 2 ? "1" : f.capacity }));
          }}
          options={OFFER_FORMAT_OPTIONS}
        />
        <Select label="Уровень учеников" placeholder="Любой" value={form.level} onChange={(e) => set("level", e.target.value)} options={LEVEL_OPTIONS} />
        <TextInput label="Длительность, мин" type="number" min={15} max={1440} step={5} value={form.duration_min} onChange={(e) => set("duration_min", e.target.value)} error={errors.duration_min} />
        <TextInput
          label="Учеников на занятии"
          type="number"
          min={1}
          max={form.format === "individual" ? 2 : 100}
          value={form.capacity}
          onChange={(e) => set("capacity", e.target.value)}
          error={errors.capacity}
          hint={form.format === "individual" ? "Индивидуально — 1–2 ученика" : undefined}
        />
        <TextInput label="Цена за ученика" required inputMode="decimal" value={form.price} onChange={(e) => set("price", e.target.value)} error={errors.price} placeholder="3500" />
        <Select label="Валюта" value={form.currency} onChange={(e) => set("currency", e.target.value)} options={CURRENCY_OPTIONS} />
      </div>
      <Select
        label="Спот"
        placeholder="Не указан — выберу при создании слота"
        value={form.spot_slug}
        onChange={(e) => set("spot_slug", e.target.value)}
        options={spotOptions}
        error={(errors as Record<string, string | undefined>).spot_slug}
        hint="Список — споты вашей карточки и её регионов"
      />
      <Checkbox label="Снаряжение включено" description="Доска и гидрокостюм входят в стоимость" checked={form.equipment_included} onChange={(e) => set("equipment_included", e.target.checked)} />
      <TextInput label="Про снаряжение" value={form.equipment_note} onChange={(e) => set("equipment_note", e.target.value)} maxLength={300} placeholder="Доска и гидрокостюм по размеру" />
      <Textarea label="Правила: перенос и отмена" value={form.rules} onChange={(e) => set("rules", e.target.value)} maxLength={2000} rows={3} placeholder="Перенос по погоде — бесплатно. Отмена позднее чем за 12 часов — по договорённости." />
      <Checkbox label="Предложение активно" description="Неактивное не видно в карточке, новые слоты по нему создать нельзя" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} />
      {errors._form && <FormAlert>{errors._form}</FormAlert>}
    </Modal>
  );
}

function OfferRow({ offer, onEdit }: { offer: Offer; onEdit: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  return (
    <li className="gv-ac-line lc-offer">
      <div className="gv-ac-line-main">
        <strong className="gv-clamp-2" title={offer.title}>
          {offer.title}
        </strong>
        <small>
          {OFFER_FORMAT_LABELS[offer.format]} · {formatDuration(offer.duration_min)} · {formatMoney(offer.price, offer.currency)} · до {offer.capacity}{" "}
          {plural(offer.capacity, ["ученика", "учеников", "учеников"])}
          {offer.level ? ` · ${RIDING_LEVEL_LABELS[offer.level] ?? ""}` : ""}
        </small>
        <small>
          {offer.spot ? offer.spot.name : "Спот не указан"} · {offer.equipment_included ? "снаряжение включено" : "снаряжение отдельно"} · ближайших слотов: {offer.upcoming_sessions}
        </small>
        <div className="lc-session-tags">{offer.is_active ? <Tag variant="verified">Активно</Tag> : <Tag variant="plain" className="lc-tag-private">В архиве</Tag>}</div>
      </div>
      <div className="lc-row-actions">
        {offer.is_active && (
          <ButtonLink href={`${instructorPaths.schedule}?new=1&offer=${offer.id}`} variant="soft" size="sm" icon="plus">
            Слот
          </ButtonLink>
        )}
        <Button variant="soft" size="sm" icon="pencil" onClick={onEdit} aria-label={`Изменить «${offer.title}»`}>
          Изменить
        </Button>
        <Button variant="danger" size="sm" icon="trash" onClick={() => setConfirm(true)} aria-label={`Удалить «${offer.title}»`}>
          Удалить
        </Button>
      </div>
      <ConfirmDialog
        open={confirm}
        title="Удалить предложение?"
        confirmLabel="Удалить"
        onClose={() => setConfirm(false)}
        onConfirm={() => instructorApi.offers.remove(offer.id)}
        onDone={() => {
          toast.success(offer.upcoming_sessions || offer.is_active === false ? "Предложение перенесено в архив или удалено" : "Предложение удалено");
          void queryClient.invalidateQueries({ queryKey: ik.offers });
          void queryClient.invalidateQueries({ queryKey: ik.profile });
        }}
      >
        <p>
          «{offer.title}». Если по предложению уже были занятия, сервер не удалит его, а перенесёт в архив — история записей сохранится.
        </p>
      </ConfirmDialog>
    </li>
  );
}

export function InstructorOffers() {
  const profile = useInstructorProfile();
  const offers = useOffers(Boolean(profile.data));
  const [editing, setEditing] = useState<Offer | null>(null);
  const [creating, setCreating] = useState(false);

  if (profile.isPending) return <LoadingState variant="skeleton" lines={4} />;
  if (!profile.isError && profile.data === null) {
    return (
      <EmptyState
        compact
        title="Сначала создайте карточку инструктора"
        text="Предложения привязаны к карточке: заполните её, затем добавьте форматы занятий с ценой и длительностью."
        action={{ label: "Заполнить карточку", href: instructorPaths.profile }}
      />
    );
  }

  return (
    <div className="lc-offers">
      <div className="gv-card-head">
        <div className="gv-card-head-text">
          <h3 className="lc-section-title">Предложения</h3>
          <p className="gv-ac-desc">Что вы предлагаете ученикам: формат, длительность, цена, спот и правила. По активным предложениям создаются слоты в расписании.</p>
        </div>
        <div className="gv-card-head-actions">
          <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
            Предложение
          </Button>
        </div>
      </div>
      <QueryState
        query={offers}
        loading={<LoadingState variant="skeleton" lines={4} />}
        isEmpty={(d) => d.length === 0}
        empty={<EmptyState compact title="Предложений пока нет" text="Добавьте первое: например, индивидуальное занятие 90 минут." action={{ label: "Добавить предложение", onClick: () => setCreating(true), icon: "plus" }} />}
      >
        {(data) => (
          <ul className="lc-list" aria-label="Мои предложения">
            {data.map((o) => (
              <OfferRow key={o.id} offer={o} onEdit={() => setEditing(o)} />
            ))}
          </ul>
        )}
      </QueryState>
      {(creating || editing) && (
        <OfferModal
          key={editing?.id ?? "new"}
          offer={editing}
          open
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
        />
      )}
      {isApiError(offers.error) && offers.error.isConflict ? <FormAlert>{offers.error.message}</FormAlert> : null}
    </div>
  );
}
