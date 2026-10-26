"use client";
/**
 * «Быстрое редактирование» (BRD-12): every active variant of the workshop in one table — price, made-to-order
 * days, «в наличии, шт.» and «активен». Saving sends only changed rows to PATCH variants/bulk (all or nothing);
 * server errors `items.N.field` are shown in the matching cell. On phones only the table scrolls sideways,
 * inside its own container (no page scroll, ATX-19).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { shaperApi, shaperKeys, type VariantTableRow } from "@/lib/api/shaper";
import { cx } from "@/lib/cx";
import { pluralize } from "@/lib/format";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { bulkDraftFromRow, bulkErrorsByRow, bulkRowChanges, validateBulkDraft, type BulkDraft, type BulkField } from "./draft";

type RowErrors = Partial<Record<BulkField | "id" | "_row", string>>;

export function BulkTable({ workshopId, onEdit }: { workshopId: string; onEdit?: (modelId: string) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: shaperKeys.variants(workshopId), queryFn: () => shaperApi.variants(workshopId) });
  const rows = useMemo(() => query.data ?? [], [query.data]);
  const originals = useMemo(() => Object.fromEntries(rows.map((r) => [r.id, bulkDraftFromRow(r)])), [rows]);
  const [drafts, setDrafts] = useState<Record<string, BulkDraft>>({});
  const [errors, setErrors] = useState<Record<string, RowErrors>>({});
  const [formError, setFormError] = useState<string | null>(null);

  // keep user edits; start fresh rows from the server values
  useEffect(() => {
    setDrafts((prev) => {
      const next: Record<string, BulkDraft> = {};
      for (const r of rows) next[r.id] = prev[r.id] ?? originals[r.id];
      return next;
    });
  }, [rows, originals]);

  const changed = rows
    .map((r) => ({ row: r, changes: drafts[r.id] ? bulkRowChanges(drafts[r.id], originals[r.id]) : null }))
    .filter((x): x is { row: VariantTableRow; changes: NonNullable<ReturnType<typeof bulkRowChanges>> } => Boolean(x.changes));

  const save = useMutation({
    mutationFn: (items: Array<{ id: string } & NonNullable<ReturnType<typeof bulkRowChanges>>>) => shaperApi.bulkVariants(workshopId, items),
    onSuccess: (res) => {
      setErrors({});
      setFormError(null);
      // the saved rows are the new baseline
      setDrafts((prev) => {
        const next = { ...prev };
        for (const r of res.items) next[r.id] = bulkDraftFromRow(r);
        return next;
      });
      qc.setQueryData<VariantTableRow[]>(shaperKeys.variants(workshopId), (old) =>
        old ? old.map((r) => res.items.find((x) => x.id === r.id) ?? r) : old,
      );
      void qc.invalidateQueries({ queryKey: shaperKeys.all });
      toast.success(`Сохранено вариантов: ${res.updated}. Карточки обновлены.`);
    },
    onError: (err, items) => {
      if (isApiError(err)) {
        const { byRow, other } = bulkErrorsByRow(err.fields, items.map((i) => i.id));
        setErrors(byRow);
        setFormError([err.message, ...other].filter((m, i, a) => m && a.indexOf(m) === i).join(" "));
        if (err.retryable) toast.error(err, { action: { label: "Повторить", onClick: () => save.mutate(items) } });
      } else setFormError(errorMessage(err));
    },
  });

  const submit = () => {
    if (!changed.length) {
      toast.info("Пока нет изменений для сохранения");
      return;
    }
    const local: Record<string, RowErrors> = {};
    for (const { row } of changed) {
      const e = validateBulkDraft(drafts[row.id]);
      if (Object.keys(e).length) local[row.id] = e;
    }
    if (Object.keys(local).length) {
      setErrors(local);
      setFormError("Проверьте значения, отмеченные в таблице.");
      return;
    }
    save.mutate(changed.map(({ row, changes }) => ({ id: row.id, ...changes })));
  };

  const set = (id: string, field: BulkField, value: string | boolean) => {
    setDrafts((d) => ({ ...d, [id]: { ...d[id], [field]: value } }));
    setErrors((e) => (e[id] ? { ...e, [id]: { ...e[id], [field]: undefined, _row: undefined } } : e));
  };

  return (
    <section className="gv-sc-bulk" aria-labelledby="bulk-title">
      <div className="bulk-head">
        <div>
          <h3 id="bulk-title">Быстрое редактирование вариантов</h3>
          <p className="muted">Меняйте цены, сроки и наличие сразу у нескольких размеров — после сохранения карточки выше обновятся.</p>
        </div>
        <Button variant="primary" onClick={submit} loading={save.isPending} disabled={!rows.length}>
          Сохранить изменения{changed.length ? ` (${changed.length})` : ""}
        </Button>
      </div>
      {query.isPending ? (
        <LoadingState variant="skeleton" lines={4} />
      ) : query.isError ? (
        <ErrorState compact error={query.error} onRetry={() => void query.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState compact title="Вариантов пока нет" text="Добавьте модель и её размеры — они появятся в этой таблице." />
      ) : (
        <>
          <div className="bulk-scroll" role="region" aria-label="Таблица вариантов — прокручивается по горизонтали" tabIndex={0}>
            <table className="table bulk-table gv-sc-bulk-table">
              <caption className="sr-only">Варианты досок мастерской: цена, срок изготовления, наличие и активность</caption>
              <thead>
                <tr>
                  <th scope="col">Модель</th>
                  <th scope="col">Артикул</th>
                  <th scope="col">Размер</th>
                  <th scope="col">Цена, ₽</th>
                  <th scope="col">Под заказ, дней</th>
                  <th scope="col">В наличии, шт.</th>
                  <th scope="col">Статус</th>
                  <th scope="col">Активен</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const d = drafts[r.id] ?? originals[r.id];
                  const e = errors[r.id] ?? {};
                  const isChanged = Boolean(bulkRowChanges(d, originals[r.id]));
                  const cell = (field: BulkField) => `bulk-${r.id}-${field}`;
                  const rowLabel = `${r.model.name}, ${r.dimensions_display}`;
                  return (
                    <tr key={r.id} className={cx(isChanged && "changed", Object.keys(e).some((k) => e[k as BulkField]) && "has-error")}>
                      <th scope="row" className="gv-sc-bulk-model">
                        {onEdit ? (
                          <button type="button" className="gv-board-title gv-clamp-2" onClick={() => onEdit(r.model.id)} title={`Открыть «${r.model.name}»`}>
                            {r.model.name}
                          </button>
                        ) : (
                          <span className="gv-clamp-2" title={r.model.name}>
                            {r.model.name}
                          </span>
                        )}
                        <small>{r.model.board_type.name}</small>
                        {e._row && <span className="gv-field-error">{e._row}</span>}
                        {e.id && <span className="gv-field-error">{e.id}</span>}
                      </th>
                      <td className="gv-sc-bulk-sku">{r.sku}</td>
                      <td className="gv-sc-bulk-size">
                        {r.dimensions_display}
                        {r.volume_display ? <small>{r.volume_display}</small> : null}
                      </td>
                      <td>
                        <label className="sr-only" htmlFor={cell("price")}>
                          Цена, ₽ — {rowLabel}
                        </label>
                        <input
                          id={cell("price")}
                          inputMode="decimal"
                          value={d.price}
                          placeholder="—"
                          onChange={(ev) => set(r.id, "price", ev.target.value)}
                          aria-invalid={e.price ? true : undefined}
                          aria-describedby={e.price ? `${cell("price")}-err` : undefined}
                        />
                        {e.price && (
                          <span id={`${cell("price")}-err`} className="gv-field-error">
                            {e.price}
                          </span>
                        )}
                      </td>
                      <td>
                        <label className="sr-only" htmlFor={cell("made_to_order_days")}>
                          Срок изготовления, дней — {rowLabel}
                        </label>
                        <input
                          id={cell("made_to_order_days")}
                          inputMode="numeric"
                          value={d.made_to_order_days}
                          placeholder="—"
                          onChange={(ev) => set(r.id, "made_to_order_days", ev.target.value.replace(/\D/g, ""))}
                          aria-invalid={e.made_to_order_days ? true : undefined}
                          aria-describedby={e.made_to_order_days ? `${cell("made_to_order_days")}-err` : undefined}
                        />
                        {e.made_to_order_days && (
                          <span id={`${cell("made_to_order_days")}-err`} className="gv-field-error">
                            {e.made_to_order_days}
                          </span>
                        )}
                      </td>
                      <td>
                        <label className="sr-only" htmlFor={cell("in_stock_quantity")}>
                          В наличии, шт. — {rowLabel}
                        </label>
                        <input
                          id={cell("in_stock_quantity")}
                          inputMode="numeric"
                          value={d.in_stock_quantity}
                          onChange={(ev) => set(r.id, "in_stock_quantity", ev.target.value.replace(/\D/g, ""))}
                          aria-invalid={e.in_stock_quantity ? true : undefined}
                          aria-describedby={e.in_stock_quantity ? `${cell("in_stock_quantity")}-err` : undefined}
                        />
                        {e.in_stock_quantity && (
                          <span id={`${cell("in_stock_quantity")}-err`} className="gv-field-error">
                            {e.in_stock_quantity}
                          </span>
                        )}
                      </td>
                      <td>
                        <StatusBadge domain="availability" status={r.availability} />
                      </td>
                      <td className="gv-sc-bulk-active">
                        <input
                          type="checkbox"
                          id={cell("is_active")}
                          checked={d.is_active}
                          onChange={(ev) => set(r.id, "is_active", ev.target.checked)}
                          aria-label={`Активен — ${rowLabel}`}
                          aria-invalid={e.is_active ? true : undefined}
                        />
                        {e.is_active && <span className="gv-field-error">{e.is_active}</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="form-help">
            <Icon name="info" size={13} /> Изменения применяются только после «Сохранить изменения» — все строки сразу или ни одна.{" "}
            {pluralize(rows.length, ["вариант", "варианта", "вариантов"])} в таблице. Размеры и материал меняются в карточке
            модели (карандаш) — там же создаётся новая версия, если по размеру уже были заказы.
          </p>
        </>
      )}
      {formError && (
        <p className="gv-sc-form-error" role="alert">
          <Icon name="alert" size={14} /> {formError}
        </p>
      )}
    </section>
  );
}
