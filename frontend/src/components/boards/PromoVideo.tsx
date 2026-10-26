"use client";
/**
 * Shaper promo video (SHP-03): one slot, played in the public card. In the catalogue card a small «Промо» button
 * opens the player for THIS shaper (prototype bug #11 — it always played your own video). Closing pauses playback
 * because the <video> unmounts with the modal.
 */
import { useState } from "react";
import { Button, Modal } from "@/components/ui";
import type { Media } from "@/lib/api/types";
import { formatClock } from "@/lib/format";

export function VideoPlayer({ video, title, autoPlay }: { video: Media; title: string; autoPlay?: boolean }) {
  if (!video.url) {
    return <p className="muted">Видео обрабатывается — загляните чуть позже.</p>;
  }
  return (
    <video
      className="gv-video-player"
      src={video.url}
      poster={video.poster_url ?? undefined}
      controls
      playsInline
      preload="metadata"
      autoPlay={autoPlay}
      aria-label={title}
    >
      <track kind="captions" />
    </video>
  );
}

export function PromoVideoButton({ video, shaperName }: { video: Media; shaperName: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="soft" size="sm" icon="play" className="secondary gv-promo-link" onClick={() => setOpen(true)}>
        Промо{video.duration_seconds ? ` · ${formatClock(video.duration_seconds)}` : ""}
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title={`Промо-видео: ${shaperName}`} size="wide">
        <VideoPlayer video={video} title={`Промо-видео мастерской ${shaperName}`} autoPlay />
      </Modal>
    </>
  );
}
