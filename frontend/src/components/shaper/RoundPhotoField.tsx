"use client";
/**
 * Compact round photo (SHP-02: the workshop photo is round, small and sits left of the name; edited only here).
 * Presigned upload through uploadMedia (progress, processing, rejection, retry); the parent saves the id.
 */
import { useId, useRef, useState } from "react";
import { errorMessage } from "@/lib/api/errors";
import { uploadMedia, validateFile } from "@/lib/api/media";
import type { Media, MediaPurpose } from "@/lib/api/types";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";

export function RoundPhotoField({
  value,
  onChange,
  name,
  purpose = "org_logo",
  label = "Фото мастерской",
  disabled,
  uploader = uploadMedia,
}: {
  value: Media | null;
  onChange: (media: Media | null) => void;
  /** for initials when there is no photo */
  name: string;
  purpose?: MediaPurpose;
  label?: string;
  disabled?: boolean;
  uploader?: typeof uploadMedia;
}) {
  const id = useId().replace(/:/g, "");
  const input = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<{ progress: number; stage: "uploading" | "processing" } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastFile, setLastFile] = useState<File | null>(null);

  const start = async (file: File) => {
    const problem = validateFile(file, "image");
    setLastFile(file);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setState({ progress: 0, stage: "uploading" });
    try {
      const media = await uploader(file, {
        purpose,
        kind: "image",
        onProgress: (progress) => setState((s) => (s ? { ...s, progress } : s)),
        onStage: (stage) => setState((s) => (s ? { ...s, stage } : s)),
      });
      onChange(media);
    } catch (err) {
      setError(errorMessage(err, "Не удалось загрузить фото."));
    } finally {
      setState(null);
    }
  };

  return (
    <div className="gv-sc-photo">
      <span className="gv-sc-photo-ring">
        <Avatar media={value} name={name || "?"} size={76} alt={value ? label : ""} />
        {state && (
          <span className="gv-sc-photo-progress" role="status">
            {state.stage === "processing" ? "Обработка…" : `${Math.round(state.progress * 100)}%`}
          </span>
        )}
      </span>
      <div className="gv-sc-photo-actions">
        <span className="gv-field-label" id={`${id}-label`}>
          {label}
        </span>
        <div className="gv-sc-photo-buttons">
          <button type="button" className="secondary gv-sc-small-btn" onClick={() => input.current?.click()} disabled={disabled || Boolean(state)} aria-describedby={`${id}-hint`}>
            <Icon name="camera" size={15} /> {value ? "Заменить фото" : "Загрузить фото"}
          </button>
          {value && (
            <button type="button" className="plain gv-sc-danger-link" onClick={() => onChange(null)} disabled={disabled || Boolean(state)}>
              Удалить
            </button>
          )}
        </div>
        <small id={`${id}-hint`} className="gv-sc-photo-hint">
          JPG, PNG или WebP до 15 МБ · круглая миниатюра в каталоге
        </small>
        {error && (
          <p className="gv-field-error" role="alert">
            {error}{" "}
            {lastFile && !validateFile(lastFile, "image") && (
              <button type="button" className="plain" onClick={() => void start(lastFile)}>
                Повторить
              </button>
            )}
          </p>
        )}
      </div>
      <input
        ref={input}
        type="file"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        accept="image/jpeg,image/png,image/webp"
        data-testid="round-photo-input"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void start(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}
