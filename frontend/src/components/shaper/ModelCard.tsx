"use client";
/**
 * Own model card in «Мои доски» (BRD-08/09/10): availability + publication badges, a clear pencil edit button
 * (BRD-09), a clickable name and picture opening «Фото и параметры» (BRD-08), SKU chip, size/volume/fins icons
 * on one stroke grid (BRD-10), price, variants and media links. No photo → the board type silhouette.
 */
import { formatMoney, formatPriceFrom, plural } from "@/lib/format";
import { mediaSrc } from "@/lib/api/media";
import { silhouetteSrc, type BoardModelCard } from "@/lib/api/shaper";
import { StatusBadge } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";

export function BoardSpecs({ dimensions, volume, fins }: { dimensions?: string | null; volume?: string | null; fins?: string | null }) {
  if (!dimensions && !volume && !fins) return null;
  return (
    <div className="gv-sc-specs">
      {dimensions && (
        <span className="gv-spec" title="Длина × ширина × толщина">
          <Icon name="ruler" className="ic" size={14} />
          <span className="sr-only">Размеры: </span>
          {dimensions}
        </span>
      )}
      {volume && (
        <span className="gv-spec" title="Объём">
          <Icon name="droplets" className="ic" size={14} />
          <span className="sr-only">Объём: </span>
          {volume}
        </span>
      )}
      {fins && (
        <span className="gv-spec" title="Вид закладных">
          <Icon name="fins" className="ic" size={14} />
          <span className="sr-only">Закладные: </span>
          {fins}
        </span>
      )}
    </div>
  );
}

export function modelPrice(model: Pick<BoardModelCard, "price_from" | "currency" | "variants_count">): string {
  if (!model.price_from) return "Цена по договорённости";
  return model.variants_count > 1 ? formatPriceFrom(model.price_from, model.currency) : formatMoney(model.price_from, model.currency);
}

export function ModelCard({
  model,
  onEdit,
  onView,
  readOnly,
}: {
  model: BoardModelCard;
  onEdit?: () => void;
  onView: () => void;
  readOnly?: boolean;
}) {
  const cover = model.cover ? mediaSrc(model.cover, "thumb") : null;
  const primary = model.primary_variant;
  const more = model.variants_count - 1;
  return (
    <article className="model gv-sc-model" aria-labelledby={`model-${model.id}`}>
      <div className="model-visual">
        <button type="button" className="gv-sc-visual-btn" onClick={onView} aria-label={`Фото и параметры: ${model.name}`} tabIndex={-1}>
          <img src={cover ?? silhouetteSrc(model.board_type.silhouette)} alt="" loading="lazy" className={cover ? undefined : "is-silhouette"} />
        </button>
        <div className="gv-sc-badges">
          <StatusBadge domain="availability" status={model.availability} />
          {model.status !== "published" && <StatusBadge domain="publication" status={model.status} />}
        </div>
        {!readOnly && onEdit && (
          <button type="button" className="model-menu" aria-label={`Редактировать «${model.name}»`} title="Редактировать карточку доски" onClick={onEdit}>
            <Icon name="pencil" className="ic" size={18} />
          </button>
        )}
      </div>
      <div className="model-info">
        <h3 className="gv-sc-model-title" id={`model-${model.id}`}>
          <button type="button" className="gv-board-title gv-clamp-2" onClick={onView} title={model.name}>
            {model.name}
          </button>
        </h3>
        <div className="model-type">
          {model.board_type.name}
          {primary?.sku ? (
            <span className="gv-article" title="Артикул: код шейпера · тип · длина · ширина · номер модели">
              Арт. {primary.sku}
            </span>
          ) : (
            <span className="gv-sc-noarticle">Добавьте размер — артикул присвоится автоматически</span>
          )}
          {more > 0 && <span className="gv-sc-more-variants">+{more} {plural(more, ["вариант", "варианта", "вариантов"])}</span>}
        </div>
        <BoardSpecs
          dimensions={more > 0 ? model.length_range_display : primary?.dimensions_display}
          volume={more > 0 ? model.volume_range_display : primary?.volume_display}
          fins={primary?.fin_system_label}
        />
        <div className="model-price">{modelPrice(model)}</div>
        <div className="model-foot">
          {model.photos_count > 1 || model.has_video ? (
            <button type="button" className="gv-gallery-link" onClick={onView}>
              <Icon name="photo" size={13} /> {model.photos_count} фото{model.has_video ? " · видео" : ""}
            </button>
          ) : (
            <span>{model.photos_count ? "1 фото" : "Фото пока нет"}</span>
          )}
          {model.is_public ? (
            <a href={model.public_url} className="gv-sc-public-link" target="_blank" rel="noreferrer">
              На сайте <Icon name="external" size={12} />
            </a>
          ) : (
            <span className="gv-sc-hidden-note">Не видна в каталоге</span>
          )}
        </div>
      </div>
    </article>
  );
}
