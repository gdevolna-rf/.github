import { cx } from "@/lib/cx";
import { COMPASS, COMPASS_POINTS, compassCodes, type Choice } from "@/lib/labels";
import type { CompassPoint } from "@/lib/api/types";
import { Icon } from "./Icon";

const C = 100; // centre of the 200×200 viewBox
const RAD = Math.PI / 180;
const MAJOR: CompassPoint[] = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

/** Rounded to 0.01 so server (Node) and browser render identical attributes (no hydration mismatch). */
const round = (n: number) => Math.round(n * 100) / 100;

function polar(r: number, deg: number): [number, number] {
  return [round(C + r * Math.sin(deg * RAD)), round(C - r * Math.cos(deg * RAD))];
}
const pt = ([x, y]: [number, number]) => `${x.toFixed(2)} ${y.toFixed(2)}`;

/** Annular sector (petal) for one of 16 points: ±10.5° around the azimuth, from r1 to r2. */
function petalPath(deg: number, r1 = 15, r2 = 66, half = 10.5): string {
  const a = deg - half;
  const b = deg + half;
  return [
    `M${pt(polar(r1, a))}`,
    `L${pt(polar(r2, a))}`,
    `A${r2} ${r2} 0 0 1 ${pt(polar(r2, b))}`,
    `L${pt(polar(r1, b))}`,
    `A${r1} ${r1} 0 0 0 ${pt(polar(r1, a))}`,
    "Z",
  ].join(" ");
}

function rimArc(deg: number, r = 75, half = 11.25): string {
  return `M${pt(polar(r, deg - half))} A${r} ${r} 0 0 1 ${pt(polar(r, deg + half))}`;
}

/** Circular mean of the highlighted azimuths; null when they cancel out (e.g. N + S). */
export function meanDirection(points: CompassPoint[]): number | null {
  if (!points.length) return null;
  let x = 0;
  let y = 0;
  for (const p of points) {
    x += Math.sin(COMPASS[p].deg * RAD);
    y += Math.cos(COMPASS[p].deg * RAD);
  }
  const len = Math.hypot(x, y) / points.length;
  if (len < 0.5) return null;
  return ((Math.atan2(x, y) / RAD) + 360) % 360;
}

/** Human text for the list: «Северо-запад, Север» (≤2) or «СЗ, ССЗ, С» (3+). */
export function describeDirections(points: CompassPoint[]): string {
  if (!points.length) return "";
  const sorted = COMPASS_POINTS.filter((p) => points.includes(p));
  if (sorted.length <= 2) return sorted.map((p) => COMPASS[p].name).join(", ");
  return sorted.map((p) => COMPASS[p].short).join(", ");
}

export interface CompassRoseProps {
  /** 16-point codes or `{code, label, short, degrees}` objects from the API
   *  (spot.best_wind_directions / best_swell_directions). Unknown codes are ignored. */
  directions: ReadonlyArray<Choice | null | undefined> | null | undefined;
  kind?: "wind" | "swell";
  /** Card title; defaults to «Направление ветра» / «Направление свелла». */
  title?: string;
  /** Render only the SVG (no card, title, captions). */
  bare?: boolean;
  /** Max SVG width in px. */
  size?: number;
  className?: string;
}

/**
 * Wind / swell rose (SPT-04): typically favourable directions as highlighted petals on a 16-point compass,
 * explicitly «не прогноз». Directions are where the wind blows FROM / the swell comes FROM (meteorological).
 * Visual language of the prototype rose: #effaff disc, dashed rings, blue (#087da8) highlight, pink accent
 * on the main direction. Server Component (pure SVG).
 */
export function CompassRose({ directions, kind = "wind", title, bare, size = 198, className }: CompassRoseProps) {
  const points = compassCodes(directions);
  const mean = meanDirection(points);
  const fill = kind === "wind" ? "#087da8" : "#1f9cbd";
  const label = kind === "wind" ? "ветра" : "свелла";
  const described = describeDirections(points);
  const ariaLabel = points.length
    ? `Роза ${label}: типично благоприятные направления — ${COMPASS_POINTS.filter((p) => points.includes(p))
        .map((p) => COMPASS[p].name.toLowerCase())
        .join(", ")}`
    : `Роза ${label}: направления не указаны`;

  const svg = (
    <svg viewBox="0 0 200 200" role="img" aria-label={ariaLabel} className="gv-rose-svg" style={{ maxWidth: size }}>
      <circle cx={C} cy={C} r={75} fill="#effaff" stroke="#bedde9" strokeWidth={1.3} />
      <circle cx={C} cy={C} r={55} fill="none" stroke="#cee8f2" strokeDasharray="3 5" />
      <circle cx={C} cy={C} r={35} fill="none" stroke="#cee8f2" />
      {COMPASS_POINTS.map((p) => {
        const major = MAJOR.includes(p);
        const [x1, y1] = polar(major ? 12 : 64, COMPASS[p].deg);
        const [x2, y2] = polar(75, COMPASS[p].deg);
        return <line key={p} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#d7eaf3" strokeWidth={major ? 1.2 : 1} />;
      })}
      {points.map((p) => (
        <g key={p}>
          <path d={petalPath(COMPASS[p].deg)} fill={fill} fillOpacity={0.84} stroke="#ffffff" strokeWidth={1.2} />
          <path d={rimArc(COMPASS[p].deg)} fill="none" stroke={fill} strokeWidth={4} strokeLinecap="round" />
        </g>
      ))}
      {MAJOR.map((p) => {
        const [x, y] = polar(88, COMPASS[p].deg);
        const on = points.includes(p);
        return (
          <text
            key={p}
            x={x}
            y={round(y + 3.5)}
            textAnchor="middle"
            fontSize={10}
            fontWeight={on ? 800 : 700}
            fill={on ? "#064c73" : "#3f7491"}
            fontFamily="inherit"
          >
            {COMPASS[p].short}
          </text>
        );
      })}
      {mean !== null && (() => {
        const [x, y] = polar(66, mean);
        return <circle cx={x} cy={y} r={6.5} fill="#f86189" stroke="#fff" strokeWidth={2.5} />;
      })()}
      <circle cx={C} cy={C} r={points.length ? 4.5 : 9} fill={points.length ? fill : "#b0d7e7"} />
    </svg>
  );

  if (bare) return svg;

  return (
    <figure className={cx("rose-card gv-rose", className)}>
      <span className="rose-icon" aria-hidden="true">
        <Icon name={kind === "wind" ? "waves" : "diamond"} size={21} />
      </span>
      <h4>{title ?? (kind === "wind" ? "Направление ветра" : "Направление свелла")}</h4>
      {svg}
      <figcaption>
        <strong>{points.length ? described : "Направление уточняется"}</strong>
        <small>
          {points.length
            ? kind === "wind"
              ? "Откуда дует · типично благоприятный ветер, не прогноз"
              : "Откуда приходит · типичный свелл, не прогноз"
            : "Уточняйте под прогноз"}
        </small>
      </figcaption>
    </figure>
  );
}
