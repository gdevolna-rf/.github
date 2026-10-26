/**
 * Карточка сёрф-школы (SCH-02, SCH-04/05, ATX-35): brand, photos, description, region, spots, formats, programs,
 * upcoming sessions with free seats → booking, team (one entry per person), rating and reviews, inquiry, complaint.
 * Server Component (SSR + ISR); everything about the viewer (member? own review?) lives in client islands.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { isApiError } from "@/lib/api/errors";
import {
  AGE_CATEGORY_LABELS,
  LANGUAGE_LABELS,
  LESSON_FORMAT_LABELS,
  STUDENT_LEVEL_LABELS,
  labelOf,
  type SchoolDetail,
  type SchoolUpcomingSession,
} from "@/lib/api/learning";
import { mediaSrc } from "@/lib/api/media";
import type { PublicReview } from "@/lib/api/publicReviews";
import { serverFetch, serverFetchSafe } from "@/lib/api/server";
import type { Media, Paginated, RegionRef } from "@/lib/api/types";
import { formatDate, formatDuration, formatMoney, formatPriceFrom, formatTime, plural, truncate, WORDS } from "@/lib/format";
import { routes } from "@/lib/routes";
import { absoluteUrl, buildMetadata, jsonLd } from "@/lib/seo";
import { SectionTitle } from "@/components/layout/PageBlocks";
import { Avatar } from "@/components/ui/Avatar";
import { Tag } from "@/components/ui/Badge";
import { ClampText } from "@/components/ui/ClampText";
import { Icon } from "@/components/ui/Icon";
import { MediaImage } from "@/components/ui/MediaImage";
import { Rating } from "@/components/ui/Rating";
import { EmptyState } from "@/components/ui/States";
import { TrackView } from "@/components/analytics/TrackView";
import { ReviewsSection } from "@/components/trust/ReviewsSection";
import { ProgramInquiry, SchoolActions, SchoolReviewForm, SessionCta } from "@/components/schools/SchoolIslands";
import { dedupeTeam, teamRoleLabel } from "@/components/schools/team";
import "@/components/schools/schools.css";

export const revalidate = 120;

type Params = Promise<{ slug: string }>;

async function loadSchool(slug: string): Promise<SchoolDetail> {
  const data = await serverFetch<SchoolDetail>(`organizations/${encodeURIComponent(slug)}`, {
    revalidate,
    tags: ["organizations", `organization:${slug}`],
  }).catch((err: unknown) => {
    if (isApiError(err) && err.isNotFound) notFound();
    throw err; // → app/error.tsx with «Повторить»
  });
  if (data.kind !== "school") notFound();
  return data;
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { slug } = await params;
  const school = await serverFetchSafe<SchoolDetail>(`organizations/${encodeURIComponent(slug)}`, { revalidate, tags: ["organizations"] });
  if (!school || school.kind !== "school") return buildMetadata({ title: "Сёрф-школа", path: routes.school(slug), noindex: true });
  const place = [school.region?.name, school.city].filter(Boolean).join(", ");
  return buildMetadata({
    title: `${school.name} — сёрф-школа${place ? `, ${place}` : ""}`,
    description: truncate(school.short_description || school.description || `Сёрф-школа ${school.name}: программы, расписание и отзывы.`, 160),
    path: routes.school(school.slug),
    image: mediaSrc(school.cover ?? school.logo, "full"),
  });
}

function galleryItems(gallery: SchoolDetail["gallery"]): Media[] {
  return (gallery ?? [])
    .map((g) => ("media" in g && g.media && typeof g.media === "object" ? (g.media as Media) : (g as Media)))
    .filter((m): m is Media => Boolean(m?.url));
}

function sessionWhen(s: SchoolUpcomingSession, tz?: string) {
  const zone = s.timezone || tz;
  return `${formatDate(s.starts_at, { timeZone: zone, style: "long" })}, ${formatTime(s.starts_at, zone)}–${formatTime(s.ends_at, zone)}`;
}

export default async function SchoolPage({ params }: { params: Params }) {
  const { slug } = await params;
  const school = await loadSchool(slug);
  const [regions, reviews] = await Promise.all([
    serverFetchSafe<RegionRef[]>("regions", { revalidate: 3600, tags: ["regions"] }),
    serverFetchSafe<Paginated<PublicReview>>("reviews", {
      query: { target_type: "organization", target_id: school.id, page_size: 10 },
      revalidate: 120,
      tags: ["reviews", `reviews:organization:${school.id}`],
    }),
  ]);
  const timeZone = regions?.find((r) => r.slug === school.region?.slug)?.timezone;
  const photos = galleryItems(school.gallery);
  const team = dedupeTeam(school.team);
  const ref = { id: school.id, name: school.name };
  const programTitle = new Map(school.programs.map((p) => [p.id, p.title]));
  const place = [school.region?.name, school.city].filter(Boolean).join(" · ");
  const logo = mediaSrc(school.logo, "thumb");
  const site = school.website && /^https?:\/\//.test(school.website) ? school.website : school.website ? `https://${school.website}` : "";

  const ld: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "SportsActivityLocation",
    name: school.name,
    description: school.short_description || truncate(school.description || "", 300),
    url: absoluteUrl(routes.school(school.slug)),
    sport: "Surfing",
    address: {
      "@type": "PostalAddress",
      addressCountry: "RU",
      ...(school.region?.name ? { addressRegion: school.region.name } : {}),
      ...(school.city ? { addressLocality: school.city } : {}),
      ...(school.address ? { streetAddress: school.address } : {}),
    },
  };
  const image = mediaSrc(school.cover ?? school.logo, "full");
  if (image) ld.image = absoluteUrl(image);
  if (school.rating_count > 0) {
    ld.aggregateRating = { "@type": "AggregateRating", ratingValue: Number(school.rating_avg), reviewCount: school.rating_count, bestRating: 5, worstRating: 1 };
  }
  if (school.price_from) ld.priceRange = `от ${Number(school.price_from)} ${school.currency || "RUB"}`;

  return (
    <div className="wrap gv-school-page">
      <script type="application/ld+json" dangerouslySetInnerHTML={jsonLd(ld)} />
      <TrackView subjectType="organization" subjectId={school.id} />

      <div className="gv-school-cover">
        <MediaImage media={school.cover} alt={`Сёрф-школа «${school.name}»`} priority placeholder="Обложка пока не загружена" />
      </div>

      <header className="gv-school-head">
        <span className="gv-school-head-logo" aria-hidden="true">
          {logo ? <img src={logo} alt="" /> : <Icon name="school" size={34} />}
        </span>
        <div className="gv-school-head-text">
          <p className="gv-session-crumbs">
            <Link href={routes.schools}>Сёрф-школы</Link>
            {school.region?.name ? (
              <>
                {" "}
                · <Link href={`${routes.schools}?region=${encodeURIComponent(school.region.slug)}`}>{school.region.name}</Link>
              </>
            ) : null}
          </p>
          <h1>{school.name}</h1>
          <div className="gv-school-head-line">
            {place && (
              <span>
                <Icon name="map-pin" size={14} /> {place}
              </span>
            )}
            <Rating value={school.rating_avg} count={school.rating_count} href="#reviews" />
            {school.verification_status === "verified" && (
              <Tag variant="verified" icon="check">
                Школа проверена
              </Tag>
            )}
          </div>
          <SchoolActions school={ref} />
        </div>
      </header>

      <div className="gv-school-layout">
        <div>
          <section className="gv-school-block" aria-labelledby="about-title">
            <SectionTitle id="about-title">О школе</SectionTitle>
            {school.description || school.short_description ? (
              <ClampText lines={6} className="gv-school-text">
                {school.description || school.short_description}
              </ClampText>
            ) : (
              <p className="gv-school-text">Школа пока не добавила описание.</p>
            )}
          </section>

          {photos.length > 0 && (
            <section className="gv-school-block" aria-labelledby="photos-title">
              <SectionTitle id="photos-title">
                Фото <Tag>{`${photos.length} ${plural(photos.length, WORDS.photo)}`}</Tag>
              </SectionTitle>
              <ul className={photos.length === 1 ? "gv-school-gallery is-single" : "gv-school-gallery"}>
                {photos.map((m, i) => (
                  <li key={m.id}>
                    <a href={m.url ?? "#"} target="_blank" rel="noopener noreferrer" aria-label={`Открыть фото ${i + 1} из ${photos.length}`}>
                      <img src={mediaSrc(m, photos.length === 1 ? "full" : "thumb") ?? ""} alt={m.alt_text || `${school.name} — фото ${i + 1}`} loading="lazy" />
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="gv-school-block" aria-labelledby="programs-title">
            <SectionTitle id="programs-title">Программы</SectionTitle>
            {school.programs.length === 0 ? (
              <EmptyState compact title="Программ пока нет" text="Напишите школе — расскажут о занятиях и ближайших датах." />
            ) : (
              <ul className="gv-program-list">
                {school.programs.map((p) => (
                  <li key={p.id} className="lesson-info-card gv-program">
                    <h3 className="gv-clamp-2" title={p.title}>
                      {p.title}
                    </h3>
                    <div className="conditions">
                      {p.level && <Tag>{labelOf(STUDENT_LEVEL_LABELS, p.level)}</Tag>}
                      {p.age_category && <Tag>{labelOf(AGE_CATEGORY_LABELS, p.age_category)}</Tag>}
                      {p.format && <Tag>{labelOf(LESSON_FORMAT_LABELS, p.format)}</Tag>}
                    </div>
                    {p.description && <p className="gv-clamp-3">{p.description}</p>}
                    <p className="small">
                      {formatDuration(p.duration_min)}
                      {p.sessions_count > 1 ? ` · ${p.sessions_count} занятий в курсе` : ""}
                      {p.max_group_size ? ` · группа до ${p.max_group_size}` : ""}
                      {p.equipment_included ? " · снаряжение включено" : ""}
                    </p>
                    <div className="gv-program-foot">
                      <span className="gv-program-price">{p.price ? formatMoney(p.price, p.currency || "RUB") : "Цена по запросу"}</span>
                      <ProgramInquiry school={ref} program={{ id: p.id, title: p.title }} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="gv-school-block" aria-labelledby="sessions-title">
            <SectionTitle id="sessions-title">Ближайшие занятия</SectionTitle>
            {school.upcoming_sessions.length === 0 ? (
              <EmptyState compact title="Ближайших занятий нет" text="Расписание обновляется — напишите школе, чтобы договориться о дате." />
            ) : (
              <>
                <p className="small">Время указано местное{timeZone ? ` (${timeZone.replace(/_/g, " ")})` : ""}. Места подтверждает школа.</p>
                <ul className="gv-session-list">
                  {school.upcoming_sessions.map((s) => {
                    const program = s.program_id ? programTitle.get(s.program_id) : undefined;
                    const full = s.free_seats <= 0;
                    return (
                      <li key={s.id} className="gv-session-row">
                        <div>
                          <h3 className="gv-clamp-2" title={s.title}>
                            <Link href={routes.session(s.id)}>{s.title || program || "Занятие"}</Link>
                          </h3>
                          <p className="gv-session-meta">
                            <span>
                              <Icon name="calendar" size={13} /> {sessionWhen(s, timeZone)}
                            </span>
                            {s.spot && (
                              <span>
                                <Icon name="map-pin" size={13} /> <Link href={routes.spot(s.spot.slug)}>{s.spot.name}</Link>
                              </span>
                            )}
                            {s.instructor && (
                              <span>
                                <Icon name="user" size={13} /> {s.instructor.display_name}
                              </span>
                            )}
                            {s.price && <span>{formatMoney(s.price, s.currency || "RUB")}</span>}
                          </p>
                        </div>
                        <div className="gv-session-cta">
                          <span className={full ? "gv-seats is-full" : "gv-seats"}>
                            {full ? "Мест нет" : `Свободно ${s.free_seats} из ${s.capacity}`}
                          </span>
                          <SessionCta
                            school={ref}
                            timeZone={timeZone}
                            session={{
                              id: s.id,
                              title: s.title || program || "Занятие",
                              starts_at: s.starts_at,
                              ends_at: s.ends_at,
                              timezone: s.timezone ?? timeZone ?? null,
                              free_seats: s.free_seats,
                              capacity: s.capacity,
                              price: s.price,
                              currency: s.currency,
                              spot: s.spot,
                            }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </>
            )}
          </section>

          <ReviewsSection
            targetType="organization"
            targetId={school.id}
            initial={reviews}
            ratingAvg={school.rating_avg}
            ratingCount={school.rating_count}
            title="Отзывы учеников"
            emptyText="Отзывы появятся после завершённых занятий и проверки модератором."
            form={<SchoolReviewForm school={ref} />}
          />
        </div>

        <aside className="gv-school-aside" aria-label="Коротко о школе">
          <div className="side-card">
            <h2>Коротко</h2>
            <dl className="gv-school-facts">
              <div>
                <dt>Стоимость</dt>
                <dd>{formatPriceFrom(school.price_from, school.currency || "RUB")}</dd>
              </div>
              {school.region?.name && (
                <div>
                  <dt>Регион</dt>
                  <dd>{school.region.name}</dd>
                </div>
              )}
              {school.city && (
                <div>
                  <dt>Город</dt>
                  <dd>{school.city}</dd>
                </div>
              )}
              {school.address && (
                <div>
                  <dt>Адрес</dt>
                  <dd>{school.address}</dd>
                </div>
              )}
              {school.formats?.length > 0 && (
                <div>
                  <dt>Форматы</dt>
                  <dd>{school.formats.map((f) => labelOf(LESSON_FORMAT_LABELS, f)).join(", ")}</dd>
                </div>
              )}
              {school.languages?.length > 0 && (
                <div>
                  <dt>Языки</dt>
                  <dd>{school.languages.map((l) => labelOf(LANGUAGE_LABELS, l)).join(", ")}</dd>
                </div>
              )}
              {site && (
                <div>
                  <dt>Сайт</dt>
                  <dd>
                    <a href={site} target="_blank" rel="noopener noreferrer nofollow">
                      {school.website.replace(/^https?:\/\//, "")}
                    </a>
                  </dd>
                </div>
              )}
            </dl>
          </div>

          <div className="side-card">
            <h2>Споты</h2>
            {school.spots.length === 0 ? (
              <p className="small">Школа пока не указала споты.</p>
            ) : (
              <div className="gv-school-chips">
                {school.spots.map((s) => (
                  <Link key={s.id} href={routes.spot(s.slug)} className="chip">
                    <Icon name="target" size={13} /> {s.name}
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div className="side-card">
            <h2>Команда</h2>
            {team.length === 0 ? (
              <p className="small">Команда пока не представлена.</p>
            ) : (
              <ul className="gv-team-list">
                {team.map((m) => (
                  <li key={m.accountId} className="gv-team-member">
                    <Avatar media={m.member.account.avatar} name={m.name} size={44} />
                    <div>
                      <b>{m.name}</b>
                      <small>{teamRoleLabel(m)}</small>
                      {m.instructorHandle && (
                        <Link href={routes.instructor(m.instructorHandle)} aria-label={`Профиль инструктора: ${m.name}`}>
                          Профиль инструктора →
                        </Link>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
