/**
 * Public shapers catalogue (SHP-07/08/09, NAV-02, ATX-02): open to everyone, never asks to «зарегистрироваться
 * шейпером». Server Component (SSR + ISR for SEO); filters live in the URL (`?tab=boards|shapers&type=fish…`) and are
 * changed by the client island without losing the rendered list. Profiles open as a modal (see layout.tsx).
 */
import type { Metadata } from "next";
import { Suspense } from "react";
import { Hero } from "@/components/layout/PageBlocks";
import { BoardCard } from "@/components/boards/BoardCard";
import { CatalogNavProvider, CatalogPending } from "@/components/boards/CatalogNav";
import { RefreshError, serializeError } from "@/components/boards/RefreshError";
import { ShaperCard } from "@/components/boards/ShaperCard";
import { ShapersCatalogTools, type ShapersCatalogOptions } from "@/components/boards/ShapersCatalogTools";
import "@/components/boards/boards.css";
import { EmptyState, Pagination } from "@/components/ui";
import {
  boardsQuery,
  CATALOG_PAGE_SIZE,
  catalogTab,
  pageParam,
  shapersQuery,
  type BoardCard as BoardCardData,
  type BoardMaterial,
  type BoardsRegion,
  type BoardType,
  type SearchParamsRecord,
  type ShaperCard as ShaperCardData,
} from "@/lib/api/boards";
import { isApiError } from "@/lib/api/errors";
import { listResults, serverFetch, serverFetchSafe } from "@/lib/api/server";
import type { Paginated } from "@/lib/api/types";
import { pluralize } from "@/lib/format";
import { routes } from "@/lib/routes";
import { absoluteUrl, buildMetadata, jsonLd } from "@/lib/seo";

export const revalidate = 300;

type Props = { searchParams: Promise<SearchParamsRecord> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const tab = catalogTab(await searchParams);
  const meta = buildMetadata({
    title: tab === "shapers" ? "Шейперы и мастерские" : "Каталог досок от шейперов",
    description:
      tab === "shapers"
        ? "Мастерские шейперов России: специализация, сроки изготовления, ремонт досок и модели прямо в карточке мастера."
        : "Все доски ручной работы: шортборды, фиши, ганы, лонгборды и SUP от российских шейперов — размеры, объём, цена и наличие.",
    path: routes.shapers,
  });
  return tab === "shapers" ? { ...meta, alternates: { canonical: `${routes.shapers}?tab=shapers` } } : meta;
}

type ListResult<T> = { ok: true; data: Paginated<T> } | { ok: false; error: unknown };

async function load<T>(path: string, query: Record<string, string | number>): Promise<ListResult<T>> {
  try {
    const data = await serverFetch<Paginated<T> | T[]>(path, { query, revalidate: 120, tags: ["boards"] });
    return { ok: true, data: Array.isArray(data) ? { count: data.length, next: null, previous: null, results: data } : data };
  } catch (error) {
    return { ok: false, error };
  }
}

function hrefForPage(params: SearchParamsRecord, page: number): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    const value = Array.isArray(v) ? v[0] : v;
    if (value && k !== "page") p.set(k, value);
  }
  if (page > 1) p.set("page", String(page));
  const qs = p.toString();
  return qs ? `${routes.shapers}?${qs}` : routes.shapers;
}

