/**
 * Карта сёрф-спотов (PUBLIC_SCREENS §4.1, SPT-01): Server Component (SSR for SEO) with client islands —
 * filters in the URL, clustered Leaflet map with a card on marker click, side list and the card grid with
 * page links. No «Открыть спутник» (SPT-09).
 */
import type { Metadata } from "next";
import { Suspense } from "react";
import { Hero, PageHead, SectionTitle, WideBanner } from "@/components/layout/PageBlocks";
import { RetryError } from "@/components/spots/RetryError";
import { SpotCard } from "@/components/spots/SpotCard";
import { SpotFilters, type SpotFilterOptions } from "@/components/spots/SpotFilters";
import { SpotMapIsland } from "@/components/spots/SpotMapIsland";
import { ButtonLink, EmptyState, Pagination } from "@/components/ui";
import { errorMessage } from "@/lib/api/errors";
import { serverFetch, serverFetchAll, serverFetchSafe } from "@/lib/api/server";
import type { MapResponse, Region, SpotCard as SpotCardData, SpotDictionaries } from "@/lib/api/spots";
import type { Paginated } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";
import "@/components/spots/spots.css";

export const revalidate = 300;

const PAGE_SIZE = 12;

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";

export async function generateMetadata(): Promise<Metadata> {
  // Filtered and paged variants share the canonical catalogue URL.
  return buildMetadata({
    title: "Карта сёрф-спотов",
    description:
      "Сёрф-споты России на карте: Камчатка, Сахалин, Крым, Приморье, Ладога. Ветер и свелл, дно, сезон, опасности, инфраструктура и отзывы.",
    path: routes.spots,
  });
}

function pick(value: string, allowed: Set<string>): string | undefined {
  return value && allowed.has(value) ? value : undefined;
}

export default async function SpotsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const [regionsData, dicts] = await Promise.all([
    serverFetchSafe<Region[]>("regions", { tags: ["regions"], revalidate: 3600 }),
    serverFetchSafe<SpotDictionaries>("spots/dictionaries", { tags: ["spots"], revalidate: 3600 }),
  ]);
  const regions = regionsData ?? [];
  const codes = (list?: Array<{ code: string }>) => new Set((list ?? []).map((c) => c.code));

  // Unknown values would make the API answer 400 — drop them instead.
  const filters = {
    region: pick(one(sp.region), new Set(regions.map((r) => r.slug))),
    difficulty: pick(one(sp.difficulty), codes(dicts?.difficulty)),
    bottom: pick(one(sp.bottom), codes(dicts?.bottom_type)),
    break: pick(one(sp.break), codes(dicts?.break_type)),
    q: one(sp.q).trim().slice(0, 100) || undefined,
  };
  const page = Math.max(1, Number.parseInt(one(sp.page), 10) || 1);
  const view = one(sp.view) === "list" ? "list" : "map";
  const nonRegionFilter = Boolean(filters.difficulty || filters.bottom || filters.break || filters.q);
  const anyFilter = nonRegionFilter || Boolean(filters.region);

  let list: Paginated<SpotCardData> | null = null;
  let listError: string | null = null;
  try {
    list = await serverFetch<Paginated<SpotCardData>>("spots", {
      query: { ...filters, page, page_size: PAGE_SIZE },
      tags: ["spots"],
      revalidate: 120,
    });
  } catch (err) {
    // page beyond the end → first page
    if ((err as { status?: number })?.status === 404 && page > 1) {
      list = await serverFetchSafe<Paginated<SpotCardData>>("spots", { query: { ...filters, page_size: PAGE_SIZE }, tags: ["spots"], revalidate: 120 });
    } else listError = errorMessage(err);
  }

  let markers: MapResponse["markers"] = [];
  let mapError = false;
  if (view === "map") {
    const map = await serverFetchSafe<MapResponse>("spots/map", { query: { region: filters.region }, tags: ["spots"], revalidate: 120 });
    if (!map) mapError = true;
    markers = map?.markers ?? [];
    if (nonRegionFilter && markers.length) {
      // the map endpoint filters by region only — intersect with the filtered catalogue
      const all = await serverFetchAll<SpotCardData>("spots", { query: filters, tags: ["spots"], revalidate: 120, maxPages: 5 }).catch(() => null);
      if (all) {
        const ids = new Set(all.map((s) => s.id));
        markers = markers.filter((m) => ids.has(m.id));
      }
    }
  }

  const options: SpotFilterOptions = {
    regions: regions.map((r) => ({ value: r.slug, label: r.spots_count ? `${r.name} (${r.spots_count})` : r.name })),
    difficulty: (dicts?.difficulty ?? []).map((c) => ({ value: c.code, label: c.label })),
    bottom: (dicts?.bottom_type ?? []).map((c) => ({ value: c.code, label: c.label })),
    breaks: (dicts?.break_type ?? []).map((c) => ({ value: c.code, label: c.label })),
  };

  const hrefFor = (n: number) => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(sp)) {
      const value = one(v);
      if (value && k !== "page") p.set(k, value);
    }
    if (n > 1) p.set("page", String(n));
    const qs = p.toString();
    return qs ? `${routes.spots}?${qs}` : routes.spots;
  };

  const spots = list?.results ?? [];

  return (
    <>
      <Hero
        variant="people"
        title="Карта сёрф-спотов"
        text="Открывайте новые места, изучайте особенности берега и выбирайте, где ловить свою волну."
      />
      <div className="wrap gv-spots-page">
        <PageHead
          title="Где сегодня искать свою волну?"
          text="Интерактивная карта, типичный ветер и свелл, дно, сезон, опасности, инфраструктура и отзывы сёрферов."
        />
        <Suspense fallback={null}>
          <SpotFilters options={options} total={list?.count ?? 0} />
        </Suspense>

        {view === "map" &&
          (mapError ? (
            <RetryError compact title="Карта не загрузилась" message="Сервис временно недоступен. Список спотов ниже работает." />
          ) : (
            <SpotMapIsland markers={markers} filtered={anyFilter} />
          ))}

        <section className="section gv-spots-cards" aria-labelledby="spots-cards-title">
          <SectionTitle id="spots-cards-title">Карточки спотов</SectionTitle>
          {listError ? (
            <RetryError message={listError} />
          ) : spots.length === 0 ? (
            <EmptyState
              title={anyFilter ? "Похоже, все ушли ловить волну!" : "Споты скоро появятся"}
              text={
                anyFilter
                  ? "По этим условиям споты не нашлись. Попробуйте другой регион или сбросьте фильтры."
                  : "Мы проверяем данные о местах для сёрфинга — загляните чуть позже."
              }
              action={anyFilter ? { label: "Сбросить фильтры", href: routes.spots, icon: "refresh" } : undefined}
            />
          ) : (
            <>
              <div className="grid grid-3 gv-spot-grid">
                {spots.map((spot) => (
                  <SpotCard key={spot.id} spot={spot} />
                ))}
              </div>
              <Pagination page={page} count={list?.count ?? 0} pageSize={PAGE_SIZE} hrefFor={hrefFor} ariaLabel="Страницы каталога спотов" />
            </>
          )}
        </section>

        <div className="gv-spots-help notice">
          Знаете спот лучше нас? Откройте карточку и нажмите карандаш на фото — предложение проверит модератор.{" "}
          <ButtonLink href={routes.account.proposals} variant="link" iconRight="arrow">
            Мои предложения
          </ButtonLink>
        </div>
        <WideBanner cta={{ href: routes.gg, label: "Найти компанию для катания" }} />
      </div>
    </>
  );
}
