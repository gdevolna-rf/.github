"use client";
/**
 * Interactive spot map (SPT-01, SPT-12): OpenStreetMap tiles, clustered markers, a card in the popup on
 * marker click (keyboard: Tab to a marker, Enter opens the card). Approximate spots (precise=false) get a
 * dashed marker and a translucent area instead of an exact pin. Leaflet touches `window`, so this module is
 * loaded only on the client via next/dynamic (see SpotMapIsland).
 */
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import L from "leaflet";
import "leaflet.markercluster";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import { popupHtml, type SpotMapPoint } from "./SpotMapPoint";

export interface SpotMapProps {
  points: SpotMapPoint[];
  /** Spot to reveal (zoom to its cluster and open the card), e.g. from the side list. */
  focusId?: string | null;
  /** Called after the focused card is shown so the parent can reset focusId. */
  onFocused?: () => void;
  /** Single-spot mode (detail page): no clustering, fixed zoom, no popup link. */
  single?: boolean;
  /** Radius of the «approximate» area in metres. */
  approxRadius?: number;
  ariaLabel?: string;
  className?: string;
}

const RUSSIA: L.LatLngTuple = [60, 100];
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

function pinIcon(point: SpotMapPoint): L.DivIcon {
  const cls = ["gv-map-pin", point.precise ? "" : "is-approx", point.isClosed ? "is-closed" : ""].filter(Boolean).join(" ");
  return L.divIcon({
    className: "gv-map-pin-wrap",
    html: `<span class="${cls}"><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 1 1 13 0C18.5 15.4 12 21 12 21Z" fill="currentColor" stroke="#fff" stroke-width="1.6"/><circle cx="12" cy="10" r="2.4" fill="#fff"/></svg></span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 32],
    popupAnchor: [0, -28],
  });
}

function Layers({ points, focusId, onFocused, single, approxRadius = 4000 }: SpotMapProps) {
  const map = useMap();
  const router = useRouter();
  const markers = useRef(new Map<string, L.Marker>());
  const cluster = useRef<L.MarkerClusterGroup | null>(null);

  useEffect(() => {
    const group: L.MarkerClusterGroup | L.LayerGroup = single
      ? L.layerGroup()
      : L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 50, spiderfyOnMaxZoom: true });
    const areas = L.layerGroup();
    markers.current.clear();
    for (const p of points) {
      if (!Number.isFinite(p.lat) || !Number.isFinite(p.lng)) continue;
      const marker = L.marker([p.lat, p.lng], {
        icon: pinIcon(p),
        title: p.name,
        alt: p.name,
        keyboard: true,
        riseOnHover: true,
      });
      marker.bindPopup(popupHtml(p, !single), { maxWidth: 260, minWidth: 220, className: "gv-map-popup" });
      marker.on("popupopen", (e) => {
        const el = (e as L.PopupEvent).popup.getElement();
        const a = el?.querySelector<HTMLAnchorElement>("a.gv-map-card-link");
        if (a) {
          a.onclick = (ev) => {
            if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.button !== 0) return;
            ev.preventDefault();
            router.push(a.getAttribute("href") ?? "/");
          };
        }
      });
      group.addLayer(marker);
      markers.current.set(p.id, marker);
      if (!p.precise) {
        areas.addLayer(
          L.circle([p.lat, p.lng], {
            radius: approxRadius,
            color: "#0390bd",
            weight: 1,
            dashArray: "4 4",
            fillColor: "#0390bd",
            fillOpacity: 0.08,
            interactive: false,
          }),
        );
      }
    }
    areas.addTo(map);
    group.addTo(map);
    cluster.current = single ? null : (group as L.MarkerClusterGroup);

    const valid = points.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng));
    if (valid.length === 0) map.setView(RUSSIA, 3);
    else if (valid.length === 1) map.setView([valid[0].lat, valid[0].lng], single ? (valid[0].precise ? 12 : 10) : 9);
    else map.fitBounds(L.latLngBounds(valid.map((p) => [p.lat, p.lng] as L.LatLngTuple)), { padding: [36, 36], maxZoom: 9 });

    return () => {
      group.remove();
      areas.remove();
    };
  }, [map, points, single, approxRadius, router]);

  useEffect(() => {
    if (!focusId) return;
    const marker = markers.current.get(focusId);
    if (!marker) return;
    const reveal = () => {
      marker.openPopup();
      onFocused?.();
    };
    if (cluster.current) cluster.current.zoomToShowLayer(marker, reveal);
    else {
      map.setView(marker.getLatLng(), Math.max(map.getZoom(), 9));
      reveal();
    }
  }, [focusId, map, onFocused]);

  return null;
}

export default function SpotMap(props: SpotMapProps) {
  const { ariaLabel = "Карта спотов", className } = props;
  return (
    <div className="gv-leaflet-wrap" role="region" aria-label={ariaLabel}>
      <MapContainer
        center={RUSSIA}
        zoom={3}
        minZoom={2}
        scrollWheelZoom={false}
        worldCopyJump
        className={className ?? "gv-leaflet"}
        attributionControl
      >
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution={ATTRIBUTION} maxZoom={18} />
        <Layers {...props} />
      </MapContainer>
    </div>
  );
}
