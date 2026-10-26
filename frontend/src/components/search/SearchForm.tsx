/**
 * Search box of /search (NAV-04): a GET form (next/form — client navigation with JS, plain GET without it).
 * The selected type filter is kept as a hidden field so a new query stays in the same section.
 */
import Form from "next/form";
import type { SearchType } from "@/lib/api/search";
import { SEARCH_MAX_QUERY } from "@/lib/api/search";
import { routes } from "@/lib/routes";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";

export function SearchForm({ q, type, autoFocus }: { q: string; type?: SearchType | null; autoFocus?: boolean }) {
  return (
    <Form action={routes.search()} role="search" aria-label="Поиск по сайту" className="gv-search-form gv-sr-form">
      <label htmlFor="search-page-q" className="sr-only">
        Что ищем
      </label>
      <span className="gv-search-box">
        <Icon name="search" size={18} />
        <input
          key={q}
          id="search-page-q"
          type="search"
          name="q"
          defaultValue={q}
          maxLength={SEARCH_MAX_QUERY}
          placeholder="Например: Камчатка, Алексей, Ладога"
          autoComplete="off"
          enterKeyHint="search"
          autoFocus={autoFocus}
        />
      </span>
      {type ? <input type="hidden" name="types" value={type} /> : null}
      <Button type="submit" variant="primary" iconRight="arrow">
        Найти
      </Button>
    </Form>
  );
}
