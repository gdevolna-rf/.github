/**
 * /spots/[slug] — карточка спота (SPT-01..12): SSR для SEO, персональные части (мой отзыв, мои правки, избранное)
 * — клиентские острова. «Типичные условия» (розы ветра и свелла) строго отделены от прогноза (SPT-04, GEO-04).
 */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";
import { TrackView } from "@/components/analytics/TrackView";
import { SpotGallery } from "@/components/spots/SpotGallery";
import { SpotMyStatus } from "@/components/spots/SpotMyStatus";
import { SpotReviews } from "@/components/spots/SpotReviews";
import { SpotEditButton } from "@/components/spots/SpotEditButton";
import { SpotEditFromUrl, SpotViewerProvider } from "@/components/spots/SpotViewer";
import { ReportButton } from "@/components/trust/ReportButton";
import { Avatar, CompassRose, HeartButton, Rating } from "@/components/ui";
import { isApiError } from "@/lib/api/errors";
import { mediaSrc } from "@/lib/api/media";
import type { PublicReview } from "@/lib/api/publicReviews";
import { serverFetch, serverFetchSafe } from "@/lib/api/server";
import { formatCoords, formatDay, formatDistance, type ForecastResponse, type SpotDetail, type SpotDictionaries } from "@/lib/api/spots";
import type { Paginated } from "@/lib/api/types";
import { choiceLabel } from "@/lib/labels";
import { formatDateTime, formatMoney } from "@/lib/format";
import { routes } from "@/lib/routes";
import { buildMetadata, jsonLd } from "@/lib/seo";
import "@/components/spots/spots.css";
import "@/components/trust/trust.css";

export const revalidate = 120;
type Params = Promise<{ slug: string }>;

