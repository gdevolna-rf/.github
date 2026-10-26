"use client";
/**
 * «Фото и параметры» (BRD-08, SHAPERS_SCREENS §3.5): the model's gallery (cover first, ≤10), a separate video,
 * and the parameters of every active size variant with SKU, availability and price. Read-only; editing is the
 * pencil in the card (BRD-09). Self-views here are not analytics events (MET-08).
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { mediaSrc } from "@/lib/api/media";
import { shaperApi, shaperKeys, silhouetteSrc } from "@/lib/api/shaper";
import { cx } from "@/lib/cx";
import { formatMoney } from "@/lib/format";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ClampText } from "@/components/ui/ClampText";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { BoardSpecs } from "./ModelCard";

export function ModelViewer({ modelId, onClose, onEdit }: { modelId: string | null; onClose: () => void; onEdit?: (id: string) => void }) {
  const query = useQuery({
    queryKey: shaperKeys.model(modelId ?? ""),
    queryFn: () => shaperApi.model(modelId!),
    enabled: Boolean(modelId),
  });
  const [active, setActive] = useState<number | "video">(0);
  const model = query.data;
  const photos = model?.photos ?? [];
  const activeVariants = (model?.variants ?? []).filter((v) => v.is_active);
  const current = active === "video" ? null : photos[Math.min(active, Math.max(photos.length - 1, 0))];

  return (
    <Modal
      open={Boolean(modelId)}
      onClose={() => {
        setActive(0);
        onClose();
      }}
      size="wide"
      title={model?.name ?? "Фото и параметры"}
      description={model ? (activeVariants[0]?.sku ? `Артикул: ${activeVariants.map((v) => v.sku).join(", ")}` : "Артикул появится после добавления размера") : undefined}
      footer={
        model && onEdit && model.status !== "archived" ? (
          <Button variant="soft" icon="pencil" onClick={() => onEdit(model.id)}>
            Редактировать
          </Button>
        ) : undefined
      }
    >
      {query.isPending ? (
        <LoadingState label="Загружаем фото и параметры…" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : model ? (
        <div className="gv-sc-viewer">
          <div className="gv-sc-viewer-media">
            <div className="gv-sc-viewer-main">
              {active === "video" && model.video ? (
                <video src={model.video.url ?? undefined} poster={model.video.poster_url ?? undefined} controls playsInline preload="metadata" aria-label={`Видео доски ${model.name}`} />
              ) : current ? (
                <img src={mediaSrc(current.media, "full") ?? undefined} alt={current.media.alt_text || `${model.name} — фото ${photos.indexOf(current) + 1}`} />
              ) : (
                <img src={silhouetteSrc(model.board_type.silhouette)} alt={`Силуэт: ${model.board_type.name}`} className="is-silhouette" />
              )}
            </div>
            {(photos.length > 1 || model.video) && (
              <div className="gv-sc-viewer-thumbs" role="group" aria-label="Фото и видео модели">
                {photos.map((p, i) => (
                  <button
                    key={p.id}
                    type="button"
                    className={cx("gv-sc-viewer-thumb", active === i && "active")}
                    aria-pressed={active === i}
                    aria-label={`Фото ${i + 1}${p.is_cover ? " (обложка)" : ""}`}
                    onClick={() => setActive(i)}
                  >
                    <img src={mediaSrc(p.media, "thumb") ?? undefined} alt="" />
                  </button>
                ))}
                {model.video && (
                  <button
                    type="button"
                    className={cx("gv-sc-viewer-thumb is-video", active === "video" && "active")}
                    aria-pressed={active === "video"}
                    onClick={() => setActive("video")}
                  >
                    <Icon name="play" size={16} /> Видео доски
                  </button>
                )}
              </div>
            )}
          </div>
          <div className="gv-sc-viewer-specs">
            <p>
              <b>Тип:</b> {model.board_type.name}
            </p>
            <p className="gv-sc-viewer-status">
              <StatusBadge domain="availability" status={model.availability} />
              <StatusBadge domain="publication" status={model.status} />
            </p>
            {activeVariants.length === 0 ? (
              <p className="form-help">Размерных вариантов пока нет — добавьте их в редакторе модели.</p>
            ) : (
              <ul className="gv-sc-viewer-variants" aria-label="Размерные варианты">
                {activeVariants.map((v) => (
                  <li key={v.id}>
                    <span className="gv-article">Арт. {v.sku}</span>
                    <BoardSpecs dimensions={v.dimensions_display} volume={v.volume_display} fins={v.fin_system_label} />
                    <span className="gv-sc-viewer-line">
                      {v.material?.name ? `Материал: ${v.material.name}` : "Материал не указан"}
                      {v.construction ? ` · ${v.construction}` : ""}
                    </span>
                    <span className="gv-sc-viewer-line">
                      <b>{v.price ? formatMoney(v.price, v.currency) : "Цена по договорённости"}</b> · <StatusBadge domain="availability" status={v.availability} />
                      {v.made_to_order_days !== null ? ` · изготовление ${v.made_to_order_days} дн.` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {model.description ? (
              <ClampText lines={5}>{model.description}</ClampText>
            ) : (
              <p className="form-help">Описание не заполнено.</p>
            )}
            {model.tags.length > 0 && (
              <p className="gv-sc-tags">
                {model.tags.map((t) => (
                  <span key={t} className="gv-article">
                    #{t}
                  </span>
                ))}
              </p>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
