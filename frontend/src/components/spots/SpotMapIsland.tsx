"use client";
/**
 * Map + «Точки на карте» side list (SPT-01). The list is server-rendered (links work without JS and for crawlers);
 * the Leaflet map is loaded client-side only. «Показать на карте» reveals the marker and opens its card.
 */
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { Icon, LoadingState } from "@/components/ui";
import type { MapMarker } from "@/lib/api/spots";
import { routes } from "@/lib/routes";
import { pointFromMarker } from "./SpotMapPoint";
import "./spots.css";

const SpotMap = dynamic(() => import("./SpotMap"), {
  ssr: false,
  loading: () => (
    <div className="gv-leaflet gv-map-loading">
      <LoadingState label="Загружаем карту…" />
    </div>
  ),
});

export function SpotMapIsland({ markers, filtered }: { markers: MapMarker[]; filtered: boolean }) {
  const points = useMemo(() => markers.map(pointFromMarker), [markers]);
  const [focusId, setFocusId] = useState<string | null>(null);
  const clearFocus = useCallback(() => setFocusId(null), []);

  return (
    <div className="spots-overview-map gv-spots-map">
      <div className="mapbox gv-mapbox">
        <SpotMap points={points} focusId={focusId} onFocused={clearFocus} ariaLabel="Интерактивная карта сёрф-спотов" />
        {points.length === 0 && (
          <div className="gv-map-empty" role="status">
            {filtered ? "По выбранным фильтрам точек на карте нет." : "Споты пока не опубликованы."}
          </div>
        )}
      </div>
      <aside className="spots-map-sidebar" aria-labelledby="spots-map-list-title">
        <h3 id="spots-map-list-title">Точки на карте</h3>
        {points.length === 0 ? (
          <p className="small muted">Ничего не найдено — измените фильтры.</p>
        ) : (
          <ul className="gv-map-list">
            {points.map((p) => (
              <li key={p.id} className="map-spot-row">
                <Icon name="map-pin" size={16} />
                <span>
                  <Link href={routes.spot(p.slug)} className="gv-map-list-name">
                    {p.name}
                  </Link>
                  <small>
                    {p.regionName}
                    {p.difficultyLabel ? ` · ${p.difficultyLabel}` : ""}
                    {p.precise ? "" : " · примерно"}
                    {p.isClosed ? " · закрыт" : ""}
                  </small>
                </span>
                <button
                  type="button"
                  className="gv-map-list-show"
                  onClick={() => setFocusId(p.id)}
                  aria-label={`Показать на карте: ${p.name}`}
                  title="Показать на карте"
                >
                  <Icon name="target" size={18} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
