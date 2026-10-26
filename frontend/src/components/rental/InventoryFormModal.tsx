"use client";
/**
 * Create / edit an inventory item (RENT-01/02, BRD-13): what, where and when, prices and conditions, photos
 * (≤10, first = cover, UX-08) and catalogue visibility. Create = one POST with photo_ids; edit = PATCH, then the
 * photo diff (DELETE removed → POST added → PUT order). Server field errors land under the fields; a network
 * failure keeps everything typed and offers «Повторить» (ATX-25). A retry after a partial save PATCHes the
 * already created item instead of creating a duplicate.
 */
import { useId, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { inventoryApi, inventoryKeys, PURPOSE_LABELS, type InventoryItem, type ItemPhoto } from "@/lib/api/inventory";
import { shaperApi, shaperKeys } from "@/lib/api/shaper";
import { isApiError } from "@/lib/api/errors";
import type { Media } from "@/lib/api/types";
import { apiFieldErrors, type FormErrors } from "@/lib/forms";
import { CONDITION_LABELS, INVENTORY_KIND_LABELS } from "@/lib/labels";
import { Button } from "@/components/ui/Button";
import { Select, TextInput, Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { MediaUploader } from "@/components/ui/MediaUploader";
import { Modal } from "@/components/ui/Modal";
import { ToggleRow } from "@/components/ui/Toggle";
import { useToast } from "@/components/ui/Toast";
import {
  desiredOrder,
  diffPhotos,
  emptyValues,
  FIELD_ALIASES,
  RENTAL_PURPOSES,
  SALE_PURPOSES,
  toPayload,
  validateValues,
  valuesFromItem,
  type InventoryField,
  type InventoryFormValues,
} from "./form";
import styles from "./rental.module.css";

const KIND_OPTIONS = Object.entries(INVENTORY_KIND_LABELS).map(([value, label]) => ({ value, label }));
const CONDITION_OPTIONS = Object.entries(CONDITION_LABELS).map(([value, label]) => ({ value, label }));
const PURPOSE_OPTIONS = Object.entries(PURPOSE_LABELS).map(([value, label]) => ({ value, label }));

export interface InventoryFormModalProps {
  open: boolean;
  onClose: () => void;
  /** null → create */
  item: InventoryItem | null;
  /** organization context (null = personal inventory) */
  organizationId: string | null;
  /** default region for new items (organization / profile region id) */
  defaultRegionId?: string | number | null;
  onSaved?: (item: InventoryItem) => void;
  /** the user may own a workshop → offer «Модель моей мастерской» (skips a useless me/workshop 404 otherwise) */
  canLinkVariants?: boolean;
}

export function InventoryFormModal(props: InventoryFormModalProps) {
  // Remount per item so every open starts from the saved state.
  if (!props.open) return null;
  return <InventoryForm key={props.item?.id ?? "new"} {...props} />;
}

function InventoryForm({ onClose, item, organizationId, defaultRegionId, onSaved, canLinkVariants = true }: InventoryFormModalProps) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const formId = useId().replace(/:/g, "");
  const [values, setValues] = useState<InventoryFormValues>(() =>
    item ? valuesFromItem(item) : emptyValues({ region_id: defaultRegionId ? String(defaultRegionId) : "" }),
  );
  const [photos, setPhotos] = useState<Media[]>(() => (item?.photos ?? []).slice().sort((a, b) => a.position - b.position).map((p) => p.media));
  const [errors, setErrors] = useState<FormErrors<InventoryField>>({});
  const [saving, setSaving] = useState(false);
  /** The saved item (after a successful create/patch) and its saved gallery — the baseline for the photo diff. */
  const savedRef = useRef<InventoryItem | null>(item);
  const baselineRef = useRef<ItemPhoto[]>(item?.photos ?? []);

  const regions = useQuery({ queryKey: shaperKeys.regions, queryFn: shaperApi.regions, staleTime: 60 * 60_000 });
  const regionSlug = regions.data?.find((r) => String(r.id) === values.region_id)?.slug ?? null;
  const spots = useQuery({
    queryKey: inventoryKeys.spots(regionSlug),
    queryFn: () => inventoryApi.spots(regionSlug),
    enabled: Boolean(regionSlug),
    staleTime: 10 * 60_000,
  });
  const variants = useQuery({
    queryKey: inventoryKeys.myVariants,
    queryFn: inventoryApi.myWorkshopVariants,
    staleTime: 5 * 60_000,
    enabled: canLinkVariants,
  });
  const linked = item?.variant ?? null;
  const variantOptions = useMemo(() => {
    const options = (variants.data ?? []).map((v) => ({
      value: v.id,
      label: `${v.model.name} · ${v.dimensions_display}${v.volume_display ? ` · ${v.volume_display}` : ""} · ${v.sku}`,
    }));
    // keep a linked variant that is no longer active visible as an option
    if (linked && !options.some((o) => o.value === linked.id)) {
      options.push({ value: linked.id, label: `${linked.model_name} · ${linked.dimensions_display} · ${linked.sku}` });
    }
    return options;
  }, [variants.data, linked]);
  const variantsAllowed = variantOptions.length > 0;

  const set = <K extends keyof InventoryFormValues>(key: K, value: InventoryFormValues[K]) => {
    setValues((v) => ({ ...v, [key]: value }));
    if (errors[key]) setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const onVariant = (id: string) => {
    const v = variants.data?.find((x) => x.id === id);
    setValues((cur) => ({
      ...cur,
      variant_id: id,
      title: cur.title.trim() || !v ? cur.title : `${v.model.name} ${v.length_display}`,
      size: cur.size.trim() || !v ? cur.size : v.dimensions_display,
    }));
  };

  const rental = RENTAL_PURPOSES.has(values.purpose);
  const sale = SALE_PURPOSES.has(values.purpose);

  const focusFirstError = (errs: FormErrors<InventoryField>) => {
    const first = Object.keys(errs).find((k) => k !== "_form" && errs[k as InventoryField]);
    if (!first) return;
    requestAnimationFrame(() => document.getElementById(`${formId}-${first}`)?.focus());
  };

  const save = async () => {
    const clientErrors = validateValues(values);
    if (Object.keys(clientErrors).length) {
      setErrors(clientErrors);
      focusFirstError(clientErrors);
      return;
    }
    setSaving(true);
    setErrors({});
    const created = !savedRef.current;
    try {
      let saved: InventoryItem;
      if (!savedRef.current) {
        saved = await inventoryApi.create(
          toPayload(values, { create: true, organizationId, photoIds: photos.map((m) => m.id), variantsAllowed }),
        );
        savedRef.current = saved;
        baselineRef.current = saved.photos;
      } else {
        const id = savedRef.current.id;
        saved = await inventoryApi.update(id, toPayload(values, { create: false, variantsAllowed }));
        savedRef.current = saved;
        let current = baselineRef.current;
        const diff = diffPhotos(current, photos);
        for (const photoId of diff.remove) {
          current = (await inventoryApi.deletePhoto(id, photoId)).photos;
          baselineRef.current = current;
        }
        if (diff.add.length) {
          current = (await inventoryApi.addPhotos(id, diff.add)).photos;
          baselineRef.current = current;
        }
        const order = desiredOrder(current, photos);
        if (order) {
          current = (await inventoryApi.orderPhotos(id, order)).photos;
          baselineRef.current = current;
        }
      }
      await queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
      toast.success(created && !item ? `«${saved.title}» добавлено` : "Изменения сохранены");
      onSaved?.(saved);
      onClose();
    } catch (err) {
      const next = apiFieldErrors(err, FIELD_ALIASES) as FormErrors<InventoryField>;
      if (savedRef.current && created) {
        next._form = `${next._form ?? "Не всё удалось сохранить."} Карточка уже создана — исправьте ошибку и нажмите «Сохранить» ещё раз.`;
      }
      setErrors(next);
      focusFirstError(next);
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
      if (isApiError(err) && err.retryable) {
        toast.error(err, { action: { label: "Повторить", onClick: () => void save() } });
      }
    } finally {
      setSaving(false);
    }
  };

  const fid = (name: InventoryField) => `${formId}-${name}`;
  const err = (name: InventoryField) => errors[name] ?? null;

  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      closeOnBackdrop={false}
      title={item ? "Редактировать снаряжение" : "Добавить снаряжение"}
      description={
        organizationId
          ? "Экземпляр организации: его увидят и смогут изменить сотрудники."
          : "Личный экземпляр: бронирования и обращения по нему приходят вам."
      }
      footer={
        <>
          <Button variant="pill" onClick={onClose} disabled={saving}>
            Отмена
          </Button>
          <Button variant="primary" type="submit" form={formId} loading={saving}>
            Сохранить
          </Button>
        </>
      }
    >
      <form
        id={formId}
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        {errors._form && (
          <div className="gv-form-error" role="alert">
            <Icon name="alert" size={16} />
            <span>{errors._form}</span>
          </div>
        )}

        <fieldset className={styles.section}>
          <legend>Что сдаёте</legend>
          <div className="gv-form-grid">
            <Select id={fid("kind")} label="Вид" options={KIND_OPTIONS} value={values.kind} onChange={(e) => set("kind", e.target.value)} error={err("kind")} />
            <Select
              id={fid("purpose")}
              label="Назначение"
              options={PURPOSE_OPTIONS}
              value={values.purpose}
              onChange={(e) => set("purpose", e.target.value)}
              error={err("purpose")}
            />
            <TextInput
              id={fid("title")}
              className={styles.full}
              label="Название"
              required
              maxLength={200}
              placeholder="Например, лонгборд 9′0″ или гидрокостюм 4/3 мм"
              value={values.title}
              onChange={(e) => set("title", e.target.value)}
              error={err("title")}
              data-autofocus
            />
            <TextInput
              id={fid("size")}
              label="Размер"
              maxLength={60}
              placeholder="9′0″ × 22″ или M"
              value={values.size}
              onChange={(e) => set("size", e.target.value)}
              error={err("size")}
            />
            <Select
              id={fid("condition")}
              label="Состояние"
              options={CONDITION_OPTIONS}
              value={values.condition}
              onChange={(e) => set("condition", e.target.value)}
              error={err("condition")}
            />
            {variantsAllowed && values.kind === "board" && (
              <Select
                id={fid("variant_id")}
                className={styles.full}
                label="Модель моей мастерской"
                placeholder="Не связана с моделью"
                hint="Экземпляр учитывается в наличии модели в каталоге досок."
                options={variantOptions}
                value={values.variant_id}
                onChange={(e) => onVariant(e.target.value)}
                error={err("variant_id")}
              />
            )}
            <Textarea
              id={fid("description")}
              className={styles.full}
              label="Описание"
              maxLength={5000}
              rows={3}
              placeholder="Комплектация, особенности, для какого уровня подходит"
              value={values.description}
              onChange={(e) => set("description", e.target.value)}
              error={err("description")}
            />
          </div>
        </fieldset>

        <fieldset className={styles.section}>
          <legend>Где и когда</legend>
          <div className="gv-form-grid">
            <Select
              id={fid("region_id")}
              label="Регион"
              placeholder={regions.isPending ? "Загружаем регионы…" : "Не указан"}
              options={(regions.data ?? []).map((r) => ({ value: String(r.id), label: r.name }))}
              value={values.region_id}
              onChange={(e) => {
                setValues((v) => ({ ...v, region_id: e.target.value, spot_id: "" }));
                setErrors((x) => ({ ...x, region_id: undefined, spot_id: undefined }));
              }}
              error={err("region_id") ?? (regions.isError ? "Не удалось загрузить регионы." : null)}
            />
            <Select
              id={fid("spot_id")}
              label="Спот рядом"
              placeholder={!values.region_id ? "Сначала выберите регион" : spots.isPending ? "Загружаем споты…" : "Без спота"}
              options={(spots.data ?? []).map((s) => ({ value: String(s.id), label: s.name }))}
              disabled={!values.region_id}
              value={values.spot_id}
              onChange={(e) => set("spot_id", e.target.value)}
              error={err("spot_id")}
            />
            <TextInput
              id={fid("pickup_location")}
              label="Место получения"
              maxLength={300}
              placeholder="Город, адрес или ориентир"
              value={values.pickup_location}
              onChange={(e) => set("pickup_location", e.target.value)}
              error={err("pickup_location")}
            />
            <TextInput
              id={fid("available_hours")}
              label="Когда можно забрать"
              maxLength={120}
              placeholder="Ежедневно 9:00–20:00"
              value={values.available_hours}
              onChange={(e) => set("available_hours", e.target.value)}
              error={err("available_hours")}
            />
          </div>
        </fieldset>

        <fieldset className={styles.section}>
          <legend>Цены и условия</legend>
          <div className="gv-form-grid">
            {rental && (
              <>
                <TextInput
                  id={fid("rental_price_per_day")}
                  label="Цена за сутки, ₽"
                  inputMode="decimal"
                  placeholder="1500"
                  value={values.rental_price_per_day}
                  onChange={(e) => set("rental_price_per_day", e.target.value)}
                  error={err("rental_price_per_day")}
                  hint="Укажите цену за сутки, за час или обе."
                />
                <TextInput
                  id={fid("rental_price_per_hour")}
                  label="Цена за час, ₽"
                  inputMode="decimal"
                  placeholder="400"
                  value={values.rental_price_per_hour}
                  onChange={(e) => set("rental_price_per_hour", e.target.value)}
                  error={err("rental_price_per_hour")}
                />
                <TextInput
                  id={fid("min_rental_hours")}
                  label="Минимальный срок, ч"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={720}
                  value={values.min_rental_hours}
                  onChange={(e) => set("min_rental_hours", e.target.value)}
                  error={err("min_rental_hours")}
                />
                <TextInput
                  id={fid("deposit_note")}
                  label="Залог"
                  maxLength={200}
                  placeholder="Например, документ или 5 000 ₽"
                  value={values.deposit_note}
                  onChange={(e) => set("deposit_note", e.target.value)}
                  error={err("deposit_note")}
                />
              </>
            )}
            {sale && (
              <TextInput
                id={fid("sale_price")}
                label="Цена продажи, ₽"
                inputMode="decimal"
                placeholder="45000"
                value={values.sale_price}
                onChange={(e) => set("sale_price", e.target.value)}
                error={err("sale_price")}
              />
            )}
            <TextInput
              id={fid("serial_number")}
              label="Инвентарный номер"
              maxLength={80}
              hint="Виден только вам и сотрудникам."
              value={values.serial_number}
              onChange={(e) => set("serial_number", e.target.value)}
              error={err("serial_number")}
            />
            <Textarea
              id={fid("restrictions")}
              className={styles.full}
              label="Ограничения"
              maxLength={2000}
              rows={2}
              placeholder="Например, только для райдеров среднего уровня, не для рифа"
              value={values.restrictions}
              onChange={(e) => set("restrictions", e.target.value)}
              error={err("restrictions")}
            />
          </div>
        </fieldset>

        <fieldset className={styles.section}>
          <legend>Фотографии</legend>
          <MediaUploader
            purpose="item_photo"
            maxFiles={10}
            value={photos}
            onChange={setPhotos}
            label="Фото снаряжения"
            disabled={saving}
          />
          {errors.photos && (
            <p className="gv-field-error" role="alert">
              {errors.photos}
            </p>
          )}
        </fieldset>

        <ToggleRow
          title="Показывать в каталоге аренды"
          description="Скрытый экземпляр остаётся в вашем инвентаре, но клиенты его не видят и не могут забронировать."
          checked={values.is_published}
          onChange={(v) => set("is_published", v)}
        />
      </form>
    </Modal>
  );
}
