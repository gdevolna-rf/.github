/**
 * Leaflet-free helpers of the spot map (safe to import on the server and in tests): the point model and the
 * popup card markup.
 */
import type { MapMarker } from "@/lib/api/spots";
import { formatRating, plural, WORDS } from "@/lib/format";
import { routes } from "@/lib/routes";

export interface SpotMapPoint {
  id: string;
  slug: string;
  name: string;
  lat: number;
  lng: number;
  precise: boolean;
  regionName?: string;
  difficultyLabel?: string;
  ratingAvg?: string | number;
  ratingCount?: number;
  isClosed?: boolean;
  thumbnailUrl?: string | null;
}

export function pointFromMarker(m: MapMarker): SpotMapPoint {
  return {
    id: m.id,
    slug: m.slug,
    name: m.name,
    lat: m.lat,
    lng: m.lng,
    precise: m.precise,
    regionName: m.region_name,
    difficultyLabel: m.difficulty_label,
    ratingAvg: m.rating_avg,
    ratingCount: m.rating_count,
    isClosed: m.is_closed,
    thumbnailUrl: m.thumbnail_url,
  };
}

export const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] ?? c);

export function popupHtml(point: SpotMapPoint, withLink = true): string {
  const rating =
    point.ratingCount && point.ratingCount > 0
      ? `★ ${esc(formatRating(point.ratingAvg ?? 0))} <small>(${point.ratingCount} ${plural(point.ratingCount, WORDS.review)})</small>`
      : "Пока без отзывов";
  const meta = [point.regionName, point.difficultyLabel].filter(Boolean).map((s) => esc(String(s))).join(" · ");
  const img = point.thumbnailUrl ? `<img src="${esc(point.thumbnailUrl)}" alt="" loading="lazy" />` : "";
  const notes = [
    point.isClosed ? `<span class="gv-map-card-warn">Временно закрыт</span>` : "",
    point.precise ? "" : `<span class="gv-map-card-note">Точка показана приблизительно</span>`,
  ].join("");
  const link = withLink
    ? `<a class="gv-map-card-link" href="${esc(routes.spot(point.slug))}">Подробнее о споте →</a>`
    : "";
  return `<div class="gv-map-card">${img}<div class="gv-map-card-body"><b>${esc(point.name)}</b><span>${meta}</span><span class="gv-map-card-rating">${rating}</span>${notes}${link}</div></div>`;
}

