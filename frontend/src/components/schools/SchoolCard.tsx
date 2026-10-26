/**
 * School card for /schools (SCH-02): prototype `.spot-card` language — cover photo with region pill and heart,
 * name + rating, formats, short description, «от …» price, CTA to the school page. Server-safe.
 */
import Link from "next/link";
import type { SchoolCard as SchoolCardData } from "@/lib/api/learning";
import { LESSON_FORMAT_LABELS, labelOf } from "@/lib/api/learning";
import { mediaSrc } from "@/lib/api/media";
import { formatPriceFrom } from "@/lib/format";
import { routes } from "@/lib/routes";
import { Tag } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { HeartButton } from "@/components/ui/HeartButton";
import { Icon } from "@/components/ui/Icon";
import { MediaImage } from "@/components/ui/MediaImage";
import { Rating } from "@/components/ui/Rating";

export function SchoolCard({ school }: { school: SchoolCardData }) {
  const place = [school.region?.name, school.city].filter(Boolean).join(" · ");
  const logo = mediaSrc(school.logo, "thumb");
  return (
    <article className="spot-card gv-school-card">
      <div className="spot-pic">
        <MediaImage media={school.cover ?? school.logo} alt={`Сёрф-школа «${school.name}»`} prefer="thumb" />
        {logo && school.cover && (
          <span className="gv-school-logo" aria-hidden="true">
            <img src={logo} alt="" loading="lazy" />
          </span>
        )}
        {school.region?.name && (
          <span className="photo-badge">
            <Icon name="map-pin" size={12} /> {school.region.name}
          </span>
        )}
        <HeartButton type="organization" id={school.id} name={school.name} />
      </div>
      <div className="spot-body">
        <div className="spot-title">
          <h3 className="gv-clamp-2" title={school.name}>
            <Link href={routes.school(school.slug)}>{school.name}</Link>
          </h3>
          <Rating value={school.rating_avg} count={school.rating_count} href={`${routes.school(school.slug)}#reviews`} />
        </div>
        {place && <p className="gv-school-meta gv-clamp-1">{place}</p>}
        {school.formats?.length > 0 && (
          <div className="conditions">
            {school.formats.map((f) => (
              <Tag key={f}>{labelOf(LESSON_FORMAT_LABELS, f)}</Tag>
            ))}
          </div>
        )}
        {school.short_description && <p className="spot-summary gv-clamp-3">{school.short_description}</p>}
        <p className="gv-school-price">
          <span>Занятие</span>
          <b>{formatPriceFrom(school.price_from, school.currency || "RUB")}</b>
        </p>
        <ButtonLink href={routes.school(school.slug)} variant="primary" className="card-cta" iconRight="arrow">
          Программы и запись
        </ButtonLink>
      </div>
    </article>
  );
}
