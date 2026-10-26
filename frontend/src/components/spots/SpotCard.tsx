/**
 * Catalogue spot card (prototype `.spot-card`, DESIGN_SYSTEM §3.14): photo with region badge, favourite heart and
 * the pencil «Предложить правку» (SPT-07; opens the form on the spot page), rating, tags, wind/season signals,
 * summary, first hazard, closed / seasonal state, CTA. Server Component with client islands.
 */
import Link from "next/link";
import { ButtonLink, HeartButton, Icon, MediaImage, Rating, Tag } from "@/components/ui";
import { formatDay, type SpotCard as SpotCardData } from "@/lib/api/spots";
import { COMPASS, compassCodes } from "@/lib/labels";
import { routes } from "@/lib/routes";

export function windSummary(spot: Pick<SpotCardData, "best_wind_directions">): string {
  const codes = compassCodes(spot.best_wind_directions);
  if (!codes.length) return "";
  return codes.length <= 2 ? codes.map((c) => COMPASS[c].name).join(", ") : codes.map((c) => COMPASS[c].short).join(", ");
}

export function SpotCard({ spot }: { spot: SpotCardData }) {
  const region = spot.region?.name;
  const wind = windSummary(spot);
  const hazard = spot.hazards?.map((h) => h.label).slice(0, 3).join(", ");
  return (
    <article className="spot-card gv-spot-card">
      <div className="spot-pic">
        <MediaImage media={spot.cover} alt={`Спот «${spot.name}»`} />
        {region && (
          <span className="photo-badge">
            <Icon name="map-pin" size={12} /> {region}
          </span>
        )}
        <HeartButton type="spot" id={spot.id} name={spot.name} />
        <Link
          href={`${routes.spot(spot.slug)}?edit=1`}
          className="gv-spot-edit-trigger"
          aria-label={`Предложить правку данных спота «${spot.name}»`}
          title="Предложить правку"
        >
          <Icon name="pencil" size={16} />
        </Link>
      </div>
      <div className="spot-body">
        <div className="spot-title">
          <h3 className="gv-clamp-2" title={spot.name}>
            <Link href={routes.spot(spot.slug)}>{spot.name}</Link>
          </h3>
          <Rating value={spot.rating_avg} count={spot.rating_count} />
        </div>
        <div className="conditions">
          {spot.break_type?.label && <Tag>{spot.break_type.label}</Tag>}
          {spot.difficulty?.label && <Tag>{spot.difficulty.label}</Tag>}
          {spot.season && <Tag>{spot.season}</Tag>}
        </div>
        {(wind || spot.best_swell_directions?.length > 0) && (
          <div className="spot-signal">
            {wind && (
              <span>
                <Icon name="waves" size={11} /> Ветер: {wind}
              </span>
            )}
            {!spot.precise && (
              <span>
                <Icon name="target" size={11} /> Примерное место
              </span>
            )}
          </div>
        )}
        {spot.is_closed ? (
          <p className="gv-spot-card-alert">
            <Icon name="lock" size={13} /> Временно закрыт{spot.closed_until ? ` до ${new Date(spot.closed_until).toLocaleDateString("ru-RU")}` : ""}
          </p>
        ) : spot.seasonal_warning ? (
          <p className="gv-spot-card-alert is-warn">
            <Icon name="alert" size={13} /> <span className="gv-clamp-2">{spot.seasonal_warning}</span>
          </p>
        ) : null}
        {spot.short_description && <p className="spot-summary gv-clamp-3">{spot.short_description}</p>}
        {hazard && (
          <p className="spot-safety gv-clamp-2">
            <Icon name="alert" size={12} /> {hazard}
          </p>
        )}
        <ButtonLink href={routes.spot(spot.slug)} variant="primary" className="card-cta" iconRight="arrow">
          Подробнее о споте
        </ButtonLink>
      </div>
    </article>
  );
}
