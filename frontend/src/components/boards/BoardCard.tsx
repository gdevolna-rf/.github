/**
 * «Все доски» card (SHAPERS_SCREENS §3.2, BRD-08/10): picture (cover or board-type silhouette), «Фото и параметры»
 * top-right, availability bottom-left, clickable title → model page, type · length, shaper + region, «О шейпере →»
 * (opens the profile modal over the catalogue, SHP-10), price, SKU chip, size/volume/fins lines, order CTA.
 */
import Link from "next/link";
import { Icon, StatusBadge } from "@/components/ui";
import { boardImage, boardTypeLine, placeLine, type BoardCard as BoardCardData } from "@/lib/api/boards";
import { formatMoney, plural } from "@/lib/format";
import { routes } from "@/lib/routes";
import { BoardOrderButton } from "./BoardActions";

export function boardPriceLabel(board: Pick<BoardCardData, "price_from" | "currency" | "variants_count">): string {
  const money = formatMoney(board.price_from, board.currency);
  if (!money) return "Цена по запросу";
  return board.variants_count > 1 ? `от ${money}` : money;
}

export function BoardCard({ board, headingLevel = 3 }: { board: BoardCardData; headingLevel?: 2 | 3 }) {
  const href = routes.board(board.id);
  const v = board.primary_variant;
  const H = headingLevel === 2 ? "h2" : "h3";
  const fins = v && v.fin_system && v.fin_system !== "none" ? v.fin_system_label : "";
  const more = board.variants_count > 1 ? board.variants_count - 1 : 0;
  return (
    <article className="model gv-board-card">
      <div className="model-visual">
        <Link href={href} className="gv-board-visual" tabIndex={-1} aria-hidden="true">
          <img src={boardImage(board)} alt="" loading="lazy" decoding="async" />
        </Link>
        <Link href={href} className="gv-gallery-top" aria-label={`Фото и параметры: ${board.name}`}>
          <Icon name="image" size={15} />
          <span>
            Фото и параметры
            {board.has_video ? " · видео" : ""}
          </span>
        </Link>
        <StatusBadge domain="availability" status={board.availability} className="gv-board-status" />
      </div>
      <div className="model-info">
        <H className="gv-board-name">
          <Link href={href} className="gv-board-title gv-clamp-2" title={board.name}>
            {board.name}
          </Link>
        </H>
        <div className="model-type">{boardTypeLine(board) || "Размер уточняется"}</div>
        <div className="model-owner">
          Шейпер: <strong>{board.shaper.name}</strong>
          {board.shaper.region && (
            <>
              <br />
              {placeLine(board.shaper.region, board.shaper.city)}
            </>
          )}
        </div>
        <Link href={routes.shaper(board.shaper.slug)} className="gv-maker-link" scroll={false}>
          <Icon name="user" size={14} /> О шейпере <Icon name="arrow" size={13} />
        </Link>
        <div className="model-price">{boardPriceLabel(board)}</div>
        <div className="gv-catalog-meta">
          {v?.sku && <span className="gv-article">Арт. {v.sku}</span>}
          {v && (
            <span className="gv-spec">
              <Icon name="ruler" size={14} />
              <span>
                {v.dimensions_display}
                {more > 0 ? ` · ещё ${more} ${plural(more, ["размер", "размера", "размеров"])}` : ""}
              </span>
            </span>
          )}
          {(board.volume_range_display || v?.volume_display) && (
            <span className="gv-spec">
              <Icon name="droplets" size={14} />
              <span>{board.volume_range_display || v?.volume_display}</span>
            </span>
          )}
          {fins && (
            <span className="gv-spec">
              <Icon name="fins" size={14} />
              <span>{fins}</span>
            </span>
          )}
        </div>
        <BoardOrderButton
          target={{ modelId: board.id, modelName: board.name, workshopId: board.shaper.id, workshopName: board.shaper.name, isOwn: board.is_own }}
          size="sm"
          className="gv-block"
        />
      </div>
    </article>
  );
}
