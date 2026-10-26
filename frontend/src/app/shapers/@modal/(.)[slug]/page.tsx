/**
 * Intercepted /shapers/[slug] (soft navigation from the catalogue): the profile in a modal over the list.
 * The canonical standalone page is app/shapers/[slug]/page.tsx.
 */
import { ShaperProfile } from "@/components/boards/ShaperProfile";
import { ShaperProfileModal } from "@/components/boards/ShaperProfileModal";
import { RefreshError, serializeError } from "@/components/boards/RefreshError";
import { ViewTracker } from "@/components/boards/ViewTracker";
import "@/components/boards/boards.css";
import { EmptyState } from "@/components/ui";
import { placeLine, type ShaperDetail } from "@/lib/api/boards";
import { isApiError } from "@/lib/api/errors";
import { serverFetch } from "@/lib/api/server";
import { routes } from "@/lib/routes";

export default async function ShaperProfileModalPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let shaper: ShaperDetail | null = null;
  let error: unknown = null;
  try {
    shaper = await serverFetch<ShaperDetail>(`shapers/${encodeURIComponent(slug)}`, { tags: ["boards", `shaper:${slug}`] });
  } catch (err) {
    error = err;
  }

  if (!shaper) {
    const notFound = isApiError(error) && error.isNotFound;
    return (
      <ShaperProfileModal title={notFound ? "Мастерская не найдена" : "Профиль не загрузился"}>
        {notFound ? (
          <EmptyState title="Мастерская не найдена" text="Возможно, её сняли с публикации." action={{ label: "Ко всем шейперам", href: `${routes.shapers}?tab=shapers` }} />
        ) : (
          <RefreshError error={serializeError(error)} />
        )}
      </ShaperProfileModal>
    );
  }

  const place = placeLine(shaper.region, shaper.city);
  return (
    <ShaperProfileModal title={shaper.name} description={["Мастерская шейпера", place].filter(Boolean).join(" · ")}>
      <ViewTracker type="organization" id={shaper.id} />
      <ShaperProfile shaper={shaper} modelsHeading={3} />
    </ShaperProfileModal>
  );
}
