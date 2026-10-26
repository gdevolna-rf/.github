"use client";
/**
 * Shaper profile as a modal over the catalogue with its own URL (SHP-10, UX-12): rendered by the intercepting route
 * app/shapers/@modal/(.)[slug]. Closing (×, Esc, backdrop, Back button) returns to the catalogue via history.
 * Content is wrapped in `.gv-shapers` because the modal is portalled to <body> (outside the catalogue wrapper).
 */
import type { ReactNode } from "react";
import { RouteModal } from "@/components/ui";

export function ShaperProfileModal({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <RouteModal title={title} description={description} size="xl" className="gv-shaper-modal" closeLabel="Закрыть профиль шейпера">
      <div className="gv-shapers gv-shapers-embed">{children}</div>
    </RouteModal>
  );
}
