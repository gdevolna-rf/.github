"use client";
/**
 * Client island of /instructors (INS-09): filter tiles (prototype `.filters/.filter`), «Ещё фильтры» row, result
 * count + sorting (`.listing-top`). Every change is written to the URL (router.replace) so the server page re-renders
 * the cards — links are shareable and crawlable. Text inputs commit on Enter/blur, selects immediately.
 */
import { useEffect, useId, useState, useTransition, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Button, Icon, type IconName } from "@/components/ui";
import { LESSON_FORMAT_LABELS, STUDENT_LEVEL_LABELS } from "@/lib/api/learning";
import { cx } from "@/lib/cx";
import { plural, WORDS } from "@/lib/format";
import {
  activeCount,
  CERTIFICATE_OPTIONS,
  EXTRA_KEYS,
  filtersToSearch,
  ORDERING_OPTIONS,
  RATING_OPTIONS,
  withFilter,
  type FilterKey,
  type InstructorFilters,
} from "./catalog";
import "./instructors.css";

export interface CatalogOption {
  value: string;
  label: string;
  group?: string;
}

export interface InstructorCatalogProps {
  filters: InstructorFilters;
  count: number | null;
  regions: CatalogOption[];
  /** spot options; `group` = region slug (narrowed by the chosen region) */
  spots: CatalogOption[];
  boardTypes: CatalogOption[];
  children: ReactNode;
}

