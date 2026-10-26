/**
 * Home teasers built from public API data (GET /spots, /instructors) — Server Components with client islands
 * (HeartButton). They reuse the prototype card classes (.spot-card / .person-card); catalogue pages may
 * replace them with their full cards later.
 */
import Link from "next/link";
import type { ReactNode } from "react";
import type { InstructorListItem, RegionRef, SpotListItem } from "@/lib/api/types";
import { formatPriceFrom } from "@/lib/format";
import { choiceLabel, SPOT_BREAK_LABELS, SPOT_DIFFICULTY_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { ButtonLink } from "@/components/ui/Button";
import { CertificateBadge } from "@/components/ui/CertificateBadge";
import { HeartButton } from "@/components/ui/HeartButton";
import { Icon } from "@/components/ui/Icon";
import { MediaImage } from "@/components/ui/MediaImage";
import { Rating } from "@/components/ui/Rating";
import { Tag } from "@/components/ui/Badge";
import { SectionTitle } from "@/components/layout/PageBlocks";

const regionName = (r: RegionRef | string | null | undefined) => (typeof r === "string" ? r : (r?.name ?? ""));

export function SpotTeaserCard({ spot }: { spot: SpotListItem }) {
  const region = regionName(spot.region);
  return (
    <article className="spot-card">
      <div className="spot-pic">
        <MediaImage media={spot.cover} alt={`Спот «${spot.name}»`} />
        {region && (
          <span className="photo-badge">
            <Icon name="map-pin" size={12} /> {region}
          </span>
        )}
        <HeartButton type="spot" id={spot.id} name={spot.name} />
      </div>
      <div className="spot-body">
        <div className="spot-title">
          <h3 className="gv-clamp-2" title={spot.name}>
            <Link href={routes.spot(spot.slug)}>{spot.name}</Link>
          </h3>
          <Rating value={spot.rating_avg} count={spot.rating_count} />
        </div>
        <div className="conditions">
          {choiceLabel(spot.break_type, SPOT_BREAK_LABELS) && <Tag>{choiceLabel(spot.break_type, SPOT_BREAK_LABELS)}</Tag>}
          {choiceLabel(spot.difficulty, SPOT_DIFFICULTY_LABELS) && <Tag>{choiceLabel(spot.difficulty, SPOT_DIFFICULTY_LABELS)}</Tag>}
          {spot.season && <Tag>{spot.season}</Tag>}
        </div>
        {spot.short_description && <p className="spot-summary gv-clamp-3">{spot.short_description}</p>}
        <ButtonLink href={routes.spot(spot.slug)} variant="primary" className="card-cta" iconRight="arrow">
          Подробнее о споте
        </ButtonLink>
      </div>
    </article>
  );
}

export function InstructorTeaserCard({ instructor }: { instructor: InstructorListItem }) {
  const name = instructor.display_name || instructor.account?.display_name || instructor.handle;
  const photo = instructor.photo ?? instructor.avatar ?? instructor.account?.avatar ?? null;
  const region = instructor.regions?.[0]?.name;
  const spots = instructor.spots?.map((s) => s.name).join(", ");
  return (
    <article className="person-card">
      <div className="person-photo gv-person-teaser-photo">
        <MediaImage media={photo} alt={`Фото: ${name}`} />
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
          <h3 className="gv-clamp-2" title={name}>
            {name}
          </h3>
          <Rating value={instructor.rating_avg} count={instructor.rating_count} />
        </div>
        <div className="fieldline">
          <span className="sym">
            <Icon name="clover" size={16} />
          </span>
          <div>
            Инструктор по сёрфингу <CertificateBadge status={instructor.certificate_status} hideNone compact />
          </div>
        </div>
        {spots && (
          <div className="fieldline">
            <span className="sym">
              <Icon name="target" size={16} />
            </span>
            <div className="gv-clamp-2">
              <b>Споты</b>
              {spots}
            </div>
          </div>
        )}
        {instructor.headline && <p className="small muted gv-clamp-2">{instructor.headline}</p>}
        <div className="instructor-price">
          <span>
            Занятие <strong>{formatPriceFrom(instructor.price_from, instructor.currency)}</strong>
          </span>
        </div>
        <ButtonLink href={routes.instructor(instructor.handle)} variant="primary" className="card-cta" icon="calendar" iconRight="chevron-right">
          Профиль, отзывы и запись
        </ButtonLink>
      </div>
    </article>
  );
}

export function TeaserSection({ title, href, linkLabel, children }: { title: string; href: string; linkLabel: string; children: ReactNode }) {
  return (
    <section className="section">
      <div className="gv-teaser-head">
        <SectionTitle>{title}</SectionTitle>
        <ButtonLink href={href} variant="link" iconRight="arrow">
          {linkLabel}
        </ButtonLink>
      </div>
      <div className="grid grid-3 gv-teaser-grid">{children}</div>
    </section>
  );
}
