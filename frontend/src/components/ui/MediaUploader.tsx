"use client";
/**
 * Photo/video uploader (UX-08/09, BRD-03/04, ATX-06, ATX-24).
 * Layout: upload slot on top → thumbnails grid below (× delete top-right, «Обложка» marker / «Сделать обложкой»,
 * drag-and-drop or ‹ › buttons to reorder) → a separate compact video tile (poster, duration, delete).
 * Upload: presigned flow from src/lib/api/media.ts (POST uploads → PUT with progress → complete → poll).
 * The component only manages the list of ready Media; the parent saves it (ids + order + cover) to its model.
 *
 *   <MediaUploader purpose="board_photo" value={photos} onChange={setPhotos}
 *     coverId={coverId} onCoverChange={setCoverId}
 *     video={{ purpose: "board_video", value: video, onChange: setVideo }} />
 */
import { useCallback, useEffect, useId, useRef, useState, type DragEvent } from "react";
import { cx } from "@/lib/cx";
import { errorMessage } from "@/lib/api/errors";
import { formatBytes, MEDIA_LIMITS, mediaSrc, uploadMedia, validateFile } from "@/lib/api/media";
import type { Media, MediaKind, MediaPurpose } from "@/lib/api/types";
import { formatClock, plural, WORDS } from "@/lib/format";
import { Icon } from "./Icon";

interface Pending {
  key: string;
  file: File;
  preview: string | null;
  progress: number;
  stage: "uploading" | "processing" | "error";
  error?: string;
  controller: AbortController;
}

export interface VideoSlotConfig {
  purpose: MediaPurpose;
  value: Media | null;
  onChange: (media: Media | null) => void;
  accept?: string[];
  label?: string;
}

export interface MediaUploaderProps {
  purpose: MediaPurpose;
  /** Gallery item kind (default image). Use "document" for certificate scans (maxFiles=1). */
  kind?: Exclude<MediaKind, "video">;
  maxFiles?: number;
  /** MIME types; default = server limits for the kind. */
  accept?: string[];
  value: Media[];
  onChange: (items: Media[]) => void;
  /** Explicit cover; without onCoverChange the first photo is the cover and «Сделать обложкой» moves it first. */
  coverId?: string | null;
  onCoverChange?: (id: string) => void;
  /** Separate video tile below the grid (UX-09). */
  video?: VideoSlotConfig;
  /** Optional server-side removal (e.g. DELETE models/{id}/media/{mid}); the item is removed only if it resolves. */
  onRemove?: (media: Media) => Promise<void>;
  label?: string;
  hint?: string;
  disabled?: boolean;
  className?: string;
  /** For tests / custom flows. */
  uploader?: typeof uploadMedia;
}

const isImage = (type: string) => type.startsWith("image/");

function acceptText(types: string[]): string {
  return types
    .map((t) => t.split("/")[1]?.toUpperCase().replace("JPEG", "JPG").replace("QUICKTIME", "MOV"))
    .filter((v, i, a) => v && a.indexOf(v) === i)
    .join(", ");
}

