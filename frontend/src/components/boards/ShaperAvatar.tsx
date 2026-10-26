/**
 * Round compact workshop photo left of the name (SHP-02): workshop logo, else the master's avatar, else initials
 * of the master (prototype «АВ» circle). Decorative — the name is always next to it.
 */
import { cx } from "@/lib/cx";
import { initials } from "@/lib/format";
import type { Media, PublicAccount } from "@/lib/api/types";

export function ShaperAvatar({
  logo,
  owner,
  name,
  size = 65,
  className,
}: {
  logo?: Media | null;
  owner?: Pick<PublicAccount, "avatar" | "display_name"> | null;
  name: string;
  size?: number;
  className?: string;
}) {
  const media = logo ?? owner?.avatar ?? null;
  const url = media ? media.thumbnail_url || media.url : null;
  return (
    <span className={cx("gv-shaper-avatar", className)} style={{ width: size, height: size, minWidth: size, fontSize: Math.round(size * 0.28) }} aria-hidden="true">
      {url ? <img src={url} alt="" loading="lazy" decoding="async" /> : initials(owner?.display_name || name)}
    </span>
  );
}