export default async function ShapersCatalogPage({ searchParams }: Props) {
  const params = await searchParams;
  const tab = catalogTab(params);
  const page = pageParam(params);

  const [list, types, materials, regions, shaperOptions] = await Promise.all([
    tab === "boards"
      ? load<BoardCardData>("boards", boardsQuery(params) as Record<string, string | number>)
      : load<ShaperCardData>("shapers", shapersQuery(params) as Record<string, string | number>),
    serverFetchSafe<BoardType[]>("board-types", { revalidate: 3600, tags: ["boards"] }),
    serverFetchSafe<BoardMaterial[]>("board-materials", { revalidate: 3600, tags: ["boards"] }),
    serverFetchSafe<BoardsRegion[] | Paginated<BoardsRegion>>("regions", { revalidate: 3600, tags: ["regions"] }),
    tab === "boards" ? serverFetchSafe<Paginated<ShaperCardData>>("shapers", { query: { page_size: 100, ordering: "name" }, revalidate: 600, tags: ["boards"] }) : null,
  ]);

  const options: ShapersCatalogOptions = {
    types: types ?? [],
    materials: materials ?? [],
    regions: listResults(regions),
    shapers: listResults(shaperOptions).map((s) => ({ slug: s.slug, name: s.name })),
  };

  const heading = tab === "boards" ? "Все доски" : "Шейперы и их мастерские";
  const pageSize = tab === "boards" ? CATALOG_PAGE_SIZE : 12;

  return (
    <>
      <Hero variant="people" kicker="Мастерские · доски · Россия" title="Каталог шейперов" text="Найдите доску под свою волну — у мастеров со всей России." />
      <div className="wrap">
        <div className="gv-shapers gv-shapers-catalog">
          <CatalogNavProvider>
            <Suspense fallback={null}>
              <ShapersCatalogTools tab={tab} options={options} />
            </Suspense>
            <section className="gv-catalog-section" aria-labelledby="catalog-heading">
              <div className="section-head">
                <h2 id="catalog-heading" className="gv-catalog-heading">
                  {heading}
                </h2>
                {list.ok && (
                  <span className="muted" aria-live="polite">
                    Найдено{" "}
                    {tab === "boards"
                      ? pluralize(list.data.count, ["модель", "модели", "моделей"])
                      : pluralize(list.data.count, ["мастерская", "мастерские", "мастерских"])}
                  </span>
                )}
              </div>
              <CatalogPending>
                {!list.ok ? (
                  isApiError(list.error) && list.error.isValidation ? (
                    <EmptyState
                      title="Фильтр не подошёл"
                      text={`${list.error.message} Проверьте значения или сбросьте фильтры.`}
                      action={{ label: "Сбросить фильтры", href: `${routes.shapers}?tab=${tab}` }}
                    />
                  ) : (
                    <RefreshError error={serializeError(list.error)} title={tab === "boards" ? "Не удалось загрузить доски" : "Не удалось загрузить мастерские"} />
                  )
                ) : list.data.results.length === 0 ? (
                  <EmptyState
                    title={tab === "boards" ? "Досок пока не нашлось" : "Мастерские не найдены"}
                    text={page > 1 ? "На этой странице пусто — вернитесь к первой." : "Попробуйте другие фильтры или посмотрите все модели."}
                    action={{ label: "Сбросить фильтры", href: `${routes.shapers}?tab=${tab}` }}
                  />
                ) : tab === "boards" ? (
                  <ul className="models catalog-models gv-plain-list">
                    {(list.data.results as BoardCardData[]).map((b) => (
                      <li key={b.id}>
                        <BoardCard board={b} />
                      </li>
                    ))}
                  </ul>
                ) : (
                  <ul className="maker-list gv-plain-list">
                    {(list.data.results as ShaperCardData[]).map((s) => (
                      <li key={s.id}>
                        <ShaperCard shaper={s} />
                      </li>
                    ))}
                  </ul>
                )}
                {list.ok && list.data.count > pageSize && (
                  <Pagination page={page} count={list.data.count} pageSize={pageSize} hrefFor={(n) => hrefForPage(params, n)} ariaLabel="Страницы каталога" />
                )}
              </CatalogPending>
            </section>
          </CatalogNavProvider>
          {list.ok && list.data.results.length > 0 && (
            <script
              type="application/ld+json"
              dangerouslySetInnerHTML={jsonLd({
                "@context": "https://schema.org",
                "@type": "ItemList",
                name: heading,
                itemListElement: list.data.results.map((item, i) => ({
                  "@type": "ListItem",
                  position: (page - 1) * pageSize + i + 1,
                  url: absoluteUrl(tab === "boards" ? routes.board((item as BoardCardData).id) : routes.shaper((item as ShaperCardData).slug)),
                  name: (item as { name: string }).name,
                })),
              })}
            />
          )}
        </div>
      </div>
    </>
  );
}
