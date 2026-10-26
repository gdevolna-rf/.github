"use client";
/**
 * Instructor photos & video (INS-12): MediaUploader grid (upload slot on top, thumbnails below, × delete,
 * «Обложка», reorder; mobile thumbnail grid) + one video tile. Changes are saved immediately through
 * POST/PATCH/DELETE me/instructor/media… (the gallery is not part of the card form).
 */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ik, instructorApi, type InstructorMediaItem } from "@/lib/api/instructorCabinet";
import type { Media } from "@/lib/api/types";
import { MediaUploader } from "@/components/ui/MediaUploader";
import { useToast } from "@/components/ui/Toast";

const MAX_ITEMS = 20;

export function InstructorMediaManager({ items, disabled }: { items: InstructorMediaItem[]; disabled?: boolean }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const serverPhotos = items.filter((i) => i.media.kind !== "video").map((i) => i.media);
  const videoItem = items.find((i) => i.media.kind === "video") ?? null;
  const [photos, setPhotos] = useState<Media[]>(serverPhotos);
  const known = useRef(new Map<string, number>());
  const signature = items.map((i) => `${i.id}:${i.media.id}:${i.position}`).join("|");

  useEffect(() => {
    known.current = new Map(items.map((i) => [i.media.id, i.id]));
    setPhotos(items.filter((i) => i.media.kind !== "video").map((i) => i.media));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ik.profile });

  const onPhotosChange = async (next: Media[]) => {
    setPhotos(next);
    try {
      const alive = new Set(known.current.values());
      const serverOrder = [...items].sort((a, b) => a.position - b.position).map((i) => i.id).filter((id) => alive.has(id));
      const added: number[] = [];
      for (const m of next) {
        if (!known.current.has(m.id)) {
          const item = await instructorApi.media.add(m.id);
          known.current.set(m.id, item.id);
          added.push(item.id);
        }
      }
      const actual = [...serverOrder, ...added];
      const photoIds = next.map((m) => known.current.get(m.id)).filter((x): x is number => typeof x === "number");
      const desired = [...photoIds, ...actual.filter((id) => !photoIds.includes(id))];
      if (desired.length === actual.length && desired.some((id, i) => id !== actual[i])) {
        await instructorApi.media.reorder(desired);
      }
      await refresh();
    } catch (err) {
      toast.error(err, { action: { label: "Обновить", onClick: () => void refresh() } });
      await refresh();
    }
  };

  const removeItem = async (media: Media) => {
    const id = known.current.get(media.id);
    if (id === undefined) return;
    await instructorApi.media.remove(id);
    known.current.delete(media.id);
    toast.success("Файл удалён из галереи");
    void refresh();
  };

  return (
    <section className="gv-ac-card lc-media" aria-labelledby="ins-media-title">
      <div className="gv-ac-card-head">
        <h3 id="ins-media-title">Фото и видео</h3>
      </div>
      <p>Первое фото — обложка карточки в каталоге. Изменения галереи сохраняются сразу. Можно до {MAX_ITEMS} файлов, видео — одно.</p>
      <MediaUploader
        purpose="profile_gallery"
        value={photos}
        onChange={(next) => void onPhotosChange(next)}
        onRemove={removeItem}
        maxFiles={MAX_ITEMS - 1}
        label="Фотографии с занятий"
        disabled={disabled}
        video={{
          purpose: "profile_gallery",
          label: "Видео (одно)",
          value: videoItem?.media ?? null,
          onChange: (media) => {
            void (async () => {
              try {
                if (videoItem && (!media || media.id !== videoItem.media.id)) {
                  await instructorApi.media.remove(videoItem.id);
                }
                if (media) await instructorApi.media.add(media.id);
                toast.success(media ? "Видео добавлено" : "Видео удалено");
              } catch (err) {
                toast.error(err);
              } finally {
                void refresh();
              }
            })();
          },
        }}
      />
    </section>
  );
}
