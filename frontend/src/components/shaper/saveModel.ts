/**
 * «Сохранить» in the model editor (BRD-02/03/05/11, F10): a sequence of server calls, each error attributed to
 * the right place so the editor can show it next to the field / variant / gallery:
 *   1. model: POST (new, as a draft) or PATCH (changed fields only);
 *   2. variants: create new ones, then update changed ones (server SKU; `versioned` → a new F10 version),
 *      then delete removed ones (so the last active variant of a published model is never removed first);
 *   3. gallery: attach new photos, delete removed ones (after adding — the cover must stay), reorder;
 *      video: set / remove.
 * Variants are created one by one (not inside POST models) so a field error or 409 sku_conflict points to the
 * exact variant (nested create errors lose their index in the API's error format).
 */
import { isApiError, errorMessage } from "@/lib/api/errors";
import { shaperApi, type BoardModelDetail, type BoardModelInput, type ModelMediaPayload, type VariantResult } from "@/lib/api/shaper";
import type { Media } from "@/lib/api/types";
import { galleryOrder, planGallerySync, variantFieldErrors, variantInput, type VariantDraft, type VariantField } from "./draft";

export interface ModelDraft {
  name: string;
  board_type_id: string;
  description: string;
  tags: string[];
}

export type ModelField = keyof ModelDraft;

export interface EditorState {
  model: ModelDraft;
  variants: VariantDraft[];
  /** server ids of variants removed in the editor */
  removed: string[];
  photos: Media[];
  video: Media | null;
}

export interface SaveOutcome {
  ok: boolean;
  modelId: string | null;
  created: boolean;
  modelErrors: Partial<Record<ModelField | "_form", string>>;
  variantErrors: Record<string, Partial<Record<VariantField | "_form", string>>>;
  /** draft key → saved server variant */
  saved: Record<string, VariantResult>;
  /** server id → result of the removal */
  removed: Record<string, "deleted" | "deactivated">;
  removeErrors: Record<string, string>;
  mediaError: string | null;
  versioned: VariantResult[];
  /** request never reached the server — offer «Повторить» (ATX-25) */
  network: boolean;
}

export function modelDraftFrom(detail?: BoardModelDetail | null): ModelDraft {
  return {
    name: detail?.name ?? "",
    board_type_id: detail?.board_type ? String(detail.board_type.id) : "",
    description: detail?.description ?? "",
    tags: [...(detail?.tags ?? [])],
  };
}

export function modelInput(draft: ModelDraft, original?: BoardModelDetail | null): BoardModelInput {
  const base = modelDraftFrom(original);
  const out: BoardModelInput = {};
  if (!original || draft.name.trim() !== base.name.trim()) out.name = draft.name.trim();
  if (!original || draft.board_type_id !== base.board_type_id) out.board_type_id = Number(draft.board_type_id);
  if (!original ? draft.description.trim() !== "" : draft.description !== base.description) out.description = draft.description;
  const tags = draft.tags.map((t) => t.trim()).filter(Boolean);
  if (!original ? tags.length > 0 : tags.join("\n") !== base.tags.join("\n")) out.tags = tags;
  return out;
}

const MODEL_FIELDS: Record<string, ModelField> = { name: "name", board_type_id: "board_type_id", description: "description", tags: "tags", slug: "name" };

export async function saveModel(params: {
  workshopId: string;
  original: BoardModelDetail | null;
  state: EditorState;
  originals: Record<string, VariantDraft>;
}): Promise<SaveOutcome> {
  const { workshopId, original, state, originals } = params;
  const out: SaveOutcome = {
    ok: true,
    modelId: original?.id ?? null,
    created: false,
    modelErrors: {},
    variantErrors: {},
    saved: {},
    removed: {},
    removeErrors: {},
    mediaError: null,
    versioned: [],
    network: false,
  };
  const fail = (err: unknown) => {
    out.ok = false;
    if (isApiError(err) && (err.isNetwork || err.retryable)) out.network = true;
  };

  /* 1. model */
  const body = modelInput(state.model, original);
  try {
    if (!original) {
      const created = await shaperApi.createModel(workshopId, body);
      out.modelId = created.id;
      out.created = true;
    } else if (Object.keys(body).length) {
      await shaperApi.updateModel(original.id, body);
    }
  } catch (err) {
    fail(err);
    if (isApiError(err)) {
      for (const [k, v] of Object.entries(err.fields)) if (MODEL_FIELDS[k] && v[0]) out.modelErrors[MODEL_FIELDS[k]] = v[0];
      out.modelErrors._form = err.message;
    } else out.modelErrors._form = errorMessage(err);
    return out; // nothing else makes sense without the model
  }
  const modelId = out.modelId!;

  /* 2. variants: create → update → delete */
  const ordered = [...state.variants.filter((v) => !v.id), ...state.variants.filter((v) => v.id)];
  for (const draft of ordered) {
    const original = draft.id ? originals[draft.id] : undefined;
    const input = variantInput(draft, original);
    if (draft.id && !Object.keys(input).length) continue;
    try {
      const result = draft.id ? await shaperApi.updateVariant(modelId, draft.id, input) : await shaperApi.createVariant(modelId, input);
      out.saved[draft.key] = result;
      if (result.versioned) out.versioned.push(result);
    } catch (err) {
      fail(err);
      out.variantErrors[draft.key] = isApiError(err) ? variantFieldErrors(err.fields, err.message) : { _form: errorMessage(err) };
      if (!out.variantErrors[draft.key]._form && isApiError(err)) out.variantErrors[draft.key]._form = err.message;
    }
  }
  for (const id of state.removed) {
    try {
      const res = await shaperApi.deleteVariant(modelId, id);
      out.removed[id] = res?.result ?? "deleted";
    } catch (err) {
      fail(err);
      out.removeErrors[id] = errorMessage(err);
    }
  }

  /* 3. media */
  try {
    let payload: ModelMediaPayload = { photos: original?.photos ?? [], variants: [], video: original?.video ?? null };
    const plan = planGallerySync(payload.photos, state.photos);
    if (plan.add.length) payload = await shaperApi.addModelPhotos(modelId, plan.add);
    for (const itemId of plan.remove) payload = await shaperApi.deleteModelPhoto(modelId, itemId);
    const order = galleryOrder(payload.photos, state.photos);
    if (order) payload = await shaperApi.orderModelPhotos(modelId, order);
    const videoId = state.video?.id ?? null;
    const serverVideo = original?.video?.id ?? null;
    if (videoId !== serverVideo) {
      if (videoId) await shaperApi.setModelVideo(modelId, videoId);
      else await shaperApi.deleteModelVideo(modelId);
    }
  } catch (err) {
    fail(err);
    out.mediaError = errorMessage(err, "Не удалось сохранить фото или видео.");
  }

  return out;
}
