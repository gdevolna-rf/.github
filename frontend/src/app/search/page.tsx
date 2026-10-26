/**
 * Глобальный поиск (NAV-04, ARCHITECTURE §9 `/search?q=`): споты, инструкторы, школы, шейперы, доски,
 * оборудование и участники GG Surfer, сгруппированно, с «Показать ещё» в каталог раздела.
 * Server Component (results are rendered on the server; the header search dialog navigates here).
 * Search result pages are not indexed (noindex), the canonical URL is /search.
 */
import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { Hero } from "@/components/layout/PageBlocks";
import { SearchForm } from "@/components/search/SearchForm";
import { SearchResults } from "@/components/search/SearchResults";
import { SearchRetry } from "@/components/search/SearchRetry";
import { SearchTypeFilter } from "@/components/search/SearchTypeFilter";
import {
  normalizeQuery,
  parseType,
  queryState,
  searchHref,
  totalResults,
  typeChips,
  visibleGroups,
} from "@/components/search/searchModel";
import "@/components/search/search.css";
import { EmptyState } from "@/components/ui/States";
import { Icon } from "@/components/ui/Icon";
import { isApiError } from "@/lib/api/errors";
import { SEARCH_LIMIT_ALL, SEARCH_LIMIT_ONE, SEARCH_MIN_QUERY, SEARCH_TYPES, type SearchResponse } from "@/lib/api/search";
import { serverFetch } from "@/lib/api/server";
import { plural, WORDS } from "@/lib/format";
import { MAIN_NAV, routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export async function generateMetadata({ searchParams }: { searchParams: SearchParams }): Promise<Metadata> {
  const q = normalizeQuery((await searchParams).q);
  return buildMetadata({
    title: q ? `Поиск: ${q}` : "Поиск",
    description: "Поиск по спотам, инструкторам, сёрф-школам, шейперам, доскам, снаряжению и участникам GG Surfer.",
    path: "/search",
    noindex: true,
  });
}

interface Loaded {
  all: SearchResponse | null;
  one: SearchResponse | null;
  error: { status: number; code: string; message: string; requestId: string | null } | null;
}

async function load(q: string, type: string | null): Promise<Loaded> {
  try {
    const [all, one] = await Promise.all([
      serverFetch<SearchResponse>("search", { query: { q, limit: SEARCH_LIMIT_ALL }, revalidate: 60, tags: ["search"] }),
      type
        ? serverFetch<SearchResponse>("search", {
            query: { q, types: type, limit: SEARCH_LIMIT_ONE },
            revalidate: 60,
            tags: ["search"],
          })
        : Promise.resolve(null),
    ]);
    return { all, one, error: null };
  } catch (err) {
    const e = isApiError(err) ? err : null;
    return {
      all: null,
      one: null,
      error: {
        status: e?.status ?? 0,
        code: e?.code ?? "network",
        message: e?.message ?? "Не удалось выполнить поиск. Попробуйте ещё раз.",
        requestId: e?.requestId ?? null,
      },
    };
  }
}

function SectionLinks() {
  return (
    <div className="chips gv-search-sections gv-sr-sections">
      {MAIN_NAV.map((item) => (
        <Link key={item.href} href={item.href} className="chip">
          <Icon name={item.icon} size={14} />
          {item.short}
        </Link>
      ))}
    </div>
  );
}

export default async function SearchPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const q = normalizeQuery(params.q);
  const type = parseType(params.types);
  const state = queryState(q);
  const typeLabel = type ? SEARCH_TYPES.find((t) => t.type === type)?.label : null;

  let body: ReactNode;
  if (state === "empty") {
    body = (
      <div className="gv-sr-hint">
        <p>
          <b>Начните вводить название, имя или регион</b> — например, «Камчатка», «Алексей» или «лонгборд».
        </p>
        <p className="muted">Или откройте раздел:</p>
        <SectionLinks />
      </div>
    );
  } else if (state === "short") {
    body = (
      <div className="gv-sr-hint" role="status">
        <p>
          <b>Введите не меньше {SEARCH_MIN_QUERY} символов</b>, чтобы мы нашли споты, людей и снаряжение.
        </p>
      </div>
    );
  } else {
    const { all, one, error } = await load(q, type);
    if (error) {
      body = <SearchRetry status={error.status} code={error.code} message={error.message} requestId={error.requestId} />;
    } else {
      const total = totalResults(all);
      const groups = visibleGroups(all, one, type);
      const chips = typeChips(all, q, type);
      body = (
        <>
          <p className="gv-sr-summary" role="status">
            {total > 0 ? (
              <>
                По запросу <b>«{q}»</b> найдено {total} {plural(total, WORDS.result)}
                {typeLabel ? (
                  <>
                    {" "}
                    · показан раздел «{typeLabel}»
                  </>
                ) : null}
              </>
            ) : (
              <>
                По запросу <b>«{q}»</b> ничего не нашлось
              </>
            )}
          </p>
          {total > 0 && <SearchTypeFilter chips={chips} />}
          {total === 0 ? (
            <EmptyState
              title="Похоже, все ушли ловить волну!"
              text={
                <>
                  По запросу «{q}» ничего не нашлось. Проверьте написание, попробуйте название региона, спота или имя —
                  или загляните в разделы.
                </>
              }
            />
          ) : groups.length === 0 ? (
            <EmptyState
              compact
              title={`В разделе «${typeLabel ?? "выбранном"}» ничего не нашлось`}
              text="Зато есть результаты в других разделах."
              action={{ label: "Все результаты", href: searchHref(q), icon: "arrow" }}
            />
          ) : (
            <SearchResults groups={groups} single={Boolean(type)} />
          )}
          {total === 0 && <SectionLinks />}
        </>
      );
    }
  }

  return (
    <>
      <Hero
        variant="people"
        title="Поиск по Гдеволне"
        text="Споты, инструкторы, школы, шейперы, доски, снаряжение и свои люди в GG Surfer — в одном месте."
      />
      <div className="wrap gv-sr-page">
        <section className="section" aria-label="Результаты поиска">
          <SearchForm q={q} type={type} autoFocus={state === "empty"} />
          {body}
          <p className="gv-sr-assistant">
            <Icon name="sparkle" size={16} /> Не знаете, что искать?{" "}
            <Link href={routes.assistant}>Помощник подбора</Link> подскажет спот, инструктора и размер доски.
          </p>
        </section>
      </div>
    </>
  );
}
