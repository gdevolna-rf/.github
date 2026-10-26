"use client";
/**
 * Spot photos (SPT-03, UX-13 «0 / 1 / 10 фото»): a large first photo with the favourite heart and the pencil
 * «Предложить правку» (SPT-07), thumbnails below and a lightbox (Modal; ←/→ keys, counter, author caption).
 * 0 photos → placeholder; 1 → single photo without a grid.
 */
import { useCallback, useEffect, useState, type KeyboardEvent } from "react";
import { HeartButton, Icon, IconButton, MediaImage, Modal } from "@/components/ui";
import { mediaSrc } from "@/lib/api/media";
import type { SpotPhoto } from "@/lib/api/spots";
import type { Media } from "@/lib/api/types";
import { plural, WORDS } from "@/lib/format";
import { SpotEditButton } from "./SpotEditButton";

export function galleryItems(photos: SpotPhoto[], cover: Media | null): Array<{ media: Media; caption: string; author?: string }> {
  const items = photos.map((p) => ({
    media: p.media,
    caption: p.caption,
    author: p.author && !p.author.is_deleted ? p.author.display_name : undefined,
  }));
  if (cover && !items.some((i) => i.media.id === cover.id)) items.unshift({ media: cover, caption: "", author: undefined });
  return items;
}

const MAX_THUMBS = 8;

export function SpotGallery({ spotId, name, photos, cover }: { spotId: string; name: string; photos: SpotPhoto[]; cover: Media | null }) {
  const items = galleryItems(photos, cover);
  const [index, setIndex] = useState<number | null>(null);
  const open = index !== null;
  const count = items.length;
  const go = useCallback((delta: number) => setIndex((i) => (i === null ? i : (i + delta + count) % count)), [count]);

  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      go(1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      go(-1);
    }
  };

  useEffect(() => {
    if (index !== null && index >= count) setIndex(null);
  }, [index, count]);

  const first = items[0];
  const current = index !== null ? items[index] : null;
  const altFor = (i: number) => items[i]?.media.alt_text || items[i]?.caption || `${name} — фото ${i + 1}`;
  const extra = count - 1 - MAX_THUMBS;

  return (
    <div className="gv-spot-gallery">
      <div className="gv-spot-hero">
        {first ? (
          <button type="button" className="gv-spot-hero-btn" onClick={() => setIndex(0)} aria-label={`Открыть фото: ${altFor(0)}${count > 1 ? `, всего ${count}` : ""}`}>
            <MediaImage media={first.media} alt={altFor(0)} className="gv-spot-hero-img" priority />
          </button>
        ) : (
          <MediaImage media={null} alt={`Спот «${name}»`} className="gv-spot-hero-img" />
        )}
        <div className="gv-spot-hero-actions">
          <HeartButton type="spot" id={spotId} name={name} />
          <SpotEditButton variant="photo" />
        </div>
        {count > 1 && (
          <span className="gv-spot-hero-count">
            <Icon name="photo" size={13} /> {count} {plural(count, WORDS.photo)}
          </span>
        )}
      </div>

      {count > 1 && (
        <ul className="gv-spot-thumbs" aria-label="Фотографии спота">
          {items.slice(1, 1 + MAX_THUMBS).map((item, n) => {
            const i = n + 1;
            const last = n === MAX_THUMBS - 1 && extra > 0;
            return (
              <li key={item.media.id}>
                <button type="button" onClick={() => setIndex(i)} aria-label={`Открыть фото ${i + 1} из ${count}${last ? ` (ещё ${extra})` : ""}`}>
                  <img src={mediaSrc(item.media, "thumb") ?? ""} alt="" loading="lazy" decoding="async" />
                  {last && <span className="gv-spot-thumb-more">+{extra}</span>}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <Modal open={open} onClose={() => setIndex(null)} title={`Фото ${index !== null ? index + 1 : ""} из ${count}`} size="xl" className="gv-lightbox">
        {current && (
          <div className="gv-lightbox-body" onKeyDown={onKey} tabIndex={-1}>
            <img src={mediaSrc(current.media, "full") ?? ""} alt={altFor(index ?? 0)} className="gv-lightbox-img" />
            {(current.caption || current.author) && (
              <p className="gv-lightbox-caption">
                {current.caption}
                {current.author ? `${current.caption ? " · " : ""}Автор: ${current.author}` : ""}
              </p>
            )}
            {count > 1 && (
              <div className="gv-lightbox-nav">
                <IconButton icon="chevron-left" label="Предыдущее фото" shape="round" onClick={() => go(-1)} />
                <span aria-live="polite">
                  {(index ?? 0) + 1} / {count}
                </span>
                <IconButton icon="chevron-right" label="Следующее фото" shape="round" onClick={() => go(1)} data-autofocus="" />
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