const loadSpot = cache(async (slug: string): Promise<SpotDetail | null> => {
  try {
    return await serverFetch<SpotDetail>(`spots/${encodeURIComponent(slug)}`, { revalidate: 120, tags: ["spots", `spot:${slug}`] });
  } catch (err) {
    if (isApiError(err) && err.isNotFound) return null;
    throw err;
  }
});

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { slug } = await params;
  const spot = await loadSpot(slug);
  if (!spot) return { title: "Спот не найден" };
  return buildMetadata({
    title: `${spot.name} — сёрф-спот${spot.region ? `, ${spot.region.name}` : ""}`,
    description: spot.short_description || spot.description.slice(0, 160),
    path: routes.spot(spot.slug),
    image: mediaSrc(spot.cover) ?? undefined,
  });
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  if (children === null || children === undefined || children === "") return null;
  return (
    <div className="gv-fact">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Forecast({ data }: { data: ForecastResponse | null }) {
  if (!data || !data.provider || data.items.length === 0) {
    return <p className="muted">{data?.message || "Прогноз появится после подключения провайдера данных. Ориентируйтесь на типичные условия и местных инструкторов."}</p>;
  }
  return (
    <>
      <p className="small muted">
        Источник: {data.provider_title ?? data.provider}
        {data.issued_at ? `, обновлено ${formatDateTime(data.issued_at)}` : ""}. Прогноз — не гарантия условий.
      </p>
      <div className="gv-table-scroll">
        <table className="gv-table">
          <thead>
            <tr>
              <th scope="col">Время</th>
              <th scope="col">Волна</th>
              <th scope="col">Период</th>
              <th scope="col">Ветер</th>
              <th scope="col">Вода</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((f) => (
              <tr key={f.valid_from}>
                <td>{formatDateTime(f.valid_from)}</td>
                <td>{f.wave_height_m ?? "—"} м {f.wave_direction ?? ""}</td>
                <td>{f.wave_period_s ?? "—"} с</td>
                <td>{f.wind_speed_ms ?? "—"} м/с {f.wind_direction ?? ""}</td>
                <td>{f.water_temp_c ?? "—"} °C</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default async function SpotPage({ params }: { params: Params }) {
  const { slug } = await params;
  const spot = await loadSpot(slug);
  if (!spot) notFound();
  const [forecast, dictionaries, reviews] = await Promise.all([
    serverFetchSafe<ForecastResponse>(`spots/${encodeURIComponent(slug)}/forecast`, { revalidate: 600 }),
    serverFetchSafe<SpotDictionaries>("spots/dictionaries", { revalidate: 3600 }),
    serverFetchSafe<Paginated<PublicReview>>(`reviews?target_type=spot&target_id=${spot.id}`, { revalidate: 120 }),
  ]);

  return (
    <SpotViewerProvider spot={spot} dictionaries={dictionaries}>
      <TrackView subjectType="spot" subjectId={spot.id} />
      <SpotEditFromUrl />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={jsonLd({
        "@context": "https://schema.org",
        "@type": "Place",
        name: spot.name,
        description: spot.short_description,
        ...(spot.precise && spot.lat !== null ? { geo: { "@type": "GeoCoordinates", latitude: spot.lat, longitude: spot.lng } } : {}),
        ...(spot.rating_count ? { aggregateRating: { "@type": "AggregateRating", ratingValue: spot.rating_avg, reviewCount: spot.rating_count } } : {}),
        })}
      />
      <div className="wrap gv-page-body">
        <nav className="small muted" aria-label="Навигация">
          <Link href={routes.spots}>Карта спотов</Link> {spot.region ? `· ${spot.region.name}` : ""}
        </nav>
        <header className="gv-spot-page-head">
          <div>
            <div className="kicker">{spot.region?.name ?? "Сёрф-спот"}</div>
            <h1 className="spot-title">{spot.name}</h1>
            <Rating value={spot.rating_avg} count={spot.rating_count} href="#reviews" />
          </div>
          <div className="gv-spot-page-actions">
            <HeartButton type="spot" id={spot.id} name={spot.name} variant="pill" />
            <SpotEditButton variant="pill" />
            <ReportButton targetType="spot" targetId={spot.id} variant="link" />
          </div>
        </header>

        {(spot.is_closed || spot.seasonal_warning) && (
          <div className="spot-safety" role="note">
            {spot.is_closed ? `Спот закрыт${spot.closed_until ? ` до ${formatDay(spot.closed_until)}` : ""}. ` : ""}
            {spot.seasonal_warning}
          </div>
        )}

        <SpotGallery spotId={spot.id} name={spot.name} photos={spot.photos} cover={spot.cover} />
        <SpotMyStatus />

        <div className="gv-spot-layout">
          <article className="spot-body">
            {spot.description && <p className="spot-summary">{spot.description}</p>}

            <section aria-labelledby="typical">
              <h2 id="typical">Типичные условия</h2>
              <p className="small muted">Благоприятные направления по многолетнему опыту — это не прогноз на сегодня.</p>
              <div className="gv-rose-pair">
                <CompassRose kind="wind" directions={spot.best_wind_directions} />
                <CompassRose kind="swell" directions={spot.best_swell_directions} />
              </div>
              <dl className="gv-facts">
                <Fact label="Уровень">{choiceLabel(spot.difficulty)}</Fact>
                <Fact label="Брейк">{choiceLabel(spot.break_type)}</Fact>
                <Fact label="Дно">{choiceLabel(spot.bottom_type)}</Fact>
                <Fact label="Характер волны">{spot.wave_character}</Fact>
                <Fact label="Мощность">{spot.wave_power}</Fact>
                <Fact label="Сезон">{spot.season}</Fact>
                <Fact label="Лучшие месяцы">{spot.best_months.map((m) => m.label ?? String(m.code)).join(", ")}</Fact>
                <Fact label="Прилив">{spot.best_tide}</Fact>
                <Fact label="Вода">{spot.water_temp_note}</Fact>
              </dl>
              {spot.typical_conditions && <p>{spot.typical_conditions}</p>}
            </section>

            <section aria-labelledby="forecast">
              <h2 id="forecast">Прогноз</h2>
              <Forecast data={forecast} />
            </section>

            {(spot.hazards.length > 0 || spot.hazard_notes || spot.entry_exit) && (
              <section aria-labelledby="hazards">
                <h2 id="hazards">Безопасность и вход в воду</h2>
                {spot.hazards.length > 0 && (
                  <ul className="gv-chip-list">
                    {spot.hazards.map((h) => (
                      <li key={typeof h === "string" ? h : h.code} className="gv-tag">
                        {choiceLabel(h)}
                      </li>
                    ))}
                  </ul>
                )}
                {spot.hazard_notes && <p>{spot.hazard_notes}</p>}
                {spot.entry_exit && (
                  <p>
                    <b>Вход и выход:</b> {spot.entry_exit}
                  </p>
                )}
              </section>
            )}

            <section aria-labelledby="access">
              <h2 id="access">Как добраться и инфраструктура</h2>
              <p>
                {spot.precise ? `Координаты: ${formatCoords(spot.lat, spot.lng)}` : "Точное место скрыто по просьбе сообщества — показан район."}
              </p>
              {spot.access && <p>{spot.access}</p>}
              {spot.infrastructure.length > 0 ? (
                <ul className="gv-infra">
                  {spot.infrastructure.map((i, n) => (
                    <li key={n}>
                      <b>{i.type_label}</b> {i.name} {i.distance_m !== null && <span className="muted">· {formatDistance(i.distance_m)}</span>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Сведений об инфраструктуре пока нет — предложите правку.</p>
              )}
            </section>

            <section aria-labelledby="sources">
              <h2 id="sources">Источники</h2>
              <p className="small muted">
                {spot.data_source}
                {spot.last_confirmed_at ? ` · сведения подтверждены ${formatDay(spot.last_confirmed_at)}` : ""}
              </p>
              {spot.sources.length > 0 && (
                <ul className="small">
                  {spot.sources.map((s) => (
                    <li key={s.id}>
                      {s.url ? <a href={s.url} rel="nofollow noopener" target="_blank">{s.source}</a> : s.source}
                      {s.note ? ` — ${s.note}` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <div id="reviews">
              <SpotReviews initial={reviews} />
            </div>
          </article>

          <aside className="gv-spot-aside">
            {spot.instructors.length > 0 && (
              <section aria-labelledby="spot-instructors" className="gv-ac-panel">
                <h2 id="spot-instructors">Инструкторы на этом споте</h2>
                <ul className="lc-list">
                  {spot.instructors.map((i) => (
                    <li key={i.id} className="lc-list-row">
                      <Avatar media={i.account.avatar} name={i.account.display_name} size={40} />
                      <Link className="lc-grow" href={routes.instructor(i.account.handle ?? "")}>
                        <strong>{i.account.display_name}</strong>
                        <div className="small muted">
                          {i.headline}
                          {i.price_from ? ` · от ${formatMoney(i.price_from, i.currency)}` : ""}
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {spot.organizations.length > 0 && (
              <section aria-labelledby="spot-orgs" className="gv-ac-panel">
                <h2 id="spot-orgs">Школы и прокаты рядом</h2>
                <ul className="lc-list">
                  {spot.organizations.map((o) => (
                    <li key={o.id} className="lc-list-row">
                      <Avatar media={o.logo} name={o.name} size={40} />
                      <Link className="lc-grow" href={choiceLabel(o.kind) && (typeof o.kind === "string" ? o.kind : o.kind.code) === "school" ? routes.school(o.slug) : `${routes.rentals}?organization=${o.slug}`}>
                        <strong>{o.name}</strong>
                        <div className="small muted">{choiceLabel(o.kind)}</div>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <section className="gv-ac-panel">
              <h2>Аренда рядом</h2>
              <Link href={`${routes.rentals}?spot=${spot.slug}`}>Доски и гидрокостюмы на этом споте →</Link>
            </section>
          </aside>
        </div>
      </div>
    </SpotViewerProvider>
  );
}
