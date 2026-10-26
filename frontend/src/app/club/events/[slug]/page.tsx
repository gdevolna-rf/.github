/** /club/events/[slug] — событие клуба с регистрацией, лимитом мест и листом ожидания (CLB-02). */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";
import { ClubRegistrationBox } from "@/components/public/CatalogIslands";
import { ReportButton } from "@/components/trust/ReportButton";
import { MediaImage } from "@/components/ui";
import { isApiError } from "@/lib/api/errors";
import type { ClubEventDetail } from "@/lib/api/publicCatalogs";
import { serverFetch } from "@/lib/api/server";
import { formatDateTime } from "@/lib/format";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 60;
type Params = Promise<{ slug: string }>;

const load = cache(async (slug: string) => {
  try {
    return await serverFetch<ClubEventDetail>(`club/events/${encodeURIComponent(slug)}`, { revalidate: 60 });
  } catch (e) {
    if (isApiError(e) && e.isNotFound) return null;
    throw e;
  }
});

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const e = await load((await params).slug);
  return e ? buildMetadata({ title: e.title, description: e.description.slice(0, 160), path: routes.clubEvent(e.slug) }) : { title: "Событие" };
}

export default async function EventPage({ params }: { params: Params }) {
  const e = await load((await params).slug);
  if (!e) notFound();
  return (
    <div className="wrap gv-page-body">
      <nav className="small muted">
        <Link href={routes.club}>Клуб</Link>
      </nav>
      <div className="gv-spot-layout">
        <article className="spot-body">
          <div className="kicker">{e.kind_label}</div>
          <h1 className="spot-title">{e.title}</h1>
          {e.cover && <MediaImage media={e.cover} alt="" />}
          <p className="spot-summary">{e.description}</p>
          <ReportButton targetType="club_event" targetId={e.id} variant="link" />
        </article>
        <aside className="gv-spot-aside">
          <section className="gv-ac-panel">
            <dl className="lc-dl">
              <dt>Когда</dt>
              <dd>
                {formatDateTime(e.starts_at, { timeZone: e.timezone })} — {formatDateTime(e.ends_at, { timeZone: e.timezone })}
              </dd>
              <dt>Где</dt>
              <dd>
                {e.spot ? <Link href={routes.spot(e.spot.slug)}>{e.spot.name}</Link> : e.region?.name} {e.location_note}
              </dd>
              {e.capacity ? (
                <>
                  <dt>Места</dt>
                  <dd>
                    свободно {e.free_places ?? 0} из {e.capacity}
                    {e.waitlist_count ? ` · в очереди ${e.waitlist_count}` : ""}
                  </dd>
                </>
              ) : null}
            </dl>
            <ClubRegistrationBox eventId={e.id} slug={e.slug} isOpen={e.registration_open && e.status === "published"} />
          </section>
        </aside>
      </div>
    </div>
  );
}
