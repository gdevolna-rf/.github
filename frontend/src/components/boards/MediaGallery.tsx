"use client";
/**
 * Detail-page gallery (BRD-03/04/08, UX-08/09, UX-13 «0/1/10 фото»): big picture + thumbnails (cover first, ≤10),
 * the video as a SEPARATE compact tile after the photos (never mixed into the photo row), prev/next buttons and
 * arrow keys. 0 photos → a fallback picture (board silhouette / illustration) with an honest caption;
 * 1 photo → no thumbnail row. Used by boards, rentals and the shop.
 */
import { useCallback, useId, useState, type KeyboardEvent } from "react";
import { Icon } from "@/components/ui";
import type { Media } from "@/lib/api/types";
import { cx } from "@/lib/cx";
import { formatClock } from "@/lib/format";

export interface GalleryPhoto {
  id: string | number;
  media: Media;
}

export function MediaGallery({
  photos,
  video,
  title,
  fallback,
  max = 10,
  contain = true,
  className,
}: {
  photos: GalleryPhoto[];
  video?: Media | null;
  /** Object name for alt texts: «Pacific Fish — фото 2 из 4». */
  title: string;
  fallback: { src: string; caption: string };
  max?: number;
  /** contain = boards (whole outline visible); cover = photos of things. */
  contain?: boolean;
  className?: string;
}) {
  const items = photos.filter((p) => p.media && (p.media.url || p.media.thumbnail_url)).slice(0, max);
  const hasVideo = Boolean(video && (video.url || video.poster_url));
  const [index, setIndex] = useState(0);
  const [showVideo, setShowVideo] = useState(items.length === 0 && hasVideo);
  const regionId = useId();
  const count = items.length;
  const current = items[Math.min(index, Math.max(count - 1, 0))];

  const go = useCallback(
    (delta: number) => {
      if (count < 2) return;
      setShowVideo(false);
      setIndex((i) => (i + delta + count) % count);
    },
    [count],
  );

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      go(1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      go(-1);
    }
  };

  const label = (i: number) => `${title} — фото ${i + 1} из ${count}`;

  return (
    <div className={cx("gv-gallery", className)}>
      <div
        className={cx("gv-gallery-main", contain ? "is-contain" : "is-cover")}
        id={regionId}
        role="group"
        aria-roledescription="галерея"
        aria-label={`Фото: ${title}`}
        tabIndex={count > 1 ? 0 : -1}
        onKeyDown={onKeyDown}
      >
        {showVideo && video ? (
          video.url ? (
            <video src={video.url} poster={video.poster_url ?? undefined} controls playsInline preload="metadata" autoPlay aria-label={`Видео: ${title}`}>
              <track kind="captions" />
            </video>
          ) : (
            <p className="gv-gallery-note">Видео обрабатывается — загляните чуть позже.</p>
          )
        ) : current ? (
          <img src={current.media.url || current.media.thumbnail_url || ""} alt={current.media.alt_text || label(index)} decoding="async" />
        ) : (
          <figure className="gv-gallery-fallback">
            <img src={fallback.src} alt="" />
            <figcaption>{fallback.caption}</figcaption>
          </figure>
        )}
        {count > 1 && !showVideo && (
          <>
            <button type="button" className="gv-gallery-nav is-prev" aria-label="Предыдущее фото" aria-controls={regionId} onClick={() => go(-1)}>
              <Icon name="chevron-left" size={20} />
            </button>
            <button type="button" className="gv-gallery-nav is-next" aria-label="Следующее фото" aria-controls={regionId} onClick={() => go(1)}>
              <Icon name="chevron-right" size={20} />
            </button>
            <span className="gv-gallery-counter" aria-live="polite">
              {index + 1} / {count}
            </span>
          </>
        )}
      </div>

      {(count > 1 || (hasVideo && count > 0)) && (
        <div className="gv-gallery-thumbs" aria-label="Миниатюры">
          {count > 1 &&
            items.map((p, i) => (
              <button
                key={p.id}
                type="button"
                className={cx("gv-gallery-thumb", !showVideo && i === index && "active")}
                aria-label={label(i)}
                aria-pressed={!showVideo && i === index}
                aria-controls={regionId}
                onClick={() => {
                  setShowVideo(false);
                  setIndex(i);
                }}
              >
                <img src={p.media.thumbnail_url || p.media.url || ""} alt="" loading="lazy" decoding="async" />
              </button>
            ))}
          {hasVideo && video && (
            <button
              type="button"
              className={cx("gv-gallery-video-tile", showVideo && "active")}
              aria-pressed={showVideo}
              aria-controls={regionId}
              onClick={() => setShowVideo(true)}
            >
              {video.poster_url ? <img src={video.poster_url} alt="" loading="lazy" /> : null}
              <span className="gv-gallery-video-label">
                <Icon name="play" size={14} /> Видео{video.duration_seconds ? ` · ${formatClock(video.duration_seconds)}` : ""}
              </span>
            </button>
          )}
        </div>
      )}
      {count === 0 && hasVideo && !showVideo && (
        <button type="button" className="secondary gv-gallery-video-only" onClick={() => setShowVideo(true)}>
          <Icon name="play" size={14} /> Смотреть видео
        </button>
      )}
    </div>
  );
}
