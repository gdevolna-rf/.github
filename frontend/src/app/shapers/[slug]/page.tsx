/**
 * Standalone shaper profile /shapers/[slug] (SHP-10 deep link, NAV-05/ATX-32 SEO). Direct visits and refreshes
 * land here; navigation from the catalogue opens the same content in a modal (@modal/(.)[slug]).
 */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ShaperProfile } from "@/components/boards/ShaperProfile";
import { ViewTracker } from "@/components/boards/ViewTracker";
import "@/components/boards/boards.css";
import { placeLine, type ShaperDetail } from "@/lib/api/boards";
import { isApiError } from "@/lib/api/errors";
import { serverFetch } from "@/lib/api/server";
import { truncate } from "@/lib/format";
import { routes } from "@/lib/routes";
import { absoluteUrl, buildMetadata, jsonLd } from "@/lib/seo";

export const revalidate = 300;

type Props = { params: Promise<{ slug: string }> };

async function getShaper(slug: string): Promise<ShaperDetail> {
  try {
    return await serverFetch<ShaperDetail>(`shapers/${encodeURIComponent(slug)}`, { tags: ["boards", `shaper:${slug}`] });
  } catch (err) {
    if (isApiError(err) && err.isNotFound) notFound();
    throw err;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  try {
    const shaper = await serverFetch<ShaperDetail>(`shapers/${encodeURIComponent(slug)}`, { tags: ["boards", `shaper:${slug}`] });
    const place = placeLine(shaper.region, shaper.city);
    return buildMetadata({
      title: `${shaper.name} — мастерская шейпера${place ? `, ${place}` : ""}`,
      description: truncate(shaper.short_description || shaper.description || `Доски ручной работы мастерской ${shaper.name}.`, 160),
      path: routes.shaper(slug),
      image: shaper.cover?.url ?? shaper.models[0]?.cover?.url ?? null,
      type: "profile",
    });
  } catch {
    return buildMetadata({ title: "Мастерская шейпера", path: routes.shaper(slug) });
  }
}

export default async function ShaperPage({ params }: Props) {
  const { slug } = await params;
  const shaper = await getShaper(slug);
  const place = placeLine(shaper.region, shaper.city);
  return (
    <div className="wrap">
      <div className="gv-shapers gv-shapers-page">
        <nav className="gv-breadcrumbs" aria-label="Навигационная цепочка">
          <Link href={routes.home}>Главная</Link> <span aria-hidden="true">/</span> <Link href={`${routes.shapers}?tab=shapers`}>Шейперы</Link>{" "}
          <span aria-hidden="true">/</span> <span aria-current="page">{shaper.name}</span>
        </nav>
        <div className="card gv-shaper-page-card">
          <p className="gv-profile-topline">ГДЕВОЛНА · МАСТЕРСКАЯ</p>
          <h1 className="gv-shaper-page-title">{shaper.name}</h1>
          {place && <p className="gv-region">{place}</p>}
          <ShaperProfile shaper={shaper} modelsHeading={2} />
        </div>
      </div>
      <ViewTracker type="organization" id={shaper.id} />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={jsonLd({
          "@context": "https://schema.org",
          "@type": "LocalBusiness",
          name: shaper.name,
          url: absoluteUrl(routes.shaper(shaper.slug)),
          description: shaper.short_description || undefined,
          address: shaper.region ? { "@type": "PostalAddress", addressRegion: shaper.region.name, addressLocality: shaper.city || undefined } : undefined,
          ...(shaper.rating_count > 0
            ? { aggregateRating: { "@type": "AggregateRating", ratingValue: shaper.rating_avg, reviewCount: shaper.rating_count } }
            : {}),
        })}
      />
    </div>
  );
}
