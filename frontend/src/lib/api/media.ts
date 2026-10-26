/**
 * mediafiles: presigned upload flow (ARCHITECTURE §2 «Медиа», DATA-04, ATX-24).
 *   1. POST /media/uploads {kind, purpose, filename, content_type, size} → {id|media, upload_url}
 *   2. PUT file → upload_url (straight to MinIO through nginx; progress via XMLHttpRequest)
 *   3. POST /media/{id}/complete → processing
 *   4. poll GET /media/{id} until ready | rejected
 * Big videos never touch localStorage or Django (ATX-24).
 */
import { api } from "./client";
import { ApiError, networkError } from "./errors";
import type { Media, MediaKind, MediaPurpose } from "./types";

/** Mirror of backend MEDIA_LIMITS for instant feedback; the server stays the authority. */
export const MEDIA_LIMITS: Record<MediaKind, { maxBytes: number; types: string[] }> = {
  image: { maxBytes: 15 * 1024 * 1024, types: ["image/jpeg", "image/png", "image/webp"] },
  video: { maxBytes: 500 * 1024 * 1024, types: ["video/mp4", "video/webm", "video/quicktime"] },
  document: { maxBytes: 20 * 1024 * 1024, types: ["application/pdf", "image/jpeg", "image/png", "image/webp"] },
};

const KIND_LABEL: Record<MediaKind, string> = { image: "фото", video: "видео", document: "документ" };

export function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${Math.round((bytes / 1024 / 1024) * 10) / 10} МБ`.replace(".", ",");
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${bytes} Б`;
}

/** Guess the media kind from a File (used when one uploader accepts photos and video). */
export function kindOfFile(file: File): MediaKind {
  if (file.type.startsWith("video/")) return "video";
  if (file.type.startsWith("image/")) return "image";
  return "document";
}

/** Client-side check before any request. Returns a Russian error text or null. */
export function validateFile(file: File, kind: MediaKind, accept?: string[]): string | null {
  const limits = MEDIA_LIMITS[kind];
  const allowed = accept?.length ? accept : limits.types;
  const typeOk = allowed.some((t) => (t.endsWith("/*") ? file.type.startsWith(t.slice(0, -1)) : file.type === t));
  if (!typeOk) {
    const names = allowed.map((t) => t.split("/")[1]?.toUpperCase().replace("QUICKTIME", "MOV").replace("JPEG", "JPG")).join(", ");
    return `«${file.name}»: неподходящий формат. Подойдут ${names}.`;
  }
  if (file.size > limits.maxBytes) {
    return `«${file.name}»: файл больше ${formatBytes(limits.maxBytes)} — уменьшите ${KIND_LABEL[kind]} и попробуйте снова.`;
  }
  if (file.size === 0) return `«${file.name}»: пустой файл.`;
  return null;
}

export interface UploadTicket {
  id: string;
  uploadUrl: string;
  /** Extra headers required by the presigned PUT (if the backend returns them). */
  headers: Record<string, string>;
  media: Media | null;
}

function normalizeTicket(data: unknown): UploadTicket {
  const o = (data ?? {}) as Record<string, unknown>;
  const media = (o.media ?? o.asset ?? null) as Media | null;
  const id = String(o.id ?? media?.id ?? "");
  const uploadUrl = String(o.upload_url ?? o.url ?? "");
  const headers = (o.upload_headers ?? o.headers ?? {}) as Record<string, string>;
  if (!id || !uploadUrl) {
    throw new ApiError({ status: 500, code: "bad_upload_ticket", message: "Сервер не выдал ссылку для загрузки." });
  }
  return { id, uploadUrl, headers, media };
}

export const mediaApi = {
  createUpload: (input: { kind: MediaKind; purpose: MediaPurpose; file: File }) =>
    api
      .post<unknown>("media/uploads", {
        kind: input.kind,
        purpose: input.purpose,
        filename: input.file.name,
        content_type: input.file.type,
        size: input.file.size,
      })
      .then(normalizeTicket),
  complete: (id: string) => api.post<Media>(`media/${id}/complete`),
  get: (id: string) => api.get<Media>(`media/${id}`),
  privateUrl: (id: string) => api.get<{ url: string }>(`media/${id}/url`),
  remove: (id: string) => api.delete(`media/${id}`),
};

