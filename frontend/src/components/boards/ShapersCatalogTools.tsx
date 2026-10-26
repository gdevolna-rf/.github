"use client";
/**
 * Tools card of the public shapers catalogue (SHP-07, NAV-02, ATX-02): tabs «Все доски» / «По шейперам» as links
 * (`?tab=`), search, type (incl. Fish/Gun and workshop types), region, and for boards — shaper, length, volume,
 * price, availability, material, repair, sort. No «Я смотрю как» role switch: the role comes from the account.
 */
import Link from "next/link";
import { useId, useState } from "react";
import { Button, Icon, type SelectOption } from "@/components/ui";
import type { BoardMaterial, BoardsRegion, BoardType, CatalogTab } from "@/lib/api/boards";
import { formatFeetInches, formatMoney } from "@/lib/format";
import { STATUS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { cx } from "@/lib/cx";
import { useCatalogNav } from "./CatalogNav";
import { ParamCheckbox, ParamSelect, SearchParamInput, useActiveFilterCount } from "./FilterControls";

export interface ShapersCatalogOptions {
  types: BoardType[];
  materials: BoardMaterial[];
  regions: BoardsRegion[];
  shapers: Array<{ slug: string; name: string }>;
}

const LENGTHS = [60, 66, 72, 78, 84, 90, 96, 108, 120, 132];
const PRICES = [30000, 50000, 70000, 90000, 120000, 150000];

const BOARD_EXTRA_KEYS = ["shaper", "length_min", "length_max", "volume_min", "volume_max", "price_max", "availability", "material", "repair", "ordering"] as const;
const SHAPER_EXTRA_KEYS = ["repair", "ordering"] as const;
const SHARED_KEYS = ["q", "type", "region", "repair"] as const;

export function typeOptions(types: BoardType[]): SelectOption[] {
  const seen = new Set<string>();
  const out: SelectOption[] = [];
  for (const t of types) {
    if (seen.has(t.code)) continue;
    seen.add(t.code);
    out.push({ value: t.code, label: t.name });
  }
  return out;
}

export function materialOptions(materials: BoardMaterial[]): SelectOption[] {
  const seen = new Set<string>();
  const out: SelectOption[] = [];
  for (const m of materials) {
    const key = m.name.trim().toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push({ value: m.name, label: m.name });
  }
  return out;
}

export function ShapersCatalogTools({ tab, options }: { tab: CatalogTab; options: ShapersCatalogOptions }) {
  const nav = useCatalogNav();
  const extraKeys = tab === "boards" ? BOARD_EXTRA_KEYS : SHAPER_EXTRA_KEYS;
  const extraCount = useActiveFilterCount(extraKeys);
  const totalCount = useActiveFilterCount([...SHARED_KEYS, ...extraKeys]);
  const [open, setOpen] = useState(extraCount > 0);
  const extraId = useId();

  const tabHref = (next: CatalogTab) => {
    const p = new URLSearchParams();
    for (const k of SHARED_KEYS) {
      const v = nav.params.get(k);
      if (v) p.set(k, v);
    }
    p.set("tab", next);
    return `${routes.shapers}?${p.toString()}`;
  };

  const regionOptions = options.regions.map((r) => ({ value: r.slug, label: r.name }));
  const lengthOptions = LENGTHS.map((l) => ({ value: String(l), label: formatFeetInches(l) }));

  return (
    <section className="card catalog-tools gv-catalog-tools" aria-label="Поиск и фильтры каталога">
      <nav className="catalog-switch" aria-label="Вид каталога">
        <Link href={tabHref("boards")} className={cx("tab", tab === "boards" && "active")} aria-current={tab === "boards" ? "page" : undefined} scroll={false}>
          Все доски
        </Link>
        <Link href={tabHref("shapers")} className={cx("tab", tab === "shapers" && "active")} aria-current={tab === "shapers" ? "page" : undefined} scroll={false}>
          По шейперам
        </Link>
      </nav>

      <div className="catalog-filters">
        <SearchParamInput label="Поиск" placeholder={tab === "boards" ? "Модель, тип, мастерская, артикул…" : "Мастерская, мастер, город…"} />
        <ParamSelect name="type" label="Тип доски" placeholder="Все типы" options={typeOptions(options.types)} />
        <ParamSelect name="region" label="Регион" placeholder="Все регионы" options={regionOptions} />
      </div>

      <div className="gv-catalog-more">
        <button type="button" className="plain gv-catalog-more-toggle" aria-expanded={open} aria-controls={extraId} onClick={() => setOpen((v) => !v)}>
          <Icon name="filter" size={16} />
          {open ? "Скрыть фильтры" : "Ещё фильтры"}
          {extraCount > 0 && <span className="gv-filter-count">{extraCount}</span>}
          <Icon name={open ? "chevron-up" : "chevron-down"} size={15} />
        </button>
        {totalCount > 0 && (
          <Button variant="link" size="sm" icon="refresh" onClick={() => nav.reset(["tab"])}>
            Сбросить фильтры
          </Button>
        )}
      </div>

      <div id={extraId} hidden={!open} className="catalog-filters gv-catalog-extra">
        {tab === "boards" ? (
          <>
            <ParamSelect name="shaper" label="Шейпер" placeholder="Все мастерские" options={options.shapers.map((s) => ({ value: s.slug, label: s.name }))} />
            <ParamSelect name="availability" label="Наличие" placeholder="Любое" options={Object.entries(STATUS.availability).map(([value, def]) => ({ value, label: def.label }))} />
            <ParamSelect name="material" label="Материал" placeholder="Любой материал" options={materialOptions(options.materials)} />
            <ParamSelect name="length_min" label="Длина от" placeholder="Любая" options={lengthOptions} />
            <ParamSelect name="length_max" label="Длина до" placeholder="Любая" options={lengthOptions} />
            <ParamSelect name="price_max" label="Цена до" placeholder="Любая цена" options={PRICES.map((p) => ({ value: String(p), label: formatMoney(p) }))} />
            <SearchParamInput name="volume_min" label="Объём от, л" type="number" inputMode="decimal" min={1} max={300} placeholder="Например, 30" />
            <SearchParamInput name="volume_max" label="Объём до, л" type="number" inputMode="decimal" min={1} max={300} placeholder="Например, 60" />
            <ParamSelect
              name="ordering"
              label="Сортировка"
              placeholder="Сначала новые"
              options={[
                { value: "price", label: "Сначала дешевле" },
                { value: "-price", label: "Сначала дороже" },
                { value: "name", label: "По названию" },
              ]}
            />
            <ParamCheckbox name="repair" label="Мастерская делает ремонт" className="gv-catalog-check" />
          </>
        ) : (
          <>
            <ParamSelect
              name="ordering"
              label="Сортировка"
              placeholder="По рейтингу"
              options={[
                { value: "models", label: "Больше моделей" },
                { value: "new", label: "Новые мастерские" },
                { value: "name", label: "По названию" },
              ]}
            />
            <ParamCheckbox name="repair" label="Делает ремонт досок" className="gv-catalog-check" />
          </>
        )}
      </div>
    </section>
  );
}
