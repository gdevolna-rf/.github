/**
 * Size variants of a model (BRD-02/05/07/13): SKU, sizes, volume, material, fins, price, availability with the
 * shared vocabulary («В наличии / Под заказ / Нет в наличии») and an order button per variant. On phones each row
 * becomes a labelled block (no horizontal page scroll, ATX-19).
 */
import { StatusBadge } from "@/components/ui";
import type { BoardDetail, VariantPublic } from "@/lib/api/boards";
import { formatMoney, pluralize, WORDS } from "@/lib/format";
import { BoardOrderButton } from "./BoardActions";

function availabilityNote(v: VariantPublic): string {
  if (v.availability === "in_stock" && v.items_available_for_sale > 0) return `${v.items_available_for_sale} шт. у мастера`;
  if (v.availability === "made_to_order" && v.made_to_order_days) return `≈ ${pluralize(v.made_to_order_days, WORDS.day)}`;
  return "";
}

export function VariantsTable({ board }: { board: BoardDetail }) {
  if (board.variants.length === 0) {
    return <p className="gv-maker-empty">Размеры пока не опубликованы — напишите мастеру, он подберёт параметры.</p>;
  }
  return (
    <div className="gv-variants-wrap">
      <table className="gv-variants">
        <caption className="sr-only">Размеры и варианты модели {board.name}</caption>
        <thead>
          <tr>
            <th scope="col">Артикул</th>
            <th scope="col">Размеры</th>
            <th scope="col">Объём</th>
            <th scope="col">Материал</th>
            <th scope="col">Плавники</th>
            <th scope="col">Цена</th>
            <th scope="col">Наличие</th>
            <th scope="col">
              <span className="sr-only">Действие</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {board.variants.map((v) => {
            const note = availabilityNote(v);
            const fins = [v.fin_system_label, v.fin_setup].filter(Boolean).join(", ");
            return (
              <tr key={v.id}>
                <th scope="row" data-label="Артикул">
                  <span className="gv-article">{v.sku}</span>
                </th>
                <td data-label="Размеры">{v.dimensions_display}</td>
                <td data-label="Объём">{v.volume_display || "—"}</td>
                <td data-label="Материал">{[v.material?.name, v.construction].filter(Boolean).join(", ") || "—"}</td>
                <td data-label="Плавники">{fins || "—"}</td>
                <td data-label="Цена" className="gv-variant-price">
                  {formatMoney(v.price, v.currency) || "По запросу"}
                </td>
                <td data-label="Наличие">
                  <StatusBadge domain="availability" status={v.availability} />
                  {note && <small className="gv-variant-note">{note}</small>}
                </td>
                <td className="gv-variant-action">
                  <BoardOrderButton
                    target={{
                      modelId: board.id,
                      modelName: board.name,
                      workshopId: board.shaper.id,
                      workshopName: board.shaper.name,
                      isOwn: board.is_own,
                      variant: { id: v.id, sku: v.sku, label: v.dimensions_display, price: v.price, currency: v.currency },
                    }}
                    label={v.availability === "out_of_stock" ? "Спросить" : "Заказать"}
                    size="sm"
                    variant={v.availability === "out_of_stock" ? "pill" : "primary"}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
