/**
 * «Соревнования · LIVE» block of the home page. Upcoming contests come from GET /club/events?kind=contest;
 * a stream is embedded only from an event's YouTube/RuTube link (admin data — visitors can no longer set it,
 * prototype demo behaviour removed). Without data the prototype placeholder is shown.
 */
import Link from "next/link";
import { toEmbedUrl } from "@/lib/embed";
import { formatDate } from "@/lib/format";
import { routes } from "@/lib/routes";
import { ButtonLink } from "@/components/ui/Button";

export interface LiveEvent {
  slug: string;
  title: string;
  kind?: string;
  kind_label?: string;
  starts_at: string;
  /** IANA zone of the event place (club API) */
  timezone?: string;
  region?: { name: string; timezone?: string } | null;
  location_note?: string;
  stream_url?: string | null;
  live_url?: string | null;
}

export function LivePanel({ events: all }: { events: LiveEvent[] }) {
  const contests = all.filter((e) => e.kind === "contest");
  const events = contests.length ? contests : all;
  const listLabel = contests.length ? "Ближайшие соревнования" : "Ближайшие события клуба";
  const live = events.map((e) => ({ e, url: toEmbedUrl(e.live_url ?? e.stream_url) })).find((x) => x.url);
  return (
    <section className="section">
      <div className="live-panel">
        <div className="live-panel-copy">
          <span className="live-kicker">
            <span className="live-dot" aria-hidden="true" /> СОРЕВНОВАНИЯ · LIVE
          </span>
          <h2>Когда наши выходят на волну — смотрим вместе</h2>
          <p>Здесь появятся прямые эфиры соревнований, фестивалей и сёрф-встреч.</p>
          {events.length > 0 && (
            <ul className="live-events" aria-label={listLabel}>
              {events.slice(0, 3).map((e) => (
                <li key={e.slug}>
                  <Link href={routes.clubEvent(e.slug)}>
                    <time dateTime={e.starts_at}>{formatDate(e.starts_at, { style: "dayMonth", timeZone: e.timezone ?? e.region?.timezone })}</time>
                    <span className="gv-clamp-1">
                      {e.title}
                      {e.region?.name ? ` · ${e.region.name}` : ""}
                    </span>
                    {e.kind_label && <small className="live-event-kind">{e.kind_label}</small>}
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <div className="view-tools">
            <ButtonLink href={routes.club} variant="pill" iconRight="arrow">
              События клуба
            </ButtonLink>
          </div>
        </div>
        <div className="live-screen">
          {live ? (
            <iframe
              src={live.url!}
              title={`Трансляция: ${live.e.title}`}
              loading="lazy"
              allow="autoplay; encrypted-media; fullscreen; picture-in-picture"
              allowFullScreen
            />
          ) : (
            <div className="live-empty">
              <span className="play-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width={26} height={26}>
                  <path d="M8.5 5.5v13l10-6.5z" fill="currentColor" />
                </svg>
              </span>
              <strong>Место для прямого эфира</strong>
              <small>Как только включим трансляцию, она появится здесь</small>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
