"use client";
/**
 * Photo attachments of the chat composer (MSG-04): pick from the phone/gallery, local preview, upload right away
 * through the presigned flow (purpose `message_attachment`, the MediaUploader logic from lib/api/media.ts),
 * remove before sending. At most 10 images per message (server limit).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "@/lib/api/errors";
import { uploadMedia, validateFile } from "@/lib/api/media";
import type { Media, MediaPurpose } from "@/lib/api/types";

export const MAX_ATTACHMENTS = 10;
export const ATTACHMENT_TYPES = ["image/jpeg", "image/png", "image/webp"];

export interface AttachmentDraft {
  key: string;
  file: File;
  preview: string | null;
  progress: number;
  stage: "uploading" | "processing" | "ready" | "error";
  media?: Media;
  error?: string;
  controller: AbortController;
}

export function useAttachmentDrafts({
  purpose = "message_attachment",
  max = MAX_ATTACHMENTS,
  uploader = uploadMedia,
}: { purpose?: MediaPurpose; max?: number; uploader?: typeof uploadMedia } = {}) {
  const [drafts, setDrafts] = useState<AttachmentDraft[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const ref = useRef(drafts);
  ref.current = drafts;

  useEffect(
    () => () => {
      ref.current.forEach((d) => {
        d.controller.abort();
        if (d.preview) URL.revokeObjectURL?.(d.preview);
      });
    },
    [],
  );

  const patch = (key: string, data: Partial<AttachmentDraft>) => setDrafts((list) => list.map((d) => (d.key === key ? { ...d, ...data } : d)));

  const run = useCallback(
    async (draft: AttachmentDraft) => {
      try {
        const media = await uploader(draft.file, {
          purpose,
          kind: "image",
          signal: draft.controller.signal,
          onProgress: (progress) => patch(draft.key, { progress }),
          onStage: (stage) => patch(draft.key, { stage }),
        });
        patch(draft.key, { stage: "ready", progress: 1, media });
      } catch (err) {
        if ((err as Error)?.name === "AbortError") return;
        patch(draft.key, { stage: "error", error: errorMessage(err, "Не удалось загрузить фото.") });
      }
    },
    [uploader, purpose],
  );

  const add = useCallback(
    (files: File[]) => {
      const problems: string[] = [];
      const room = max - ref.current.length;
      const accepted: File[] = [];
      for (const file of files) {
        const err = validateFile(file, "image", ATTACHMENT_TYPES);
        if (err) problems.push(err);
        else accepted.push(file);
      }
      if (accepted.length > room) problems.push(`Можно приложить не больше ${max} фото.`);
      setProblem(problems.length ? problems.join(" ") : null);
      const next = accepted.slice(0, Math.max(0, room)).map((file, i) => ({
        key: `${Date.now()}-${i}-${file.name}`,
        file,
        preview: typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : null,
        progress: 0,
        stage: "uploading" as const,
        controller: new AbortController(),
      }));
      if (!next.length) return;
      setDrafts((list) => [...list, ...next]);
      next.forEach((d) => void run(d));
    },
    [run, max],
  );

  const remove = useCallback((key: string) => {
    setDrafts((list) => {
      const d = list.find((x) => x.key === key);
      if (d) {
        d.controller.abort();
        if (d.preview) URL.revokeObjectURL?.(d.preview);
      }
      return list.filter((x) => x.key !== key);
    });
  }, []);

  const retry = useCallback(
    (key: string) => {
      const d = ref.current.find((x) => x.key === key);
      if (!d) return;
      const fresh = { ...d, stage: "uploading" as const, progress: 0, error: undefined, controller: new AbortController() };
      patch(key, fresh);
      void run(fresh);
    },
    [run],
  );

  /** Hand the ready media + previews over to the message (previews are then owned by the pending bubble). */
  const take = useCallback(() => {
    const ready = ref.current.filter((d) => d.stage === "ready" && d.media);
    setDrafts([]);
    setProblem(null);
    ref.current
      .filter((d) => !(d.stage === "ready" && d.media))
      .forEach((d) => {
        d.controller.abort();
        if (d.preview) URL.revokeObjectURL?.(d.preview);
      });
    return { media: ready.map((d) => d.media as Media), previews: ready.map((d) => d.preview).filter(Boolean) as string[] };
  }, []);

  return {
    max,
    drafts,
    problem,
    clearProblem: () => setProblem(null),
    add,
    remove,
    retry,
    take,
    uploading: drafts.some((d) => d.stage === "uploading" || d.stage === "processing"),
    failed: drafts.some((d) => d.stage === "error"),
    readyCount: drafts.filter((d) => d.stage === "ready").length,
  };
}
