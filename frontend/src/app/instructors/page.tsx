/**
 * /instructors — «Каталог сёрф-инструкторов» (PUBLIC_SCREENS §3, INS-01/03/09, NAV-05).
 * Server Component: filters live in the URL, the list is rendered on the server (SEO, shareable links);
 * the client island only rewrites the URL. Pagination is made of real links.
 */
import type { Metadata } from "next";
import { Hero } from "@/components/layout/PageBlocks";
import { InstructorCard } from "@/components/instructors/InstructorCard";
import { InstructorCatalog, type CatalogOption } from "@/components/instructors/InstructorCatalog";
import { CatalogError } from "@/components/instructors/CatalogError";
import { activeCount, filtersToApiQuery, filtersToSearch, PAGE_SIZE, parseFilters } from "@/components/instructors/catalog";
import { ButtonLink, EmptyState, Pagination } from "@/components/ui";
import type { InstructorCard as Card } from "@/lib/api/learning";
import { isApiError } from "@/lib/api/errors";
import { listResults, serverFetch, serverFetchSafe } from "@/lib/api/server";
import type { Paginated } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 120;

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const TITLE = "Каталог сёрф-инструкторов";
const DESCRIPTION =
  "Сёрф-инструкторы России: регионы и споты занятий, уровни учеников, цены, сертификаты и отзывы учеников. Выберите инструктора и запишитесь на свободное окно.";

export async function generateMetadata({ searchParams }: { searchParams: SearchParams }): Promise<Metadata> {
  const { filters, page } = parseFilters(await searchParams);
  // Filtered/paged variants are thin duplicates: canonical stays on /instructors, the variants are noindex.
  const filtered = activeCount(filters) > 0 || page > 1;
  return buildMetadata({ title: TITLE, description: DESCRIPTION, path: routes.instructors, noindex: filtered ? true : undefined });
}

interface RegionRow {
  slug: string;
  name: string;
  spots_count?: number;
}
interface SpotRow {
  slug: string;
  name: string;
  region?: { slug: string; name: string } | null;
}
interface BoardTypeRow {
  code: string;
  name: string;
}

/** Class instances cannot cross the server → client boundary. */
function plainError(error: unknown): { status: number; code: string; message: string } {
  if (isApiError(error)) return { status: error.status, code: error.code, message: error.message };
  return { status: 0, code: "error", message: "Не удалось загрузить список. Попробуйте ещё раз." };
}

export default async function InstructorsPage({ searchParams }: { searchParams: SearchParams }) {
  const { filters, page } = parseFilters(await searchParams);
  const listPromise = serverFetch<Paginated<Card>>("instructors", {
    query: filtersToApiQuery(filters, page),
    revalidate: 120,
    tags: ["instructors"],
  }).then(
    (data) => ({ data, error: null as unknown }),
    (error: unknown) => ({ data: null, error }),
  );
  const [list, regionsData, spotsData, boardTypesData] = await Promise.all([
    listPromise,
    serverFetchSafe<RegionRow[]>("regions", { revalidate: 3600, tags: ["regions"] }),
    serverFetchSafe<Paginated<SpotRow> | SpotRow[]>("spots", { query: { page_size: 100, sort: "name" }, revalidate: 600, tags: ["spots"] }),
    serverFetchSafe<BoardTypeRow[] | Paginated<BoardTypeRow>>("board-types", { revalidate: 3600, tags: ["board-types"] }),
  ]);

  const regions: CatalogOption[] = listResults(regionsData).map((r) => ({ value: r.slug, label: r.name }));
  const spots: CatalogOption[] = listResults(spotsData).map((s) => ({ value: s.slug, label: s.name, group: s.region?.slug }));
  const boardRows = listResults(boardTypesData);
  const boardTypes: CatalogOption[] = boardRows.map((b) => ({ value: b.code, label: b.name }));
  const boardLabels = Object.fromEntries(boardRows.map((b) => [b.code, b.name]));

  const items = list.data?.results ?? [];
  const count = list.data?.count ?? null;
  const hasFilters = activeCount(filters) > 0;

  return (
    <>
      <Hero
        variant="people"
        title={TITLE}
        text="Люди, с которыми начинаются хорошие истории: выбирайте споты, читайте отзывы учеников и договаривайтесь о занятии."
      />
      <div className="wrap gv-ins-page">
        <InstructorCatalog
          key={filtersToSearch(filters, page)}
          filters={filters}
          count={count}
          regions={regions}
          spots={spots}
          boardTypes={boardTypes}
        >
          {list.error ? (
            <CatalogError error={plainError(list.error)} />
          ) : items.length === 0 ? (
            <EmptyState
              illustration
              title="Похоже, все ушли ловить волну!"
              text={
                hasFilters
                  ? "По этим условиям инструкторы пока не нашлись. Волны подождут — попробуйте другой спот или сбросьте фильтры."
                  : "Инструкторы ещё не опубликовали профили. Загляните чуть позже."
              }
              action={hasFilters ? { label: "Сбросить фильтры", href: routes.instructors, icon: "refresh" } : undefined}
            />
          ) : (
            <>
              <ul className="grid grid-3 gv-ins-grid" aria-label="Инструкторы">
                {items.map((i) => (
                  <li key={i.id}>
                    <InstructorCard instructor={i} boardLabels={boardLabels} />
                  </li>
                ))}
              </ul>
              <Pagination
                page={page}
                count={count ?? items.length}
                pageSize={PAGE_SIZE}
                hrefFor={(n) => `${routes.instructors}${filtersToSearch(filters, n)}`}
                ariaLabel="Страницы каталога инструкторов"
              />
            </>
          )}
        </InstructorCatalog>
        <div className="catalog-outro">
          <ButtonLink href={routes.gg} variant="pill" iconRight="arrow">
            Найти компанию для катания через GG Surfer
          </ButtonLink>
        </div>
      </div>
    </>
  );
}
