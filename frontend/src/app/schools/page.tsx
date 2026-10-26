/**
 * Сёрф-школы (SCH-02, NAV-01): SSR catalogue with URL filters (region, spot, q) and crawlable pagination.
 * Data: GET organizations?kind=school (+ regions, spots/map for the filter options).
 */
import type { Metadata } from "next";
import { isApiError } from "@/lib/api/errors";
import type { RegionRef, Paginated } from "@/lib/api/types";
import type { SchoolCard as SchoolCardData } from "@/lib/api/learning";
import { serverFetch, serverFetchSafe } from "@/lib/api/server";
import { buildMetadata } from "@/lib/seo";
import { plural } from "@/lib/format";
import { routes } from "@/lib/routes";
import { Hero, SectionTitle } from "@/components/layout/PageBlocks";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/States";
import { Pagination } from "@/components/ui/Pagination";
import { SchoolCard } from "@/components/schools/SchoolCard";
import { SchoolFilters } from "@/components/schools/SchoolFilters";
import { schoolsHref, type SchoolFilterValues } from "@/components/schools/href";
import { RetryError } from "@/components/schools/RetryError";
import "@/components/schools/schools.css";

export const revalidate = 120;

const PAGE_SIZE = 12;

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v)?.trim() ?? "";

export async function generateMetadata({ searchParams }: { searchParams: SearchParams }): Promise<Metadata> {
  const sp = await searchParams;
  const filtered = Boolean(one(sp.region) || one(sp.spot) || one(sp.q) || Number(one(sp.page)) > 1);
  return buildMetadata({
    title: "Сёрф-школы",
    description: "Сёрф-школы России: программы обучения, ближайшие занятия со свободными местами, команда инструкторов и отзывы учеников.",
    path: routes.schools,
    // filter combinations are thin duplicates of the catalogue (canonical stays /schools)
    noindex: filtered && Boolean(one(sp.q)),
  });
}

interface SpotMarker {
  slug: string;
  name: string;
  region_slug: string;
}

export default async function SchoolsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const values: SchoolFilterValues = { region: one(sp.region), spot: one(sp.spot), q: one(sp.q).slice(0, 100) };
  const page = Math.max(1, Number.parseInt(one(sp.page) || "1", 10) || 1);

  const [regions, map, result] = await Promise.all([
    serverFetchSafe<RegionRef[]>("regions", { revalidate: 3600, tags: ["regions"] }),
    serverFetchSafe<{ count: number; markers: SpotMarker[] }>("spots/map", { revalidate: 600, tags: ["spots"] }),
    serverFetch<Paginated<SchoolCardData>>("organizations", {
      query: { kind: "school", region: values.region, spot: values.spot, q: values.q, page, page_size: PAGE_SIZE },
      revalidate,
      tags: ["organizations", "schools"],
    })
      .then((data) => ({ data, error: null }))
      .catch((error: unknown) => ({ data: null, error })),
  ]);

  const regionOptions = (regions ?? []).map((r) => ({ value: r.slug, label: r.name }));
  const spotOptions = (map?.markers ?? [])
    .map((m) => ({ value: m.slug, label: m.name, region: m.region_slug }))
    .sort((a, b) => a.label.localeCompare(b.label, "ru"));

  const pageMissing = isApiError(result.error) && result.error.isNotFound && page > 1;
  const filtered = Boolean(values.region || values.spot || values.q);
  const count = result.data?.count ?? 0;

  return (
    <>
      <Hero
        variant="people"
        title="Сёрф-школы"
        text="Школы, программы обучения и ближайшие занятия со свободными местами — от первого знакомства с волной до продолжающих групп."
      />
      <div className="wrap">
        <SchoolFilters values={values} regions={regionOptions} spots={spotOptions} />

        {result.error && !pageMissing ? (
          <RetryError
            status={isApiError(result.error) ? result.error.status : 0}
            code={isApiError(result.error) ? result.error.code : "network"}
            message={isApiError(result.error) ? result.error.message : "Нет соединения с сервером. Проверьте интернет и попробуйте ещё раз."}
            title="Не получилось загрузить школы"
          />
        ) : pageMissing ? (
          <EmptyState
            title="Такой страницы нет"
            text="Список школ стал короче — вернитесь к первой странице."
            action={{ label: "К первой странице", href: schoolsHref(values) }}
          />
        ) : count === 0 ? (
          <EmptyState
            title={filtered ? "Похоже, все ушли ловить волну!" : "Школ пока нет"}
            text={
              filtered
                ? "По этим условиям школы не нашлись. Попробуйте другой регион или сбросьте фильтры."
                : "Сёрф-школы появятся здесь после проверки модератором."
            }
            action={filtered ? { label: "Сбросить фильтры", href: routes.schools } : { label: "Найти инструктора", href: routes.instructors }}
          />
        ) : (
          <>
            <SectionTitle>Школы и программы</SectionTitle>
            <p className="gv-schools-count" aria-live="polite">
              Найдено: {count} {plural(count, ["школа", "школы", "школ"])}
            </p>
            <div className="grid grid-3 gv-school-grid">
              {result.data!.results.map((school) => (
                <SchoolCard key={school.id} school={school} />
              ))}
            </div>
            <Pagination
              page={page}
              count={count}
              pageSize={PAGE_SIZE}
              hrefFor={(n) => schoolsHref({ ...values, page: n })}
              ariaLabel="Страницы каталога школ"
            />
          </>
        )}

        <div className="catalog-outro">
          <ButtonLink href={routes.instructors} variant="pill" iconRight="arrow">
            Нужен частный инструктор? Каталог инструкторов
          </ButtonLink>
        </div>
      </div>
    </>
  );
}
