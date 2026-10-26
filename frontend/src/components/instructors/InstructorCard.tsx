/**
 * Catalogue card of an instructor (prototype `article.person-card`, PUBLIC_SCREENS §3.2; INS-01, INS-03).
 * Server Component with client islands (HeartButton). Ratings and prices are server data only.
 */
import Link from "next/link";
import { ButtonLink, CertificateBadge, HeartButton, Icon, MediaImage, Rating } from "@/components/ui";
import { BOARD_TYPE_LABELS, labelOf, STUDENT_LEVEL_LABELS, type InstructorCard as Card } from "@/lib/api/learning";
import { formatPriceFrom, plural, WORDS } from "@/lib/format";
import { routes } from "@/lib/routes";
import { yearsSince } from "./catalog";

export function instructorName(i: Pick<Card, "display_name" | "first_name" | "last_name" | "handle">): string {
  return i.display_name || [i.first_name, i.last_name].filter(Boolean).join(" ") || i.handle;
}

export function joinLabels(codes: readonly string[] | null | undefined, dict: Record<string, string>): string {
  return (codes ?? []).map((c) => labelOf(dict, c)).filter(Boolean).join(", ");
}

export function experienceText(since: number | null | undefined): string {
  const years = yearsSince(since);
  if (years === null) return "";
  if (years === 0) return "меньше года";
  return `${years} ${plural(years, WORDS.year)}`;
}

export function InstructorCard({ instructor, boardLabels }: { instructor: Card; boardLabels?: Record<string, string> }) {
  const name = instructorName(instructor);
  const href = routes.instructor(instructor.handle);
  const region = instructor.regions?.[0]?.name;
  const spots = instructor.spots?.map((s) => s.name).join(", ");
  const boards = joinLabels(instructor.board_types, { ...BOARD_TYPE_LABELS, ...boardLabels });
  const levels = joinLabels(instructor.student_levels, STUDENT_LEVEL_LABELS);
  const experience = experienceText(instructor.teaching_since ?? instructor.surfing_since);

  return (
    <article className="person-card gv-ins-card" aria-labelledby={`ins-${instructor.id}`}>
      <div className="person-photo gv-person-teaser-photo">
        <MediaImage media={instructor.avatar} alt={`Фото: ${name}`} placeholder="Фото пока нет" />
        {region && (
          <span className="region-on-photo">
            <span className="region-tag" title={`Регион работы: ${region}`}>
              <Icon name="map-pin" size={12} />
              <span>{region}</span>
            </span>
          </span>
        )}
        <HeartButton type="instructor" id={instructor.id} name={name} />
      </div>
      <div className="person-body">
        <div className="person-name">
          <h3 className="gv-clamp-2" title={name} id={`ins-${instructor.id}`}>
            <Link href={href}>{name}</Link>
          </h3>
          <Rating value={instructor.rating_avg} count={instructor.rating_count} href={`${href}#reviews`} />
        </div>
        <div className="fieldline">
          <span className="sym">
            <Icon name="clover" size={16} />
          </span>
          <div className="gv-ins-role">
            <span>Инструктор по сёрфингу</span>
            <CertificateBadge status={instructor.certificate_status} compact />
          </div>
        </div>
        {spots && (
          <div className="fieldline">
            <span className="sym">
              <Icon name="target" size={16} />
            </span>
            <div className="gv-clamp-2" title={spots}>
              <b>Споты</b>
              {spots}
            </div>
          </div>
        )}
        {boards && (
          <div className="fieldline">
            <span className="sym">
              <Icon name="board" size={16} />
            </span>
            <div className="gv-clamp-2">
              <b>Доски</b>
              {boards}
            </div>
          </div>
        )}
        {(experience || levels) && (
          <div className="tiny-cols">
            {experience && (
              <div className="fieldline">
                <span className="sym">
                  <Icon name="clock" size={16} />
                </span>
                <div>
                  <b>Опыт</b>
                  {experience}
                </div>
              </div>
            )}
            {levels && (
              <div className="fieldline">
                <span className="sym">
                  <Icon name="level" size={16} />
                </span>
                <div>
                  <b>Уровень учеников</b>
                  {levels}
                </div>
              </div>
            )}
          </div>
        )}
        {instructor.headline && (
          <p className="gv-ins-headline gv-clamp-2" title={instructor.headline}>
            {instructor.headline}
          </p>
        )}
        <div className="instructor-price">
          <span>
            Занятие <strong>{formatPriceFrom(instructor.price_from, instructor.currency || "RUB")}</strong>
          </span>
          {instructor.schools?.length ? (
            <span className="instructor-ready" title={instructor.schools.map((s) => s.name).join(", ")}>
              <Icon name="school" size={12} /> В команде школы
            </span>
          ) : null}
        </div>
        <ButtonLink href={href} variant="primary" className="card-cta" icon="calendar" iconRight="chevron-right">
          Профиль, отзывы и запись
        </ButtonLink>
      </div>
    </article>
  );
}
