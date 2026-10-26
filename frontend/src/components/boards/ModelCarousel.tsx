"use client";
/**
 * Models scrolled INSIDE a shaper card without opening the profile (SHP-09): horizontal scroll-snap row, 3 tiles
 * on desktop / 2 on phones, arrows move by two tiles and are disabled at the ends (prototype bug #14 fixed).
 * Tiles link to the model page «Фото и параметры». Swipe/trackpad scrolling works natively; arrows are buttons.
 */
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Icon } from "@/components/ui";
import { boardImage, type BoardTile } from "@/lib/api/boards";
import { formatMoney, pluralize, WORDS } from "@/lib/format";
import { routes } from "@/lib/routes";

export function ModelCarousel({ models, total, shaperName, shaperSlug }: { models: BoardTile[]; total: number; shaperName: string; shaperSlug: string }) {
  const listRef = useRef<HTMLUListElement>(null);
  const [edges, setEdges] = useState({ start: true, end: true });
  const listId = useId();

  const update = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    setEdges({ start: el.scrollLeft <= 2, end: el.scrollLeft >= max - 2 });
  }, []);

  useEffect(() => {
    update();
    const el = listRef.current;
    if (!el) return;
    el.addEventListener("scroll", update, { passive: true });
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(update) : null;
    ro?.observe(el);
    return () => {
      el.removeEventListener("scroll", update);
      ro?.disconnect();
    };
  }, [update, models.length]);

  const scrollBy = (dir: 1 | -1) => {
    const el = listRef.current;
    if (!el) return;
    const tile = el.querySelector<HTMLElement>("li");
    const step = tile ? (tile.offsetWidth + 6) * 2 : el.clientWidth * 0.66;
    el.scrollBy({ left: dir * step, behavior: "smooth" });
  };

  return (
    <div className="gv-maker-showcase">
      <div className="gv-maker-showcase-head">
        <span>
          Доски мастерской <small>{pluralize(total, WORDS.model)}</small>
        </span>
        {models.length > 1 && (
          <span className="gv-carousel-nav">
            <button type="button" aria-label={`Предыдущие модели: ${shaperName}`} aria-controls={listId} disabled={edges.start} onClick={() => scrollBy(-1)}>
              <Icon name="chevron-left" size={16} />
            </button>
            <button type="button" aria-label={`Следующие модели: ${shaperName}`} aria-controls={listId} disabled={edges.end} onClick={() => scrollBy(1)}>
              <Icon name="chevron-right" size={16} />
            </button>
          </span>
        )}
      </div>
      {models.length === 0 ? (
        <p className="gv-maker-empty">Модели пока не опубликованы</p>
      ) : (
        <ul id={listId} ref={listRef} className="gv-maker-boardline" aria-label={`Доски мастерской ${shaperName}`}>
          {models.map((m) => (
            <li key={m.id} className="gv-maker-board-item">
              <Link href={routes.board(m.id)} className="gv-maker-board" title={m.name}>
                <img src={boardImage(m)} alt="" loading="lazy" decoding="async" />
                <strong>{m.name}</strong>
                <span>{m.board_type?.name}</span>
                <span className="gv-maker-board-price">{formatMoney(m.price_from, m.currency) || "Цена по запросу"}</span>
              </Link>
            </li>
          ))}
          {total > models.length && (
            <li className="gv-maker-board-item">
              <Link href={routes.shaper(shaperSlug)} className="gv-maker-board gv-maker-board-more" scroll={false}>
                <Icon name="grid" size={22} />
                <strong>Все {pluralize(total, WORDS.model)}</strong>
                <span>в профиле мастерской</span>
              </Link>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
