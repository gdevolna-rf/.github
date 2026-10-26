"use client";
/**
 * Model editor — the only place to edit a board model (BRD-01/02/03/05/11, UX-08/09, F10, ATX-06/07/08):
 * name, type (standard + the workshop's own types), description, tags; ≤10 photos with cover/order/× and a
 * separate video tile; size variants with the server-generated SKU; publication checklist, publish/unpublish,
 * archive. The primary button is «Сохранить» and a successful save is confirmed (toast, card updates).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { shaperApi, shaperKeys, type BoardModelDetail, type Workshop } from "@/lib/api/shaper";
import type { Media } from "@/lib/api/types";
import { cx } from "@/lib/cx";
import { routes } from "@/lib/routes";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select, Textarea, TextInput } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { MediaUploader } from "@/components/ui/MediaUploader";
import { Modal } from "@/components/ui/Modal";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { emptyVariantDraft, galleryOrder, planGallerySync, validateVariant, variantDraftFromServer, variantInput, type VariantDraft, type VariantField } from "./draft";
import { modelDraftFrom, modelInput, saveModel, type ModelDraft, type ModelField, type SaveOutcome } from "./saveModel";
import { shaperRoutes } from "./routes";
import { VariantEditor } from "./VariantEditor";

type VariantErrors = Record<string, Partial<Record<VariantField | "_form", string>>>;

function originalsOf(detail: BoardModelDetail | null): Record<string, VariantDraft> {
  const out: Record<string, VariantDraft> = {};
  for (const v of detail?.variants ?? []) if (v.is_active) out[v.id] = variantDraftFromServer(v);
  return out;
}

function parseTags(text: string): string[] {
  return text
    .split(",")
    .map((t) => t.trim().replace(/^#/, ""))
    .filter(Boolean)
    .slice(0, 12);
}

function EditorForm({
  workshop,
  initial,
  onClose,
  organization,
}: {
  workshop: Workshop;
  initial: BoardModelDetail | null;
  onClose: () => void;
  organization?: string | null;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [server, setServer] = useState<BoardModelDetail | null>(initial);
  const [model, setModel] = useState<ModelDraft>(() => modelDraftFrom(initial));
  const [tagsText, setTagsText] = useState(() => (initial?.tags ?? []).join(", "));
  const [originals, setOriginals] = useState<Record<string, VariantDraft>>(() => originalsOf(initial));
  const [variants, setVariants] = useState<VariantDraft[]>(() => {
    const list = Object.values(originalsOf(initial));
    return list.length ? list : [emptyVariantDraft()];
  });
  const [removed, setRemoved] = useState<string[]>([]);
  const [photos, setPhotos] = useState<Media[]>(() => (initial?.photos ?? []).map((p) => p.media));
  const [video, setVideo] = useState<Media | null>(initial?.video ?? null);
  const [modelErrors, setModelErrors] = useState<Partial<Record<ModelField | "_form", string>>>({});
  const [variantErrors, setVariantErrors] = useState<VariantErrors>({});
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);

  const types = useQuery({ queryKey: shaperKeys.boardTypes(workshop.id), queryFn: () => shaperApi.boardTypes(workshop.id) });
  const materials = useQuery({ queryKey: shaperKeys.materials(workshop.id), queryFn: () => shaperApi.materials(workshop.id) });

  const state = useMemo(() => ({ model: { ...model, tags: parseTags(tagsText) }, variants, removed, photos, video }), [model, tagsText, variants, removed, photos, video]);
  const dirty = useMemo(() => {
    if (!server) return true;
    if (Object.keys(modelInput(state.model, server)).length) return true;
    if (removed.length) return true;
    if (variants.some((v) => !v.id || Object.keys(variantInput(v, originals[v.id])).length)) return true;
    const plan = planGallerySync(server.photos, photos);
    if (plan.add.length || plan.remove.length || galleryOrder(server.photos, photos)) return true;
    return (video?.id ?? null) !== (server.video?.id ?? null);
  }, [server, state, removed, variants, originals, photos, video]);

  const invalidate = () => qc.invalidateQueries({ queryKey: shaperKeys.all });

  const setModelField = <K extends ModelField>(key: K, value: ModelDraft[K]) => {
    setModel((m) => ({ ...m, [key]: value }));
    setModelErrors((e) => ({ ...e, [key]: undefined, _form: undefined }));
  };
  const setVariantField = (key: string, field: VariantField, value: string) => {
    setVariants((list) => list.map((v) => (v.key === key ? { ...v, [field]: value } : v)));
    setVariantErrors((e) => (e[key] ? { ...e, [key]: { ...e[key], [field]: undefined, _form: undefined } } : e));
  };
  const removeVariant = (draft: VariantDraft) => {
    setVariants((list) => list.filter((v) => v.key !== draft.key));
    if (draft.id) setRemoved((r) => [...r, draft.id!]);
  };

  /** After a partial save: re-read the model and keep the failed parts of the draft with their errors. */
  const merge = async (outcome: SaveOutcome) => {
    if (!outcome.modelId) return;
    let fresh: BoardModelDetail | null = null;
    try {
      fresh = await shaperApi.model(outcome.modelId);
    } catch {
      return;
    }
    const freshOriginals = originalsOf(fresh);
    setServer(fresh);
    setOriginals(freshOriginals);
    setVariants((list) => {
      const next = list.map((v) => {
        const saved = outcome.saved[v.key];
        if (saved) return freshOriginals[saved.id] ?? variantDraftFromServer(saved);
        return v;
      });
      for (const id of Object.keys(outcome.removeErrors)) {
        const back = freshOriginals[id];
        if (back) next.push(back);
      }
      return next;
    });
    // successful removals are done; failed ones are back in the list with their error
    setRemoved([]);
    const errs: VariantErrors = { ...outcome.variantErrors };
    for (const [id, message] of Object.entries(outcome.removeErrors)) errs[id] = { _form: message };
    setVariantErrors(errs);
  };

  const save = async () => {
    // client validation first (no request with obviously broken data)
    const errs: VariantErrors = {};
    for (const v of variants) {
      const e = validateVariant(v);
      if (Object.keys(e).length) errs[v.key] = { ...e, _form: "Проверьте размеры и цену этого варианта." };
    }
    const mErrs: Partial<Record<ModelField | "_form", string>> = {};
    if (!model.name.trim()) mErrs.name = "Укажите название модели.";
    else if (model.name.trim().length > 100) mErrs.name = "Не длиннее 100 символов.";
    if (!model.board_type_id) mErrs.board_type_id = "Выберите тип доски.";
    if (Object.keys(errs).length || Object.keys(mErrs).length) {
      setVariantErrors(errs);
      setModelErrors({ ...mErrs, _form: "Проверьте отмеченные поля." });
      return;
    }
    if (server && !dirty) {
      toast.info("Изменений нет — всё уже сохранено");
      return;
    }
    setSaving(true);
    setModelErrors({});
    setVariantErrors({});
    setMediaError(null);
    const outcome = await saveModel({ workshopId: workshop.id, original: server, state, originals });
    setSaving(false);
    void invalidate();
    if (outcome.ok) {
      const skus = Object.values(outcome.saved).map((v) => v.sku);
      const versioned = outcome.versioned.map((v) => v.sku);
      const base = outcome.created ? `Доска добавлена${skus.length ? ` · ${skus.join(", ")}` : ""}` : "Изменения сохранены";
      toast.success(versioned.length ? `${base}. Новая версия: ${versioned.join(", ")} — прошлые заказы сохранили прежние параметры` : base, {
        duration: versioned.length ? 9000 : undefined,
      });
      onClose();
      return;
    }
    setModelErrors(outcome.modelErrors);
    setMediaError(outcome.mediaError);
    await merge(outcome);
    const summary = outcome.modelErrors._form ?? "Часть изменений не сохранилась — ошибки отмечены ниже.";
    toast.error(summary, outcome.network ? { action: { label: "Повторить", onClick: () => void save() } } : undefined);
  };

  const publish = useMutation({
    mutationFn: (on: boolean) => (on ? shaperApi.publishModel(server!.id) : shaperApi.unpublishModel(server!.id)),
    onSuccess: (detail, on) => {
      setServer(detail);
      setPublishError(null);
      void invalidate();
      toast.success(on ? "Модель опубликована — она в каталоге «Все доски»" : "Модель снята с публикации");
    },
    onError: (err) => setPublishError(errorMessage(err)),
  });
  const remove = useMutation({
    mutationFn: () => shaperApi.deleteModel(server!.id),
    onSuccess: (res) => {
      void invalidate();
      toast.success(res?.result === "archived" ? "Модель перенесена в архив: по ней есть обращения или экземпляры, история сохранена" : "Модель удалена");
      onClose();
    },
    onError: (err) => {
      setConfirmDelete(false);
      setPublishError(errorMessage(err));
    },
  });

  const typeOptions = (types.data ?? []).map((t) => ({ value: String(t.id), label: t.is_custom ? `${t.name} (свой тип)` : t.name }));
  if (model.board_type_id && server?.board_type && !typeOptions.some((o) => o.value === model.board_type_id)) {
    typeOptions.push({ value: String(server.board_type.id), label: server.board_type.name });
  }
  const isPublished = server?.status === "published";
  const locked = server?.status === "hidden" || server?.status === "archived";

  const requestClose = () => {
    if (dirty && !saving && server) setConfirmClose(true);
    else if (dirty && !server && (model.name.trim() || photos.length)) setConfirmClose(true);
    else onClose();
  };

  return (
    <Modal
      open
      onClose={requestClose}
      size="xl"
      closeOnBackdrop={false}
      title={server ? "Редактировать модель доски" : "Добавить новую доску"}
      description={server ? server.name : "Модель сохранится черновиком — опубликуйте её, когда добавите фото и размер."}
      className="gv-sc-editor"
      footer={
        confirmClose ? (
          <div className="gv-sc-confirm" role="alertdialog" aria-label="Несохранённые изменения">
            <span>Есть несохранённые изменения. Закрыть без сохранения?</span>
            <Button variant="soft" onClick={() => setConfirmClose(false)} data-autofocus="">
              Продолжить редактирование
            </Button>
            <Button variant="danger" onClick={onClose}>
              Закрыть без сохранения
            </Button>
          </div>
        ) : (
          <div className="gv-sc-editor-actions">
            <Button variant="soft" onClick={requestClose} disabled={saving}>
              Отмена
            </Button>
            <Button variant="primary" loading={saving} onClick={() => void save()} disabled={locked}>
              Сохранить
            </Button>
          </div>
        )
      }
    >
      <div className="gv-sc-editor-body">
        {server && (
          <section className="gv-sc-editor-publish" aria-label="Публикация модели">
            <div className="gv-sc-publish-status">
              <StatusBadge domain="publication" status={server.status} />
              <StatusBadge domain="availability" status={server.availability} />
              {server.is_public && (
                <a className="gv-sc-public-link" href={routes.board(server.id)} target="_blank" rel="noreferrer">
                  Открыть в каталоге <Icon name="external" size={12} />
                </a>
              )}
            </div>
            {!locked && (
              <ul className="gv-sc-checklist gv-sc-checklist-inline" aria-label="Что нужно для публикации">
                {server.publish_requirements.map((r) => (
                  <li key={r.code} className={r.ok ? "is-ok" : "is-missing"}>
                    <Icon name={r.ok ? "check" : "alert"} size={13} />
                    <span>
                      {r.label}
                      <span className="sr-only">{r.ok ? " — готово" : " — не выполнено"}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div className="gv-sc-publish-actions">
              {!locked && (
                <Button variant={isPublished ? "soft" : "primary"} size="sm" loading={publish.isPending} disabled={dirty || saving} onClick={() => publish.mutate(!isPublished)}>
                  {isPublished ? "Снять с публикации" : "Опубликовать"}
                </Button>
              )}
              {server.status !== "archived" &&
                (confirmDelete ? (
                  <span className="gv-sc-confirm-inline" role="alertdialog" aria-label="Подтверждение удаления">
                    Удалить модель? Если по ней были обращения, она уйдёт в архив.
                    <Button variant="danger" size="sm" loading={remove.isPending} onClick={() => remove.mutate()}>
                      Да, удалить
                    </Button>
                    <Button variant="soft" size="sm" onClick={() => setConfirmDelete(false)}>
                      Нет
                    </Button>
                  </span>
                ) : (
                  <Button variant="danger" size="sm" icon="trash" onClick={() => setConfirmDelete(true)} disabled={saving}>
                    Удалить модель
                  </Button>
                ))}
            </div>
            {dirty && !locked && <p className="form-help">Сохраните изменения, чтобы опубликовать или снять модель.</p>}
            {server.status === "hidden" && <p className="gv-sc-form-error">Модель скрыта модератором — изменения недоступны. Обратитесь в поддержку.</p>}
            {server.status === "archived" && <p className="form-help">Модель в архиве: она не редактируется, история заказов сохранена.</p>}
            {publishError && (
              <p className="gv-sc-form-error" role="alert">
                <Icon name="alert" size={14} /> {publishError}
              </p>
            )}
          </section>
        )}

        <fieldset className="gv-sc-editor-section" disabled={saving || locked}>
          <legend>Основное</legend>
          <div className="gv-sc-editor-grid">
            <TextInput
              id="model-name"
              label="Название модели"
              required
              maxLength={100}
              placeholder="Например, Pacific Fish"
              value={model.name}
              onChange={(e) => setModelField("name", e.target.value)}
              error={modelErrors.name}
            />
            <Select
              id="model-type"
              label="Тип доски"
              required
              placeholder={types.isPending ? "Загружаем типы…" : "Выберите тип"}
              options={typeOptions}
              value={model.board_type_id}
              onChange={(e) => setModelField("board_type_id", e.target.value)}
              error={modelErrors.board_type_id ?? (types.isError ? "Не удалось загрузить типы досок." : undefined)}
              hint={
                <>
                  Свои типы добавляются в разделе <Link href={shaperRoutes.workshop(organization)}>«Мастерская»</Link>. Тип входит в артикул.
                </>
              }
            />
          </div>
          <Textarea
            id="model-description"
            label="Описание"
            maxLength={5000}
            rows={4}
            placeholder="Для каких волн и райдеров подходит доска…"
            value={model.description}
            onChange={(e) => setModelField("description", e.target.value)}
            error={modelErrors.description}
          />
          <TextInput
            id="model-tags"
            label="Теги"
            placeholder="холодная вода, для новичков"
            value={tagsText}
            onChange={(e) => {
              setTagsText(e.target.value);
              setModelErrors((er) => ({ ...er, tags: undefined }));
            }}
            error={modelErrors.tags}
            hint="Через запятую, до 12 тегов"
          />
        </fieldset>

        <fieldset className="gv-sc-editor-section" disabled={saving || locked}>
          <legend>Фото и видео</legend>
          <MediaUploader
            purpose="board_photo"
            label="Фотографии доски"
            value={photos}
            onChange={setPhotos}
            video={{ purpose: "board_video", label: "Видео доски", value: video, onChange: setVideo }}
            disabled={saving || locked}
          />
          <p className="form-help">Первое фото — обложка карточки. Порядок меняется стрелками или перетаскиванием.</p>
          {mediaError && (
            <p className="gv-sc-form-error" role="alert">
              <Icon name="alert" size={14} /> {mediaError}
            </p>
          )}
        </fieldset>

        <fieldset className="gv-sc-editor-section" disabled={saving || locked}>
          <legend>Размеры и артикулы</legend>
          <p className="form-help">
            Артикул присваивает сервер: код шейпера <b>{workshop.shaper_code}</b> · тип · длина · ширина · номер модели. Он обновится после
            сохранения; внутренний номер модели и прошлые заказы не меняются.
          </p>
          {materials.isError && (
            <ErrorState compact error={materials.error} title="Материалы не загрузились" onRetry={() => void materials.refetch()} />
          )}
          <div className="gv-sc-variants">
            {variants.map((v, i) => (
              <VariantEditor
                key={v.key}
                index={i}
                draft={v}
                original={v.id ? originals[v.id] : undefined}
                materials={materials.data ?? []}
                errors={variantErrors[v.key] ?? (v.id ? variantErrors[v.id] : undefined)}
                onChange={(field, value) => setVariantField(v.key, field, value)}
                onRemove={() => removeVariant(v)}
                canRemove={variants.length > 1 || !v.id}
                disabled={saving || locked}
              />
            ))}
          </div>
          {variants.length === 0 && <p className="form-help">Добавьте хотя бы один размер — без него модель нельзя опубликовать.</p>}
          <Button variant="soft" icon="plus" onClick={() => setVariants((list) => [...list, emptyVariantDraft()])} disabled={saving || locked || variants.length >= 30}>
            Добавить размер
          </Button>
        </fieldset>

        {modelErrors._form && (
          <p className={cx("gv-sc-form-error", "gv-sc-editor-error")} role="alert">
            <Icon name="alert" size={15} /> {modelErrors._form}
          </p>
        )}
      </div>
    </Modal>
  );
}

/** Opens for `modelId` = "new" | uuid; loads the model, then the form. */
export function ModelEditor({
  workshop,
  modelId,
  onClose,
  organization,
}: {
  workshop: Workshop;
  modelId: string | null;
  onClose: () => void;
  organization?: string | null;
}) {
  const isNew = modelId === "new";
  const detail = useQuery({
    queryKey: shaperKeys.model(modelId ?? ""),
    queryFn: () => shaperApi.model(modelId!),
    enabled: Boolean(modelId) && !isNew,
    staleTime: 0,
  });
  if (!modelId) return null;
  if (!isNew && (detail.isPending || detail.isError)) {
    return (
      <Modal open onClose={onClose} title="Редактировать модель доски" size="xl">
        {detail.isPending ? (
          <LoadingState label="Загружаем модель…" />
        ) : (
          <ErrorState error={detail.error} title={isApiError(detail.error) && detail.error.isNotFound ? "Модель не найдена" : undefined} onRetry={() => void detail.refetch()} />
        )}
      </Modal>
    );
  }
  return <EditorForm key={isNew ? "new" : detail.data!.id} workshop={workshop} initial={isNew ? null : detail.data!} onClose={onClose} organization={organization} />;
}
