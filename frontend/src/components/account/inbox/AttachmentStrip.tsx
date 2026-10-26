"use client";
/** Preview strip of photos being attached (MSG-04): local thumbnail, progress, retry, × remove before sending. */
import { cx } from "@/lib/cx";
import { Icon } from "@/components/ui/Icon";
import type { useAttachmentDrafts } from "./useAttachmentDrafts";

export function AttachmentStrip({ files, label = "Фото к сообщению" }: { files: ReturnType<typeof useAttachmentDrafts>; label?: string }) {
  if (files.drafts.length === 0 && !files.problem) return null;
  return (
    <div className="acc-chat-drafts">
      {files.drafts.length > 0 && (
        <ul aria-label={label}>
          {files.drafts.map((d) => (
            <li key={d.key} className={cx("acc-draft", d.stage === "error" && "is-error")}>
              {d.preview ? <img src={d.preview} alt="" /> : <Icon name="image" size={20} />}
              <span className="acc-draft-name" title={d.file.name}>
                {d.file.name}
              </span>
              {d.stage === "uploading" || d.stage === "processing" ? (
                <span className="acc-draft-progress" role="status">
                  {d.stage === "processing" ? "Проверяем…" : `${Math.round(d.progress * 100)}%`}
                </span>
              ) : d.stage === "error" ? (
                <button type="button" className="acc-draft-retry" onClick={() => files.retry(d.key)} title={d.error}>
                  <Icon name="refresh" size={12} /> Повторить
                </button>
              ) : null}
              <button type="button" className="acc-draft-remove" aria-label={`Убрать фото «${d.file.name}»`} onClick={() => files.remove(d.key)}>
                <Icon name="close" size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {files.problem && (
        <p className="gv-field-error" role="alert">
          {files.problem}
        </p>
      )}
      {files.failed && (
        <p className="gv-field-hint" role="status">
          Фото с ошибкой не будут отправлены — повторите загрузку или уберите их.
        </p>
      )}
    </div>
  );
}