const LEVEL_OPTIONS = Object.entries(STUDENT_LEVEL_LABELS).map(([value, label]) => ({ value, label }));
const FORMAT_OPTIONS = Object.entries(LESSON_FORMAT_LABELS).map(([value, label]) => ({ value, label }));

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function InstructorCatalog({ filters, count, regions, spots, boardTypes, children }: InstructorCatalogProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [pending, startTransition] = useTransition();
  const extraActive = activeCount(filters, EXTRA_KEYS);
  const [extraOpen, setExtraOpen] = useState(extraActive > 0);
  const extraId = useId().replace(/:/g, "");
  // «today» differs between the server (UTC) and the browser — set the date minimum after hydration
  const [minDate, setMinDate] = useState<string | undefined>(undefined);
  useEffect(() => setMinDate(todayIso()), []);

  const go = (next: InstructorFilters) => {
    startTransition(() => router.replace(`${pathname}${filtersToSearch(next)}`, { scroll: false }));
  };
  const set = (key: FilterKey, value: string | undefined) => {
    let next = withFilter(filters, key, value);
    // a spot from another region would give an empty list — drop it when the region changes
    if (key === "region" && next.spot) {
      const spot = spots.find((s) => s.value === next.spot);
      if (value && spot?.group && spot.group !== value) next = withFilter(next, "spot", undefined);
    }
    go(next);
  };
  const reset = () => go(filters.ordering ? { ordering: filters.ordering } : {});

  const spotOptions = filters.region ? spots.filter((s) => !s.group || s.group === filters.region) : spots;
  const total = activeCount(filters);

  return (
    <>
      <div className="filters gv-ins-filters" role="group" aria-label="Фильтры инструкторов">
        <SelectTile icon="map-pin" label="Регион" placeholder="Все регионы" value={filters.region} options={regions} onChange={(v) => set("region", v)} />
        <SelectTile icon="waves" label="Споты" placeholder="Любые споты" value={filters.spot} options={spotOptions} onChange={(v) => set("spot", v)} />
        <SelectTile icon="board" label="Тип доски" placeholder="Любая доска" value={filters.board_type} options={boardTypes} onChange={(v) => set("board_type", v)} />
        <SelectTile icon="level" label="Уровень учеников" placeholder="Любой уровень" value={filters.level} options={LEVEL_OPTIONS} onChange={(v) => set("level", v)} />
        <Button variant="primary" icon="refresh" onClick={reset} disabled={!total} aria-label="Сбросить все фильтры">
          Сбросить
        </Button>
      </div>

      <div className="gv-ins-extra-toggle">
        <button
          type="button"
          className="pill-btn"
          aria-expanded={extraOpen}
          aria-controls={extraId}
          onClick={() => setExtraOpen((o) => !o)}
        >
          <Icon name="filter" size={15} />
          <span>{extraOpen ? "Скрыть фильтры" : "Ещё фильтры"}</span>
          {extraActive > 0 && <span className="gv-ins-badge" aria-label={`выбрано: ${extraActive}`}>{extraActive}</span>}
          <Icon name={extraOpen ? "chevron-up" : "chevron-down"} size={15} />
        </button>
      </div>

      <div id={extraId} className="filters gv-ins-extra" hidden={!extraOpen}>
        <SelectTile icon="users" label="Формат" placeholder="Любой формат" value={filters.format} options={FORMAT_OPTIONS} onChange={(v) => set("format", v)} />
        <InputTile
          icon="ruler"
          label="Цена до, ₽"
          type="number"
          inputMode="numeric"
          min={0}
          step={100}
          placeholder="Любая"
          value={filters.price_max}
          onCommit={(v) => set("price_max", v)}
        />
        <SelectTile icon="shield" label="Сертификат" placeholder="Неважно" value={filters.certificate} options={CERTIFICATE_OPTIONS} onChange={(v) => set("certificate", v)} />
        <InputTile icon="calendar" label="Свободное окно" type="date" min={minDate} value={filters.date} onCommit={(v) => set("date", v)} commitOnChange />
        <SelectTile icon="star" label="Отзывы" placeholder="Любой рейтинг" value={filters.rating_min} options={RATING_OPTIONS} onChange={(v) => set("rating_min", v)} />
        <InputTile icon="search" label="Имя или ключевое слово" type="search" placeholder="Например, лонгборд" value={filters.q} onCommit={(v) => set("q", v)} />
      </div>

      <div className="listing-top">
        <div>
          <span className="catalog-meta" role="status" aria-live="polite">
            {pending
              ? "Обновляем список…"
              : count === null
                ? ""
                : `Найдено: ${count} ${plural(count, WORDS.instructor)}`}
          </span>
          <span className="catalog-help">
            <Icon name="clover" size={14} /> Новичкам советуем выбирать по уровню учеников, отзывам и свободным окнам.
          </span>
        </div>
        <label className="sorting">
          Сортировать
          <select value={filters.ordering ?? ""} onChange={(e) => set("ordering", e.target.value)}>
            {ORDERING_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={cx("gv-ins-results", pending && "is-pending")} aria-busy={pending || undefined}>
        {children}
      </div>
    </>
  );
}

function SelectTile({
  icon,
  label,
  placeholder,
  value,
  options,
  onChange,
}: {
  icon: IconName;
  label: string;
  placeholder: string;
  value: string | undefined;
  options: CatalogOption[];
  onChange: (value: string) => void;
}) {
  const known = !value || options.some((o) => o.value === value);
  return (
    <div className="filter">
      <span className="sym" aria-hidden="true">
        <Icon name={icon} size={22} />
      </span>
      <label>
        {label}
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
          <option value="">{placeholder}</option>
          {!known && <option value={value}>{value}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function InputTile({
  icon,
  label,
  value,
  onCommit,
  commitOnChange,
  ...input
}: {
  icon: IconName;
  label: string;
  value: string | undefined;
  onCommit: (value: string) => void;
  commitOnChange?: boolean;
  type: string;
  placeholder?: string;
  min?: number | string;
  step?: number;
  inputMode?: "numeric" | "search" | "text";
}) {
  const [draft, setDraft] = useState(value ?? "");
  const commit = (v: string) => {
    if (v.trim() !== (value ?? "")) onCommit(v.trim());
  };
  return (
    <div className="filter">
      <span className="sym" aria-hidden="true">
        <Icon name={icon} size={22} />
      </span>
      <label>
        {label}
        <input
          className="gv-ins-filter-input"
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            if (commitOnChange) commit(e.target.value);
          }}
          onBlur={(e) => commit(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit((e.target as HTMLInputElement).value);
            }
          }}
          {...input}
        />
      </label>
    </div>
  );
}
