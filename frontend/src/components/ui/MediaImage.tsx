"use client";
import { useState } from "react";
import { cx } from "@/lib/cx";
import { mediaSrc } from "@/lib/api/media";
import type { Media } from "@/lib/api/types";
import { Icon } from "./Icon";

/**
 * Card/gallery image with a consistent crop (object-fit: cover, UX-11) and a soft placeholder when there is
 * no photo or it fails to load (DSN-06 «отсутствующие фотографии»). Always lazy (UX-16).
 */
export function MediaImage({
  media,
  src,
  alt,
  prefer = "full",
  placeholder = "Фото пока нет",
  className,
  imgClassName,
  width,
  height,
  priority,
}: {
  media?: Pick<Media, "url" | "thumbnail_url"> | null;
  src?: string | null;
  /** Meaningful alt text (what is on the photo), or "" if purely decorative. */
  alt: string;
  prefer?: "thumb" | "full";
  placeholder?: string;
  className?: string;
  imgClassName?: string;
  width?: number;
  height?: number;
  priority?: boolean;
}) {
  const url = src ?? mediaSrc(media ?? null, prefer);
  const [failed, setFailed] = useState(false);
  if (!url || failed) {
    return (
      <span className={cx("gv-media-placeholder", className)} role={alt ? "img" : undefined} aria-label={alt ? `${alt} — ${placeholder.toLowerCase()}` : undefined}>
        <Icon name="image" size={26} />
        <small>{placeholder}</small>
      </span>
    );
  }
  return (
    <img
      src={url}
      alt={alt}
      width={width}
      height={height}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      className={cx(imgClassName, className)}
      onError={() => setFailed(true)}
    />
  );
}
