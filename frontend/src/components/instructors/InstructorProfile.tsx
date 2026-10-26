/**
 * Public instructor profile (INS-01/02/03/04/08, PUBLIC_SCREENS §3.3 — the prototype modal becomes a page with the same
 * blocks): intro, about + fun facts, photos/videos, where and whom he teaches, offers, free slots, certificates,
 * reviews. Server Component; viewer-dependent parts are client islands (ProfileIslands).
 */
import Link from "next/link";
import { TrackView } from "@/components/analytics/TrackView";
import { CertificateBadge, ClampText, Icon, MediaImage, Rating, StatusBadge, Tag } from "@/components/ui";
import {
  BOARD_TYPE_LABELS,
  LANGUAGE_LABELS,
  LESSON_FORMAT_LABELS,
  labelOf,
  STUDENT_LEVEL_LABELS,
  type InstructorDetail,
} from "@/lib/api/learning";
import { mediaSrc } from "@/lib/api/media";
import type { PublicReview } from "@/lib/api/publicReviews";
import type { Paginated } from "@/lib/api/types";
import { formatClock, formatDate, formatDuration, formatMoney, formatPriceFrom } from "@/lib/format";
import { routes } from "@/lib/routes";
import { instructorAccountId } from "./catalog";
import { experienceText, instructorName, joinLabels } from "./InstructorCard";
import {
  CertificateScanButton,
  InstructorReviews,
  OfferInquiry,
  ProfileActions,
  ScheduleEmpty,
  SlotList,
} from "./ProfileIslands";
import "./instructors.css";

