"use client";
/**
 * «Мои доски» (BRD-01/08/09/12): the only place to manage models — cards with a pencil (editor) and a clickable
 * name («Фото и параметры»), availability tabs and search (URL params, shareable), «Добавить доску», and the
 * bulk table of variants below. The editor and the viewer are deep-linked modals (?model=, ?view=).
 */
import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { shaperApi, shaperKeys, type ModelsFilter, type Workshop } from "@/lib/api/shaper";
import { cx } from "@/lib/cx";
import { pluralize, WORDS } from "@/lib/format";
import { useSearchParamModal } from "@/lib/hooks/useSearchParamModal";
import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { QueryState } from "@/components/ui/QueryState";
import { EmptyState, LoadingState } from "@/components/ui/States";
import { BulkTable } from "./BulkTable";
import { ModelCard } from "./ModelCard";
import { ModelEditor } from "./ModelEditor";
import { ModelViewer } from "./ModelViewer";
import { ShaperGate } from "./ShaperShell";

export const BOARD_FILTERS = [
  { id: "all", label: "Все" },
  { id: "in_stock", label: "В наличии" },
  { id: "made_to_order", label: "Под заказ" },
  { id: "out_of_stock", label: "Нет в наличии" },
  { id: "draft", label: "Черновики" },
  { id: "archived", label: "Архив" },
] as const;

export type BoardFilterId = (typeof BOARD_FILTERS)[number]["id"];

export function filterQuery(filter: string, q: string): ModelsFilter {
  const out: ModelsFilter = {};
  if (filter === "archived") out.status = "archived";
  else if (filter === "draft") out.status = "draft";
  else if (filter === "in_stock" || filter === "made_to_order" || filter === "out_of_stock") out.availability = filter;
  if (q.trim()) out.q = q.trim();
  return out;
}

function Boards({ workshop, organization }: { workshop: Workshop; organization: string | null }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const filter = (BOARD_FILTERS.some((f) => f.id === params.get("filter")) ? params.get("filter") : "all") as BoardFilterId;
  const urlQ = params.get("q") ?? "";
  const [search, setSearch] = useState(urlQ);
  const editor = useSearchParamModal("model");
  const viewer = useSearchParamModal("view");

  const setParams = (patch: Record<string, string | null>) => {
    const p = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === "" || (k === "filter" && v === "all")) p.delete(k);
      else p.set(k, v);
    }
    const qs = p.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  // debounce search into the URL
  useEffect(() => {
    if (search === urlQ) return;
    const t = setTimeout(() => setParams({ q: search }), 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const query = filterQuery(filter, urlQ);
  const models = useQuery({
    queryKey: shaperKeys.models(workshop.id, query),
    queryFn: () => shaperApi.models(workshop.id, query),
    placeholderData: (prev) => prev,
  });
  const filtered = filter !== "all" || Boolean(urlQ);
  const readOnly = filter === "archived";

  return (
    <div className="gv-sc-boards">
      <div className="section-head">
        <h3>
          <Icon name="board" className="ic" size={19} /> Мои доски
          {models.data ? <span className="gv-sc-count">{pluralize(models.data.count, WORDS.model)}</span> : null}
        </h3>
        <Button variant="primary" icon="plus" onClick={() => editor.open("new")}>
          Добавить доску
        </Button>
      </div>
      <div className="gv-sc-filters">
        <div className="tabs gv-sc-tabs" role="group" aria-label="Фильтр моделей">
          {BOARD_FILTERS.map((f) => (
            <button key={f.id} type="button" className={cx("tab", filter === f.id && "active")} aria-pressed={filter === f.id} onClick={() => setParams({ filter: f.id })}>
              {f.label}
            </button>
          ))}
        </div>
        <TextInput
          className="gv-sc-search"
          label="Поиск по названию или артикулу"
          hideLabel
          type="search"
          placeholder="Название или артикул…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <QueryState
        query={models}
        loading={<LoadingState variant="skeleton" lines={5} label="Загружаем модели…" />}
        isEmpty={(d) => d.results.length === 0}
        empty={
          filtered ? (
            <EmptyState
              compact
              title={urlQ ? "Ничего не нашлось" : filter === "archived" ? "В архиве пусто" : "Нет моделей с таким статусом"}
              text={urlQ ? `По запросу «${urlQ}» моделей нет.` : undefined}
              action={{
                label: "Показать все модели",
                onClick: () => {
                  setSearch("");
                  setParams({ filter: null, q: null });
                },
              }}
            />
          ) : (
            <EmptyState
              compact
              title="Моделей пока нет"
              text="Добавьте первую доску: название, тип, размер и фото — артикул присвоится автоматически."
              action={{ label: "Добавить доску", onClick: () => editor.open("new") }}
            />
          )
        }
      >
        {(data) => (
          <>
            <div className={cx("models gv-sc-models", models.isFetching && "is-refreshing")} aria-busy={models.isFetching || undefined}>
              {data.results.map((m) => (
                <ModelCard key={m.id} model={m} onEdit={readOnly ? undefined : () => editor.open(m.id)} onView={() => viewer.open(m.id)} readOnly={readOnly} />
              ))}
            </div>
            {data.count > data.results.length && (
              <p className="form-help">Показаны первые {data.results.length} из {data.count}. Уточните поиск, чтобы найти остальные.</p>
            )}
          </>
        )}
      </QueryState>

      {!readOnly && <BulkTable workshopId={workshop.id} onEdit={(id) => editor.open(id)} />}

      <ModelEditor workshop={workshop} modelId={editor.value} onClose={editor.close} organization={organization} />
      <ModelViewer
        modelId={viewer.value}
        onClose={viewer.close}
        onEdit={(id) => {
          viewer.close();
          setTimeout(() => editor.open(id), 0);
        }}
      />
    </div>
  );
}

export function BoardsPage() {
  return <ShaperGate title="Мои доски">{(workshop, organization) => <Boards workshop={workshop} organization={organization} />}</ShaperGate>;
}
