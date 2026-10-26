"use client";
/**
 * Image of a private media object (chat attachments, handover photos): public files use their URL, private ones
 * get a short-lived presigned link from GET /media/{id}/url (ATX-23). A ready-made `signedUrl` from the API is
 * used first; when it expires (2 min) the image re-requests a fresh link once.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { mediaApi } from "@/lib/api/media";
import { api } from "@/lib/api/client";
import type { Media } from "@/lib/api/types";
import { cx } from "@/lib/cx";
import { Icon } from "@/components/ui/Icon";

type Variant = "original" | "thumbnail";

export function privateMediaUrl(id: string, variant: Variant = "original") {
  return api.get<{ url: string; expires_at: string | null }>(`media/${id}/url`, { query: { variant: variant === "thumbnail" ? "thumbnail" : undefined } });
}

/** Open the full-size private file in a new tab (fresh presigned link on every click). */
export async function openPrivateMedia(media: Pick<Media, "id" | "url">): Promise<void> {
  // open synchronously (popup blockers), then point the tab at the fresh presigned link
  const win = typeof window !== "undefined" ? window.open("", "_blank") : null;
  if (win) win.opener = null;
  try {
    const url = media.url || (await mediaApi.privateUrl(media.id)).url;
    if (win) win.location.href = url;
    else window.location.assign(url);
  } catch (err) {
    win?.close();
    throw err;
  }
}

export function PrivateImage({
  media,
  signedUrl,
  variant = "thumbnail",
  alt,
  className,
}: {
  media: Pick<Media, "id" | "url" | "thumbnail_url" | "status">;
  signedUrl?: string | null;
  variant?: Variant;
  alt: string;
  className?: string;
}) {
  const publicUrl = variant === "thumbnail" ? media.thumbnail_url || media.url : media.url;
  const [expired, setExpired] = useState(false);
  const needsFetch = !publicUrl && (!signedUrl || expired);
  const query = useQuery({
    queryKey: ["media", media.id, "url", variant],
    queryFn: async () => {
      try {
        return (await privateMediaUrl(media.id, variant)).url;
      } catch (err) {
        if (variant === "thumbnail") return (await privateMediaUrl(media.id, "original")).url;
        throw err;
      }
    },
    enabled: needsFetch && media.status === "ready",
    staleTime: 90_000,
    gcTime: 110_000,
    retry: false,
  });
  const src = publicUrl || (!expired ? signedUrl : null) || query.data || null;
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <span className={cx("gv-media-placeholder acc-private-img", className)} role="img" aria-label={alt}>
        <Icon name={media.status === "ready" ? "image" : "clock"} size={22} />
        <small>{media.status === "ready" ? (query.isFetching ? "Загружаем…" : "Фото") : "Проверяем файл…"}</small>
      </span>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      className={className}
      onError={() => {
        if (!expired && signedUrl && !publicUrl) setExpired(true);
        else setFailed(true);
      }}
    />
  );
}
