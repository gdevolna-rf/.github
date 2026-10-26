import Link from "next/link";
import { cx } from "@/lib/cx";
import { formatRating, plural, pluralize, WORDS } from "@/lib/format";

const STAR = "M12 2.6l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.5l-5.9 3.1 1.2-6.5L2.5 9.5l6.6-.9L12 2.6z";

/** Five stars filled proportionally to `value` (0…5), e.g. 4.3 → 4 full + 30 % (fixes «always 5 gold stars»). */
export function Stars({ value, size = 14, tone = "gold" }: { value: number; size?: number; tone?: "gold" | "blue" }) {
  const pct = Math.max(0, Math.min(100, (Number(value) / 5) * 100));
  const row = (filled: boolean) => (
    <span className="gv-stars-row" aria-hidden="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <svg key={i} viewBox="0 0 24 24" width={size} height={size} className={filled ? "is-filled" : "is-empty"}>
          <path d={STAR} />
        </svg>
      ))}
    </span>
  );
  return (
    <span className={cx("gv-stars", `tone-${tone}`)} style={{ height: size }}>
      {row(false)}
      <span className="gv-stars-fill" style={{ width: `${pct}%` }}>
        {row(true)}
      </span>
    </span>
  );
}

export interface RatingProps {
  value: number | string | null | undefined;
  count?: number | null;
  /** compact: «★ 4,9 (24)» like spot cards; full: stars + «4,9 · 24 отзыва» */
  variant?: "compact" | "full";
  /** Link to the reviews (the prototype's rating link opens reviews). */
  href?: string;
  className?: string;
}

/**
 * Average from published reviews only (TRUST-01). With 0 reviews shows «Пока без отзывов» instead of 0,0.
 */
export function Rating({ value, count, variant = "compact", href, className }: RatingProps) {
  const n = count ?? 0;
  const v = Number(value ?? 0);
  if (!n) {
    return <span className={cx("gv-rating is-empty", className)}>Пока без отзывов</span>;
  }
  const label = `Рейтинг ${formatRating(v)} из 5, ${pluralize(n, WORDS.review)}`;
  const content =
    variant === "full" ? (
      <>
        <Stars value={v} />
        <b>{formatRating(v)}</b>
        <small>
          {n} {plural(n, WORDS.review)}
        </small>
      </>
    ) : (
      <>
        <svg viewBox="0 0 24 24" width={13} height={13} className="gv-rating-star" aria-hidden="true">
          <path d={STAR} />
        </svg>
        <b>{formatRating(v)}</b>
        <small>({n})</small>
      </>
    );
  if (href) {
    return (
      <Link href={href} className={cx("gv-rating rating-link", className)} aria-label={`${label}. Читать отзывы`}>
        {content}
      </Link>
    );
  }
  return (
    <span className={cx("gv-rating", className)} role="img" aria-label={label}>
      {content}
    </span>
  );
}

export { STAR as STAR_PATH };
