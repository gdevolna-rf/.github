"use client";
/**
 * Spot catalogue filters (SPT-01): region, difficulty, bottom, break, text search and the map/list view.
 * State lives in the URL (shareable, indexable): every change calls router.replace without scrolling; the
 * Server Component re-renders the results. Needs <Suspense> above (useSearchParams).
 */
import { useEffect, useId, useState, useTransition, type FormEvent } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button, Icon, Segmented, Select, type IconName, type SelectOption } from "@/components/ui";

export interface SpotFilterOptions {
  regions: SelectOption[];
  difficulty: SelectOption[];
  bottom: SelectOption[];
  breaks: SelectOption[];
}

const FILTER_PARAMS = ["region", "difficulty", "bottom", "break", "q"] as const;

/** New query string after changing one param: resets the page, drops empty values. */
export function patchQuery(current: string, patch: Record<string, string | null>): string {
  const params = new URLSearchParams(current);
  for (const [key, value] of Object.entries(patch)) {
    if (value === null || value === "") params.delete(key);
    else params.set(key, value);
  }
  if (!("page" in patch)) params.delete("page");
  return params.toString();
}

export function activeFilterCount(search: string): number {
  const params = new URLSearchParams(search);
  return FILTER_PARAMS.filter((k) => params.get(k)).length;
}

export function SpotFilters({ options, total }: { options: SpotFilterOptions; total: number }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const search = params.toString();
  const [pending, startTransition] = useTransition();
  const [q, setQ] = useState(params.get("q") ?? "");
  const searchId = useId();

  useEffect(() => setQ(params.get("q") ?? ""), [params]);

  const go = (patch: Record<string, string | null>) => {
    const qs = patchQuery(search, patch);
    startTransition(() => router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false }));
  };

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    go({ q: q.trim() || null });
  };

  const view = params.get("view") === "list" ? "list" : "map";
  const active = activeFilterCount(search);

  const tile = (icon: IconName, label: string, key: (typeof FILTER_PARAMS)[number], opts: SelectOption[], placeholder: string) => (
    <div className="filter">
      <span className="sym" aria-hidden="true">
        <Icon name={icon} size={20} />
      </span>
      <Select
        label={label}
        appearance="filter"
        placeholder={placeholder}
        options={opts}
        value={params.get(key) ?? ""}
        onChange={(e) => go({ [key]: e.target.value || null })}
      />
    </div>
  );

  return (
    <div className="gv-spot-filters" aria-busy={pending || undefined}>
      <div className="filters">
        {tile("map-pin", "Регион", "region", options.regions, "Все регионы")}
        {tile("level", "Уровень", "difficulty", options.difficulty, "Любой уровень")}
        {tile("waves", "Тип брейка", "break", options.breaks, "Любой брейк")}
        {tile("droplets", "Дно", "bottom", options.bottom, "Любое дно")}
        <Button variant="primary" icon="refresh" onClick={() => go({ region: null, difficulty: null, bottom: null, break: null, q: null })} disabled={!active}>
          Сбросить
        </Button>
      </div>
      <div className="gv-spot-toolbar">
        <form className="gv-spot-search" role="search" onSubmit={onSearch}>
          <label htmlFor={searchId} className="sr-only">
            Поиск спота
          </label>
          <Icon name="search" size={18} />
          <input
            id={searchId}
            type="search"
            className="gv-input"
            placeholder="Название, регион или описание"
            value={q}
            maxLength={100}
            onChange={(e) => setQ(e.target.value)}
          />
          <Button type="submit" variant="pill" size="sm">
            Найти
          </Button>
        </form>
        <Segmented
          ariaLabel="Вид каталога"
          value={view}
          onChange={(v) => go({ view: v === "list" ? "list" : null })}
          options={[
            { value: "map", label: "Карта и список", icon: "map" },
            { value: "list", label: "Только список", icon: "grid" },
          ]}
        />
        <p className="gv-spot-count" role="status" aria-live="polite">
          {pending ? "Обновляем…" : `Найдено: ${total}`}
        </p>
      </div>
    </div>
  );
}
