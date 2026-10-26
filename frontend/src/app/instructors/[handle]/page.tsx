/**
 * /instructors/[handle] — public instructor profile (INS-01…04, INS-08, NAV-05). SSR + ISR; old handles answer
 * `{redirect}` → permanent redirect to the new URL; unpublished/unknown → 404.
 */
import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { cache } from "react";
import { InstructorProfile } from "@/components/instructors/InstructorProfile";
import { instructorName } from "@/components/instructors/InstructorCard";
import { isApiError } from "@/lib/api/errors";
import type { InstructorDetail, InstructorRedirect } from "@/lib/api/learning";
import { mediaSrc } from "@/lib/api/media";
import type { PublicReview } from "@/lib/api/publicReviews";
import { listResults, serverFetch, serverFetchSafe } from "@/lib/api/server";
import type { Paginated } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { absoluteUrl, buildMetadata, jsonLd, SITE_NAME } from "@/lib/seo";
import { formatRating, truncate } from "@/lib/format";

export const revalidate = 120;

type Params = Promise<{ handle: string }>;

const loadInstructor = cache(async (handle: string): Promise<InstructorDetail | InstructorRedirect | null> => {
  try {
    return await serverFetch<InstructorDetail | InstructorRedirect>(`instructors/${encodeURIComponent(handle)}`, {
      revalidate: 120,
      tags: ["instructors", `instructor:${handle}`],
    });
  } catch (err) {
    if (isApiError(err) && err.isNotFound) return null;
    throw err; // → app/error.tsx with «Повторить»
  }
});

function isRedirect(data: InstructorDetail | InstructorRedirect): data is InstructorRedirect {
  return typeof (data as InstructorRedirect).redirect === "string" && !(data as InstructorDetail).id;
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { handle } = await params;
  const data = await loadInstructor(decodeURIComponent(handle));
  // notFound() here makes crawlers (blocking metadata) get a real 404 status, not a streamed 200 + noindex.
  if (!data) notFound();
  if (isRedirect(data)) permanentRedirect(routes.instructor(data.redirect));
  const name = instructorName(data);
  const region = data.regions.map((r) => r.name).join(", ");
  const description = truncate(
    [data.headline, region && `Регион: ${region}`, data.about].filter(Boolean).join(". ") ||
      `Сёрф-инструктор ${name}: занятия, свободные окна и отзывы учеников.`,
    180,
  );
  return buildMetadata({
    title: `${name} — сёрф-инструктор${region ? `, ${region}` : ""}`,
    description,
    path: routes.instructor(data.handle),
    image: mediaSrc(data.avatar, "full"),
    type: "profile",
  });
}

interface BoardTypeRow {
  code: string;
  name: string;
}

export default async function InstructorPage({ params }: { params: Params }) {
  const { handle: raw } = await params;
  const handle = decodeURIComponent(raw);
  const data = await loadInstructor(handle);
  if (!data) notFound();
  if (isRedirect(data)) permanentRedirect(routes.instructor(data.redirect));

  const [reviews, boardTypes] = await Promise.all([
    serverFetchSafe<Paginated<PublicReview>>("reviews", {
      query: { target_type: "instructor", target_id: data.id, page_size: 10 },
      revalidate: 60,
      tags: ["reviews", `reviews:instructor:${data.id}`],
    }),
    serverFetchSafe<BoardTypeRow[] | Paginated<BoardTypeRow>>("board-types", { revalidate: 3600, tags: ["board-types"] }),
  ]);
  const boardLabels = Object.fromEntries(listResults(boardTypes).map((b) => [b.code, b.name]));
  const name = instructorName(data);
  const url = absoluteUrl(routes.instructor(data.handle));
  const avatar = mediaSrc(data.avatar, "full");

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={jsonLd({
          "@context": "https://schema.org",
          "@type": "Person",
          name,
          url,
          jobTitle: "Сёрф-инструктор",
          description: data.headline || undefined,
          image: avatar ? absoluteUrl(avatar) : undefined,
          knowsLanguage: data.languages.length ? data.languages : undefined,
          areaServed: data.regions.map((r) => ({ "@type": "Place", name: r.name })),
          worksFor: data.schools.map((s) => ({ "@type": "SportsOrganization", name: s.name, url: absoluteUrl(routes.school(s.slug)) })),
          ...(data.rating_count > 0
            ? {
                aggregateRating: {
                  "@type": "AggregateRating",
                  ratingValue: formatRating(data.rating_avg).replace(",", "."),
                  reviewCount: data.rating_count,
                  bestRating: 5,
                },
              }
            : {}),
          makesOffer: data.offers.map((o) => ({
            "@type": "Offer",
            name: o.title,
            price: o.price,
            priceCurrency: o.currency || "RUB",
            seller: { "@type": "Person", name },
          })),
          isPartOf: { "@type": "WebSite", name: SITE_NAME, url: absoluteUrl("/") },
        })}
      />
      <InstructorProfile detail={data} reviews={reviews} boardLabels={boardLabels} />
    </>
  );
}