export function InstructorProfile({
  detail,
  reviews,
  boardLabels = {},
}: {
  detail: InstructorDetail;
  reviews: Paginated<PublicReview> | null;
  boardLabels?: Record<string, string>;
}) {
  const name = instructorName(detail);
  const accountId = instructorAccountId(detail);
  const contact = { accountId, offerId: detail.offers[0]?.id ?? null };
  const regions = detail.regions.map((r) => r.name).join(", ");
  const teaching = experienceText(detail.teaching_since);
  const surfing = experienceText(detail.surfing_since);
  const levels = joinLabels(detail.student_levels, STUDENT_LEVEL_LABELS);
  const formats = joinLabels(detail.formats, LESSON_FORMAT_LABELS);
  const boards = joinLabels(detail.board_types, { ...BOARD_TYPE_LABELS, ...boardLabels });
  const languages = joinLabels(detail.languages, LANGUAGE_LABELS);
  const media = [...detail.media].sort((a, b) => a.position - b.position).filter((m) => m.media && (m.media.url || m.media.thumbnail_url));
  const photos = media.filter((m) => m.media.kind !== "video");
  const videos = media.filter((m) => m.media.kind === "video");
  const sections = [
    { id: "about", label: "О себе" },
    detail.offers.length ? { id: "offers", label: "Занятия и цены" } : null,
    { id: "schedule", label: "Свободные окна" },
    detail.certificates.length ? { id: "certificates", label: "Сертификаты" } : null,
    { id: "reviews", label: "Отзывы" },
  ].filter(Boolean) as Array<{ id: string; label: string }>;

  return (
    <div className="wrap gv-ins-profile">
      <TrackView subjectType="instructor" subjectId={detail.id} />
      <nav className="gv-ins-crumbs" aria-label="Навигация">
        <Link href={routes.instructors}>Каталог сёрф-инструкторов</Link> / <span aria-current="page">{name}</span>
      </nav>

      <section className="gv-ins-intro" aria-labelledby="ins-name">
        <div className="lesson-dialog-intro">
          <div className="gv-ins-portrait">
            <MediaImage media={detail.avatar} alt={`Фото: ${name}`} placeholder="Фото пока нет" priority />
          </div>
          <div className="lesson-dialog-summary gv-ins-summary">
            <div className="lesson-kicker">Люди, с которыми волна ближе</div>
            <h1 id="ins-name">{name}</h1>
            {detail.headline && <p className="gv-ins-headline-lg">{detail.headline}</p>}
            {regions && (
              <div className="lesson-place">
                <Icon name="map-pin" size={14} /> {regions}
              </div>
            )}
            <div className="lesson-top-line">
              <Rating value={detail.rating_avg} count={detail.rating_count} href="#reviews" />
              <CertificateBadge status={detail.certificate_status} />
              {detail.schools.length > 0 && (
                <Tag variant="soft" icon="school">
                  Инструктор школы
                </Tag>
              )}
            </div>
            <p className="lesson-hint">
              {[levels && `Ученики: ${levels.toLowerCase()}`, teaching && `преподаёт ${teaching}`, surfing && `катается ${surfing}`]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <ProfileActions id={detail.id} handle={detail.handle} name={name} contact={contact} />
          </div>
        </div>
      </section>

      <nav className="gv-ins-nav" aria-label="Разделы профиля">
        {sections.map((s) => (
          <a key={s.id} href={`#${s.id}`}>
            {s.label}
          </a>
        ))}
      </nav>

      <section className="gv-ins-section" id="about" aria-labelledby="about-title">
        <h2 id="about-title">О себе</h2>
        <div className="lesson-info-columns">
          <div className="lesson-info-card">
            <h3>Про занятия</h3>
            <dl className="gv-ins-dl">
              {detail.spots.length > 0 && (
                <>
                  <dt>Где катаемся</dt>
                  <dd>
                    <span className="gv-ins-links">
                      {detail.spots.map((s) => (
                        <Link key={s.id} href={routes.spot(s.slug)} className="chip">
                          {s.name}
                        </Link>
                      ))}
                    </span>
                  </dd>
                </>
              )}
              {regions && (
                <>
                  <dt>Регионы</dt>
                  <dd>{regions}</dd>
                </>
              )}
              {formats && (
                <>
                  <dt>Форматы</dt>
                  <dd>{formats}</dd>
                </>
              )}
              {levels && (
                <>
                  <dt>Для кого</dt>
                  <dd>{levels}</dd>
                </>
              )}
              {boards && (
                <>
                  <dt>Доски</dt>
                  <dd>{boards}</dd>
                </>
              )}
              {languages && (
                <>
                  <dt>Языки</dt>
                  <dd>{languages}</dd>
                </>
              )}
              {(teaching || surfing) && (
                <>
                  <dt>Опыт</dt>
                  <dd>
                    {[teaching && `преподаёт ${teaching}`, surfing && `в сёрфинге ${surfing}`].filter(Boolean).join(", ")}
                    {detail.riding_level ? ` · уровень катания: ${labelOf(STUDENT_LEVEL_LABELS, detail.riding_level).toLowerCase()}` : ""}
                  </dd>
                </>
              )}
              <dt>Стоимость</dt>
              <dd>
                {formatPriceFrom(detail.price_from, detail.currency || "RUB")}
                {detail.contact_note ? ` · ${detail.contact_note}` : ""}
              </dd>
              {detail.schools.length > 0 && (
                <>
                  <dt>Школы</dt>
                  <dd>
                    <span className="gv-ins-links">
                      {detail.schools.map((s) => (
                        <Link key={s.id} href={routes.school(s.slug)} className="chip">
                          {s.name}
                        </Link>
                      ))}
                    </span>
                  </dd>
                </>
              )}
            </dl>
          </div>
          <div className="lesson-info-card">
            <h3>Немного о человеке</h3>
            {detail.about ? (
              <ClampText lines={6}>{detail.about}</ClampText>
            ) : (
              <p className="lesson-hint">Инструктор пока не рассказал о себе.</p>
            )}
            {detail.fun_facts.length > 0 && (
              <>
                <h3 className="gv-ins-facts-title">
                  <Icon name="sun" size={15} /> {detail.fun_facts.length > 1 ? "Забавные факты" : "Забавный факт"}
                </h3>
                <ul className="gv-ins-facts">
                  {detail.fun_facts.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      </section>

      {media.length > 0 && (
        <section className="gv-ins-section" id="media" aria-labelledby="media-title">
          <h2 id="media-title">Фото и видео</h2>
          {photos.length > 0 && (
            <ul className={photos.length === 1 ? "gv-ins-media is-single" : "gv-ins-media"} aria-label="Фотографии">
              {photos.map((m, i) => (
                <li key={m.id}>
                  <a href={m.media.url ?? "#"} target="_blank" rel="noopener noreferrer" aria-label={`Открыть фото ${i + 1} из ${photos.length}`}>
                    <img src={mediaSrc(m.media, photos.length === 1 ? "full" : "thumb") ?? ""} alt={m.media.alt_text || `${name} — фото ${i + 1}`} loading="lazy" />
                  </a>
                </li>
              ))}
            </ul>
          )}
          {videos.length > 0 && (
            <ul className="gv-ins-media" aria-label="Видео" style={{ marginTop: photos.length ? 10 : 0 }}>
              {videos.map((m) => (
                <li key={m.id}>
                  <video controls preload="metadata" poster={m.media.poster_url ?? undefined} aria-label={`Видео: ${name}${m.media.duration_seconds ? `, ${formatClock(m.media.duration_seconds)}` : ""}`}>
                    <source src={m.media.url ?? ""} type={m.media.content_type || undefined} />
                  </video>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {detail.offers.length > 0 && (
        <section className="gv-ins-section" id="offers" aria-labelledby="offers-title">
          <h2 id="offers-title">Занятия и цены</h2>
          <ul className="gv-ins-offers">
            {detail.offers.map((o) => (
              <li key={o.id}>
                <article className="lesson-info-card gv-ins-offer" aria-labelledby={`offer-${o.id}`}>
                  <div className="gv-ins-offer-head">
                    <h3 id={`offer-${o.id}`}>{o.title}</h3>
                    <span className="gv-ins-price">{formatMoney(o.price, o.currency || "RUB") || "по договорённости"}</span>
                  </div>
                  <div className="gv-ins-tags">
                    {labelOf(LESSON_FORMAT_LABELS, o.format) && <Tag variant="soft">{labelOf(LESSON_FORMAT_LABELS, o.format)}</Tag>}
                    {labelOf(STUDENT_LEVEL_LABELS, o.level) && <Tag variant="soft">{labelOf(STUDENT_LEVEL_LABELS, o.level)}</Tag>}
                    {o.duration_min ? <Tag variant="soft">{formatDuration(o.duration_min)}</Tag> : null}
                    {o.capacity > 1 ? <Tag variant="soft">до {o.capacity} чел.</Tag> : null}
                  </div>
                  {o.description && <ClampText lines={4}>{o.description}</ClampText>}
                  {o.spot && (
                    <p>
                      <Icon name="map-pin" size={13} /> Спот: <Link href={routes.spot(o.spot.slug)}>{o.spot.name}</Link>
                    </p>
                  )}
                  <p>
                    <Icon name="board" size={13} />{" "}
                    {o.equipment_included ? `Снаряжение включено${o.equipment_note ? `: ${o.equipment_note}` : ""}` : o.equipment_note || "Снаряжение — своё или по договорённости"}
                  </p>
                  {o.rules && (
                    <p className="lesson-micro">
                      <b>Правила:</b> {o.rules}
                    </p>
                  )}
                  <OfferInquiry handle={detail.handle} offerId={o.id} providerName={name} title={o.title} />
                </article>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="gv-ins-section" id="schedule" aria-labelledby="schedule-title">
        <h2 id="schedule-title">Свободные окна</h2>
        <p className="lesson-safe">
          Выберите время — заявка уйдёт инструктору или школе на подтверждение. Деньги на этом этапе не списываются, условия
          и оплату вы обсудите в переписке.
        </p>
        <div style={{ marginTop: 12 }}>
          {detail.upcoming_slots.length > 0 ? (
            <SlotList handle={detail.handle} slots={detail.upcoming_slots} instructorName={name} />
          ) : (
            <ScheduleEmpty handle={detail.handle} name={name} contact={contact} />
          )}
        </div>
      </section>

      {detail.certificates.length > 0 && (
        <section className="gv-ins-section" id="certificates" aria-labelledby="certs-title">
          <h2 id="certs-title">Сертификаты</h2>
          <ul className="gv-ins-certs">
            {detail.certificates.map((c) => (
              <li className="gv-ins-cert" key={c.id}>
                <span className="gv-ins-cert-main">
                  <b>{c.title}</b>
                  <span>
                    {[c.issuer, c.issued_on && `выдан ${formatDate(c.issued_on, { style: "long" })}`, c.valid_until && `${c.is_expired ? "истёк" : "действует до"} ${formatDate(c.valid_until, { style: "long" })}`]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </span>
                <StatusBadge domain="certificate" status={c.status} />
                {c.scan_available && <CertificateScanButton certificateId={c.id} title={c.title} />}
              </li>
            ))}
          </ul>
          <p className="lesson-micro" style={{ marginTop: 10 }}>
            «Проверен» означает, что модератор сверил документ. Это не гарантия безопасности занятия — оценивайте условия
            и свои силы.
          </p>
        </section>
      )}

      <div className="gv-ins-section">
        <InstructorReviews
          id={detail.id}
          handle={detail.handle}
          name={name}
          initial={reviews}
          ratingAvg={detail.rating_avg}
          ratingCount={detail.rating_count}
        />
      </div>
    </div>
  );
}
