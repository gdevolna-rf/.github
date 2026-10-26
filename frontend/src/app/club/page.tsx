/** /club — о проекте и клуб (CLB-01..04): анонсы, участники, ближайшие события. */
import type { Metadata } from "next";
import Link from "next/link";
import { Hero } from "@/components/layout/PageBlocks";
import { MediaImage, StatStrip } from "@/components/ui";
import type { ClubEventCard, ClubOverview } from "@/lib/api/publicCatalogs";
import { serverFetchSafe } from "@/lib/api/server";
import { formatDate, formatDateTime } from "@/lib/format";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 120;

export const metadata: Metadata = buildMetadata({ title: "О нас и клуб", description: "Клуб ГДеволна: совместные катания, встречи и события сообщества.", path: routes.club });

function EventCard({ e }: { e: ClubEventCard }) {
  return (
    <article className="spot-card">
      <Link href={routes.clubEvent(e.slug)} className="spot-pic" aria-hidden tabIndex={-1}>
        <MediaImage media={e.cover} alt="" />
      </Link>
      <div className="spot-body">
        <div className="micro muted">
          {e.kind_label} · {formatDateTime(e.starts_at, { timeZone: e.timezone })}
        </div>
        <h3>
          <Link href={routes.clubEvent(e.slug)}>{e.title}</Link>
        </h3>
        <p className="small muted">
          {[e.spot?.name, e.region?.name, e.location_note].filter(Boolean).join(" · ")}
          {e.capacity ? ` · свободно ${e.free_places ?? 0} из ${e.capacity}` : ""}
        </p>
      </div>
    </article>
  );
}

export default async function ClubPage() {
  const data = await serverFetchSafe<ClubOverview>("club", { revalidate: 120, tags: ["club"] });
  const about = data?.about;
  return (
    <>
      <Hero title={about?.title ?? "О нас и клуб"} kicker={about?.kicker ?? "Гдеволна · клуб"} text={about?.text} />
      <div className="wrap gv-page-body">
        {data && (
          <StatStrip
            items={[
              { label: "Участников GG Surfer", value: data.stats.members },
              { label: "Ближайших событий", value: data.stats.upcoming_events },
            ]}
          />
        )}
        {about?.highlights?.length ? (
          <section className="section">
            <h2 className="section-title">{about.highlights_title}</h2>
            <div className="grid-3">
              {about.highlights.map((h) => (
                <div key={h.title} className="gv-ac-panel">
                  <h3>
                    {h.emoji} {h.title}
                  </h3>
                  <p>{h.text}</p>
                </div>
              ))}
            </div>
          </section>
        ) : null}
        {data && data.announcements.length > 0 && (
          <section className="section">
            <h2 className="section-title">Анонсы</h2>
            <div className="lc-stack">
              {data.announcements.map((a) => (
                <article key={a.id} className="gv-ac-panel">
                  <h3>
                    {a.is_pinned ? "📌 " : ""}
                    {a.title}
                  </h3>
                  <p>{a.body}</p>
                  {a.published_at && <div className="small muted">{formatDate(a.published_at)}</div>}
                </article>
              ))}
            </div>
          </section>
        )}
        <section className="section">
          <h2 className="section-title">Ближайшие события</h2>
          {!data || data.upcoming_events.length === 0 ? (
            <p className="muted">Скоро появятся новые встречи и совместные катания.</p>
          ) : (
            <div className="grid-3">
              {data.upcoming_events.map((e) => (
                <EventCard key={e.id} e={e} />
              ))}
            </div>
          )}
        </section>
        {about?.roadmap?.length ? (
          <section className="section club-roadmap">
            <h2 className="section-title">Путь в клубе</h2>
            <ol>
              {about.roadmap.map((r) => (
                <li key={r.label}>
                  <b>{r.label}</b> — {r.text}
                </li>
              ))}
            </ol>
          </section>
        ) : null}
        {about?.invite && (
          <section className="club-invite gv-ac-panel">
            <div className="kicker">{about.invite.eyebrow}</div>
            <h2>{about.invite.title}</h2>
            <p>{about.invite.text}</p>
            <Link href={routes.gg}>Открыть GG Surfer →</Link>
          </section>
        )}
      </div>
    </>
  );
}
