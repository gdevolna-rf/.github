import { cx } from "@/lib/cx";
import { initials } from "@/lib/format";
import type { Media } from "@/lib/api/types";
import { mediaSrc } from "@/lib/api/media";

export interface AvatarProps {
  /** Media object or a URL; falls back to initials. */
  media?: Media | null;
  src?: string | null;
  name?: string | null;
  size?: number;
  /** Decorative by default (the name is shown next to it). Pass alt when the avatar stands alone. */
  alt?: string;
  className?: string;
}

/** Round photo or initials (cabinet hero style: #d9f1ff circle, #0875aa letters). */
export function Avatar({ media, src, name, size = 40, alt = "", className }: AvatarProps) {
  const url = src ?? mediaSrc(media ?? null, size <= 64 ? "thumb" : "full");
  return (
    <span
      className={cx("gv-avatar", className)}
      style={{ width: size, height: size, fontSize: Math.max(11, Math.round(size * 0.4)) }}
      role={alt ? "img" : undefined}
      aria-label={alt || undefined}
      aria-hidden={alt ? undefined : true}
    >
      {url ? <img src={url} alt="" loading="lazy" decoding="async" /> : <span>{initials(name)}</span>}
    </span>
  );
}
