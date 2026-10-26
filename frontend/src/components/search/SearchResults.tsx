/**
 * Grouped results of the global search (NAV-04). Server-safe (no hooks): rendered by app/search/page.tsx.
 * Each group: heading with the total, up to N rows (photo, title, subtitle → the object's page) and
 * «Показать ещё (N)» to the section catalogue with the same query (`more_url`).
 */
import Link from "next/link";
import type { SearchGroup, SearchResult, SearchType } from "@/lib/api/search";
import { plural, WORDS } from "@/lib/format";
import { Icon, type IconName } from "@/components/ui/Icon";
import { MediaImage } from "@/components/ui/MediaImage";
import { hiddenCount } from "./searchModel";

export const TYPE_ICONS: Record<SearchType, IconName> = {
  spots: "target",
  instructors: "clover",
  schools: "school",
  shapers: "ruler",
  boards: "board",
  equipment: "diamond",
  surfers: "heart",
};

/** Only same-site paths are rendered as links (the API returns frontend routes). */
export function internalHref(url: string | null | undefined, fallback = "/"): string {
  return url && url.startsWith("/") && !url.startsWith("//") ? url : fallback;
}

export function SearchResults({ groups, single = false }: { groups: SearchGroup[]; single?: boolean }) {
  return (
    <div className="gv-sr-groups">
      {groups.map((group) => (
        <SearchGroupBlock key={group.type} group={group} single={single} />
      ))}
    </div>
  );
}

function SearchGroupBlock({ group, single }: { group: SearchGroup; single: boolean }) {
  const hidden = hiddenCount(group);
  const headingId = `sr-${group.type}`;
  return (
    <section className="gv-sr-group" aria-labelledby={headingId}>
      <div className="gv-sr-group-head">
        <h2 id={headingId} className="gv-sr-group-title">
          <Icon name={TYPE_ICONS[group.type] ?? "search"} size={20} />
          <span>{group.label}</span>
        </h2>
        <span className="gv-sr-group-count">
          {group.total} {plural(group.total, WORDS.result)}
        </span>
      </div>
      <ul className="gv-sr-list">
        {group.results.map((r) => (
          <li key={`${r.type}-${r.id}`}>
            <SearchResultRow result={r} type={group.type} />
          </li>
        ))}
      </ul>
      {hidden > 0 && (
        <div className="gv-sr-more">
          <Link href={internalHref(group.more_url)} className="pill-btn" aria-label={`Показать ещё ${hidden}: ${group.label}`}>
            <span>
              Показать ещё ({hidden}){single ? " в каталоге" : ""}
            </span>
            <Icon name="arrow" size={16} />
          </Link>
        </div>
      )}
    </section>
  );
}

export function SearchResultRow({ result, type }: { result: SearchResult; type: SearchType }) {
  const round = type === "instructors" || type === "surfers";
  return (
    <Link href={internalHref(result.url)} className="gv-sr-item">
      <span className={round ? "gv-sr-thumb is-round" : "gv-sr-thumb"}>
        {result.image ? (
          <MediaImage media={result.image} alt="" prefer="thumb" placeholder="" />
        ) : (
          <span className="gv-sr-thumb-icon" aria-hidden="true">
            <Icon name={TYPE_ICONS[type] ?? "search"} size={22} />
          </span>
        )}
      </span>
      <span className="gv-sr-text">
        <b className="gv-clamp-2" title={result.title}>
          {result.title}
        </b>
        {result.subtitle && (
          <small className="gv-clamp-2" title={result.subtitle}>
            {result.subtitle}
          </small>
        )}
      </span>
      <Icon name="chevron-right" size={18} className="gv-sr-arrow" />
    </Link>
  );
}