/** PUT the file to the presigned URL with progress (fetch has no upload progress). */
export function putFile(
  url: string,
  file: File,
  opts: { headers?: Record<string, string>; onProgress?: (fraction: number) => void; signal?: AbortSignal } = {},
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    // The presigned PUT must carry exactly the headers returned by POST /media/uploads
    // (Content-Type + `If-None-Match: *`, which makes the link one-time); fall back to Content-Type only.
    const headers =
      opts.headers && Object.keys(opts.headers).length ? opts.headers : { "Content-Type": file.type || "application/octet-stream" };
    for (const [k, v] of Object.entries(headers)) xhr.setRequestHeader(k, v);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) opts.onProgress?.(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        opts.onProgress?.(1);
        resolve();
      } else {
        reject(
          new ApiError({
            status: xhr.status,
            code: "upload_failed",
            message:
              xhr.status === 403 || xhr.status === 412
                ? "Ссылка для загрузки устарела или уже использована. Повторите загрузку."
                : xhr.status === 413
                  ? "Файл слишком большой для загрузки."
                  : "Не удалось загрузить файл в хранилище.",
          }),
        );
      }
    };
    xhr.onerror = () => reject(networkError());
    xhr.onabort = () => reject(new DOMException("Загрузка отменена", "AbortError"));
    if (opts.signal) {
      if (opts.signal.aborted) {
        xhr.abort();
        return;
      }
      opts.signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }
    xhr.send(file);
  });
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        reject(new DOMException("Загрузка отменена", "AbortError"));
      },
      { once: true },
    );
  });

/** Poll GET /media/{id} until processing ends. Rejected files throw ApiError(code "media_rejected"). */
export async function waitUntilReady(
  id: string,
  opts: { signal?: AbortSignal; timeoutMs?: number; intervalMs?: number } = {},
): Promise<Media> {
  const deadline = Date.now() + (opts.timeoutMs ?? 120_000);
  let interval = opts.intervalMs ?? 800;
  for (;;) {
    const media = await mediaApi.get(id);
    if (media.status === "ready") return media;
    if (media.status === "rejected" || media.status === "deleted") {
      throw new ApiError({
        status: 422,
        code: "media_rejected",
        message:
          (media as Media & { rejection_reason?: string }).rejection_reason ||
          `Файл «${media.original_filename || "без имени"}» не прошёл проверку. Загрузите другой.`,
      });
    }
    if (Date.now() > deadline) {
      throw new ApiError({ status: 0, code: "timeout", message: "Обработка файла заняла слишком много времени. Попробуйте ещё раз." });
    }
    await sleep(interval, opts.signal);
    interval = Math.min(interval * 1.5, 3000);
  }
}

export interface UploadOptions {
  purpose: MediaPurpose;
  kind?: MediaKind;
  onProgress?: (fraction: number) => void;
  onStage?: (stage: "uploading" | "processing") => void;
  signal?: AbortSignal;
}

/** Full presigned flow for one file → ready Media. */
export async function uploadMedia(file: File, opts: UploadOptions): Promise<Media> {
  const kind = opts.kind ?? kindOfFile(file);
  let ticket = await mediaApi.createUpload({ kind, purpose: opts.purpose, file });
  opts.onStage?.("uploading");
  try {
    await putFile(ticket.uploadUrl, file, { headers: ticket.headers, onProgress: opts.onProgress, signal: opts.signal });
  } catch (err) {
    // Upload links are one-time and expire after 15 min: an expired/used link (403/412) gets one fresh ticket.
    if (!(err instanceof ApiError) || (err.status !== 403 && err.status !== 412)) throw err;
    ticket = await mediaApi.createUpload({ kind, purpose: opts.purpose, file });
    await putFile(ticket.uploadUrl, file, { headers: ticket.headers, onProgress: opts.onProgress, signal: opts.signal });
  }
  opts.onStage?.("processing");
  const completed = await mediaApi.complete(ticket.id);
  if (completed && completed.status === "ready") return completed;
  return waitUntilReady(ticket.id, { signal: opts.signal });
}

/** Public URL of a media object (thumbnail first for grids). */
export function mediaSrc(media: Pick<Media, "url" | "thumbnail_url"> | null | undefined, prefer: "thumb" | "full" = "full") {
  if (!media) return null;
  return prefer === "thumb" ? media.thumbnail_url || media.url : media.url || media.thumbnail_url;
}
