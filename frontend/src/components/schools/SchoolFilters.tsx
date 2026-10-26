"use client";
/**
 * /schools filters (prototype `.filters` row): region and spot apply immediately, the text search on submit.
 * State lives in the URL (?region=&spot=&q=) so results are shareable and crawlable; changing a filter drops ?page.
 */
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button, Icon } from "@/components/ui";
import { routes } from "@/lib/routes";
import { schoolsHref, type SchoolFilterValues } from "./href";

export interface FilterOption {
  value: string;
  label: string;
}

export function SchoolFilters({
  values,
  regions,
  spots,
}: {
  values: SchoolFilterValues;
  regions: FilterOption[];
  spots: Array<FilterOption & { region?: string }>;
}) {
  const router = useRouter();
  const [q, setQ] = useState(values.q);
  useEffect(() => setQ(values.q), [values.q]);

  const apply = (next: Partial<SchoolFilterValues>) => {
    const merged = { ...values, q, ...next };
    // a spot from another region would give an empty list — drop it when the region changes
    if (next.region !== undefined && merged.spot) {
      const spot = spots.find((s) => s.value === merged.spot);
      if (spot?.region && next.region && spot.region !== next.region) merged.spot = "";
    }
    router.replace(schoolsHref(merged), { scroll: false });
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    apply({ q });
  };

  const visibleSpots = values.region ? spots.filter((s) => !s.region || s.region === values.region) : spots;
  const dirty = Boolean(values.region || values.spot || values.q);

  return (
    <form className="filters gv-school-filters" role="search" aria-label="Фильтры школ" onSubmit={onSubmit}>
      <div className="filter">
        <span className="sym" aria-hidden="true">
          <Icon name="map-pin" />
        </span>
        <label>
          Регион
          <select value={values.region} onChange={(e) => apply({ region: e.target.value })}>
            <option value="">Все регионы</option>
            {regions.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="filter">
        <span className="sym" aria-hidden="true">
          <Icon name="waves" />
        </span>
        <label>
          Спот
          <select value={values.spot} onChange={(e) => apply({ spot: e.target.value })}>
            <option value="">Любые споты</option>
            {visibleSpots.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="filter">
        <span className="sym" aria-hidden="true">
          <Icon name="search" />
        </span>
        <label>
          Название или город
          <input
            type="search"
            value={q}
            maxLength={100}
            placeholder="Например, Kamchatka"
            onChange={(e) => setQ(e.target.value)}
            enterKeyHint="search"
          />
        </label>
      </div>
      <div className="gv-school-filter-actions">
        <Button type="submit" variant="primary" icon="search">
          Найти
        </Button>
        {dirty && (
          <Button
            variant="pill"
            icon="refresh"
            onClick={() => {
              setQ("");
              router.replace(routes.schools, { scroll: false });
            }}
          >
            Сбросить
          </Button>
        )}
      </div>
    </form>
  );
}