export function MediaUploader({
  purpose,
  kind = "image",
  maxFiles = 10,
  accept,
  value,
  onChange,
  coverId,
  onCoverChange,
  video,
  onRemove,
  label = "Фотографии",
  hint,
  disabled,
  className,
  uploader = uploadMedia,
}: MediaUploaderProps) {
  const id = useId().replace(/:/g, "");
  const inputRef = useRef<HTMLInputElement>(null);
  const valueRef = useRef(value);
  valueRef.current = value;
  const [pending, setPending] = useState<Pending[]>([]);
  const pendingRef = useRef(pending);
  pendingRef.current = pending;
  const [errors, setErrors] = useState<string[]>([]);
  const [announce, setAnnounce] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const dragIndex = useRef<number | null>(null);
  const types = accept?.length ? accept : MEDIA_LIMITS[kind].types;
  const used = value.length + pending.length;
  const remaining = Math.max(0, maxFiles - used);
  const explicitCover = Boolean(onCoverChange);
  const currentCover = explicitCover ? (coverId ?? value[0]?.id ?? null) : (value[0]?.id ?? null);
  const noun = kind === "image" ? WORDS.photo : (["файл", "файла", "файлов"] as const);

  useEffect(
    () => () => {
      pendingRef.current.forEach((p) => {
        p.controller.abort();
        if (p.preview) URL.revokeObjectURL(p.preview);
      });
    },
    [],
  );

  const patch = (key: string, data: Partial<Pending>) =>
    setPending((list) => list.map((p) => (p.key === key ? { ...p, ...data } : p)));

  const dropPending = (key: string) =>
    setPending((list) => {
      const item = list.find((p) => p.key === key);
      if (item?.preview) URL.revokeObjectURL(item.preview);
      return list.filter((p) => p.key !== key);
    });

  const run = useCallback(
    async (item: Pending) => {
      try {
        const media = await uploader(item.file, {
          purpose,
          kind,
          signal: item.controller.signal,
          onProgress: (progress) => patch(item.key, { progress }),
          onStage: (stage) => patch(item.key, { stage }),
        });
        const next = [...valueRef.current, media];
        valueRef.current = next;
        onChange(next);
        dropPending(item.key);
        setAnnounce(`«${item.file.name}» загружено`);
      } catch (err) {
        if ((err as Error)?.name === "AbortError") return dropPending(item.key);
        patch(item.key, { stage: "error", error: errorMessage(err, "Не удалось загрузить файл.") });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [purpose, kind, onChange, uploader],
  );

  const addFiles = (files: File[]) => {
    if (disabled || !files.length) return;
    const problems: string[] = [];
    const accepted: File[] = [];
    for (const file of files) {
      const problem = validateFile(file, kind, types);
      if (problem) problems.push(problem);
      else accepted.push(file);
    }
    const room = Math.max(0, maxFiles - valueRef.current.length - pendingRef.current.length);
    if (accepted.length > room) {
      problems.push(
        room === 0
          ? `Уже загружено максимум — ${maxFiles} ${plural(maxFiles, noun)}. Удалите лишнее, чтобы добавить новое.`
          : `Можно добавить ещё ${room} ${plural(room, noun)} (максимум ${maxFiles}). Лишние файлы не добавлены.`,
      );
    }
    setErrors(problems);
    const items: Pending[] = accepted.slice(0, room).map((file, i) => ({
      key: `${Date.now()}-${i}-${file.name}`,
      file,
      preview: isImage(file.type) && typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : null,
      progress: 0,
      stage: "uploading",
      controller: new AbortController(),
    }));
    if (!items.length) return;
    setPending((list) => [...list, ...items]);
    items.forEach((item) => void run(item));
  };

  const retry = (item: Pending) => {
    const fresh = { ...item, stage: "uploading" as const, progress: 0, error: undefined, controller: new AbortController() };
    patch(item.key, fresh);
    void run(fresh);
  };

  const remove = async (media: Media, index: number) => {
    if (onRemove) {
      try {
        await onRemove(media);
      } catch (err) {
        setErrors([errorMessage(err, "Не удалось удалить файл. Попробуйте ещё раз.")]);
        return;
      }
    }
    const next = valueRef.current.filter((m) => m.id !== media.id);
    valueRef.current = next;
    onChange(next);
    if (explicitCover && currentCover === media.id && next[0]) onCoverChange?.(next[0].id);
    setAnnounce(`Фото ${index + 1} удалено`);
  };

  const move = (from: number, to: number) => {
    if (to < 0 || to >= valueRef.current.length || from === to) return;
    const next = [...valueRef.current];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    valueRef.current = next;
    onChange(next);
    setAnnounce(`Фото ${from + 1} перемещено на место ${to + 1}`);
  };

  const makeCover = (index: number) => {
    const media = valueRef.current[index];
    if (!media) return;
    if (explicitCover) onCoverChange?.(media.id);
    else move(index, 0);
    setAnnounce(`Фото ${index + 1} — обложка`);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (dragIndex.current !== null) return; // internal reorder drag, handled by tiles
    addFiles(Array.from(e.dataTransfer?.files ?? []));
  };

  const limitsText =
    hint ??
    `${acceptText(types)} до ${formatBytes(MEDIA_LIMITS[kind].maxBytes)} · не больше ${maxFiles} ${plural(maxFiles, noun)}`;

  return (
    <div className={cx("gv-uploader", disabled && "is-disabled", className)}>
      <div className="gv-uploader-head">
        <span className="gv-field-label" id={`${id}-label`}>
          {label}
        </span>
        <span className="gv-uploader-count" aria-live="polite">
          {value.length} из {maxFiles}
        </span>
      </div>

      <div
        className={cx("gv-upload-slot", dragOver && "is-over", remaining === 0 && "is-full")}
        onDragOver={(e) => {
          if (dragIndex.current !== null) return;
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <Icon name="upload" size={22} />
        <div className="gv-upload-slot-text">
          <b>{remaining === 0 ? `Загружено максимум — ${maxFiles} ${plural(maxFiles, noun)}` : "Перетащите файлы сюда или выберите на устройстве"}</b>
          <small id={`${id}-hint`}>{limitsText}</small>
        </div>
        <button
          type="button"
          className="pill-btn"
          onClick={() => inputRef.current?.click()}
          disabled={disabled || remaining === 0}
          aria-describedby={`${id}-hint`}
        >
          <Icon name="plus" size={16} />
          <span>{kind === "image" ? "Выбрать фото" : "Выбрать файл"}</span>
        </button>
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
          multiple={maxFiles > 1}
          accept={types.join(",")}
          data-testid="media-input"
          onChange={(e) => {
            addFiles(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
      </div>

      {errors.length > 0 && (
        <div className="gv-uploader-errors" role="alert">
          {errors.map((m) => (
            <p key={m}>
              <Icon name="alert" size={14} /> {m}
            </p>
          ))}
        </div>
      )}

      {(value.length > 0 || pending.length > 0) && (
        <ul className="gv-thumbs" aria-labelledby={`${id}-label`}>
          {value.map((media, i) => {
            const cover = media.id === currentCover;
            const src = mediaSrc(media, "thumb");
            return (
              <li
                key={media.id}
                className={cx("gv-thumb", cover && "is-cover")}
                draggable={!disabled}
                onDragStart={() => {
                  dragIndex.current = i;
                }}
                onDragEnd={() => {
                  dragIndex.current = null;
                }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (dragIndex.current !== null) move(dragIndex.current, i);
                  dragIndex.current = null;
                }}
              >
                {src && media.kind !== "document" ? (
                  <img src={src} alt={media.alt_text || `Фото ${i + 1}`} loading="lazy" />
                ) : (
                  <span className="gv-thumb-doc">
                    <Icon name="brief" size={22} />
                    <small>{media.original_filename || "Документ"}</small>
                  </span>
                )}
                <button type="button" className="gv-thumb-remove" aria-label={`Удалить фото ${i + 1}`} onClick={() => void remove(media, i)} disabled={disabled}>
                  <Icon name="close" size={14} />
                </button>
                {kind === "image" &&
                  (cover ? (
                    <span className="gv-thumb-cover">Обложка</span>
                  ) : (
                    <button type="button" className="gv-thumb-make-cover" onClick={() => makeCover(i)} disabled={disabled} aria-label={`Сделать фото ${i + 1} обложкой`}>
                      <Icon name="cover" size={13} />
                      <span>Обложка</span>
                    </button>
                  ))}
                {value.length > 1 && (
                  <span className="gv-thumb-order">
                    <button type="button" aria-label={`Переместить фото ${i + 1} левее`} onClick={() => move(i, i - 1)} disabled={disabled || i === 0}>
                      <Icon name="chevron-left" size={14} />
                    </button>
                    <button type="button" aria-label={`Переместить фото ${i + 1} правее`} onClick={() => move(i, i + 1)} disabled={disabled || i === value.length - 1}>
                      <Icon name="chevron-right" size={14} />
                    </button>
                  </span>
                )}
              </li>
            );
          })}
          {pending.map((p) => (
            <li key={p.key} className={cx("gv-thumb is-pending", p.stage === "error" && "is-error")}>
              {p.preview ? <img src={p.preview} alt="" /> : <span className="gv-thumb-doc"><Icon name="image" size={22} /></span>}
              <div className="gv-thumb-status" role={p.stage === "error" ? "alert" : "status"}>
                {p.stage === "error" ? (
                  <>
                    <small>{p.error}</small>
                    <button type="button" className="gv-thumb-retry" onClick={() => retry(p)}>
                      <Icon name="refresh" size={13} /> Повторить
                    </button>
                  </>
                ) : (
                  <>
                    <small>{p.stage === "processing" ? "Обрабатываем…" : `Загрузка ${Math.round(p.progress * 100)}%`}</small>
                    <span className="gv-progress" aria-hidden="true">
                      <span style={{ width: `${p.stage === "processing" ? 100 : Math.round(p.progress * 100)}%` }} />
                    </span>
                  </>
                )}
              </div>
              <button
                type="button"
                className="gv-thumb-remove"
                aria-label={p.stage === "error" ? `Убрать «${p.file.name}»` : `Отменить загрузку «${p.file.name}»`}
                onClick={() => {
                  p.controller.abort();
                  dropPending(p.key);
                }}
              >
                <Icon name="close" size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {video && <VideoSlot config={video} disabled={disabled} uploader={uploader} />}

      <span className="sr-only" aria-live="polite">
        {announce}
      </span>
    </div>
  );
}

/** Compact video tile (UX-09): poster, duration, filename, × delete; or a small «Добавить видео» slot. */
function VideoSlot({ config, disabled, uploader }: { config: VideoSlotConfig; disabled?: boolean; uploader: typeof uploadMedia }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<{ file: File; progress: number; stage: "uploading" | "processing" | "error"; error?: string; controller: AbortController } | null>(null);
  const types = config.accept?.length ? config.accept : MEDIA_LIMITS.video.types;

  const start = async (file: File) => {
    const problem = validateFile(file, "video", types);
    const controller = new AbortController();
    if (problem) {
      setState({ file, progress: 0, stage: "error", error: problem, controller });
      return;
    }
    setState({ file, progress: 0, stage: "uploading", controller });
    try {
      const media = await uploader(file, {
        purpose: config.purpose,
        kind: "video",
        signal: controller.signal,
        onProgress: (progress) => setState((s) => (s ? { ...s, progress } : s)),
        onStage: (stage) => setState((s) => (s ? { ...s, stage } : s)),
      });
      config.onChange(media);
      setState(null);
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return setState(null);
      setState((s) => (s ? { ...s, stage: "error", error: errorMessage(err, "Не удалось загрузить видео.") } : s));
    }
  };

  const media = config.value;
  const poster = media ? media.poster_url || media.thumbnail_url : null;

  return (
    <div className="gv-video-slot">
      <span className="gv-field-label">{config.label ?? "Видео"}</span>
      {media ? (
        <div className="gv-video-tile">
          <span className="gv-video-poster">
            {poster ? <img src={poster} alt="" /> : <Icon name="video" size={22} />}
            <span className="gv-video-play" aria-hidden="true">
              <Icon name="play" size={18} />
            </span>
            {media.duration_seconds ? <span className="gv-video-duration">{formatClock(media.duration_seconds)}</span> : null}
          </span>
          <span className="gv-video-meta">
            <b>{media.original_filename || "Видео"}</b>
            <small>
              {media.duration_seconds ? `${formatClock(media.duration_seconds)} · ` : ""}
              {media.size_bytes ? formatBytes(media.size_bytes) : ""}
            </small>
          </span>
          <button type="button" className="gv-thumb-remove" aria-label="Удалить видео" onClick={() => config.onChange(null)} disabled={disabled}>
            <Icon name="close" size={14} />
          </button>
        </div>
      ) : state ? (
        <div className={cx("gv-video-tile is-pending", state.stage === "error" && "is-error")}>
          <span className="gv-video-poster">
            <Icon name="video" size={22} />
          </span>
          <span className="gv-video-meta" role={state.stage === "error" ? "alert" : "status"}>
            <b>{state.file.name}</b>
            {state.stage === "error" ? (
              <>
                <small>{state.error}</small>
                <button type="button" className="gv-thumb-retry" onClick={() => void start(state.file)}>
                  <Icon name="refresh" size={13} /> Повторить
                </button>
              </>
            ) : (
              <>
                <small>{state.stage === "processing" ? "Обрабатываем видео…" : `Загрузка ${Math.round(state.progress * 100)}%`}</small>
                <span className="gv-progress" aria-hidden="true">
                  <span style={{ width: `${state.stage === "processing" ? 100 : Math.round(state.progress * 100)}%` }} />
                </span>
              </>
            )}
          </span>
          <button
            type="button"
            className="gv-thumb-remove"
            aria-label="Отменить загрузку видео"
            onClick={() => {
              state.controller.abort();
              setState(null);
            }}
          >
            <Icon name="close" size={14} />
          </button>
        </div>
      ) : (
        <button type="button" className="gv-video-add" onClick={() => inputRef.current?.click()} disabled={disabled}>
          <Icon name="video" size={20} />
          <span>
            <b>Добавить видео</b>
            <small>
              {acceptText(types)} до {formatBytes(MEDIA_LIMITS.video.maxBytes)} · одно видео
            </small>
          </span>
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        accept={types.join(",")}
        data-testid="video-input"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void start(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}
