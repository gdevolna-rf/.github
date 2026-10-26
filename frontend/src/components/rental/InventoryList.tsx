"use client";
/**
 * «Снаряжение» list (RENT-01/02): cards with cover, status, catalogue visibility, prices and the linked board
 * variant (BRD-13); filters by status / kind / search (server-side). Actions are delegated to the parent.
 */
import { useDeferredValue, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { inventoryApi, inventoryKeys, PURPOSE_LABELS, type InventoryFilter, type InventoryItem } from "@/lib/api/inventory";
import { cx } from "@/lib/cx";
import { formatMoney, plural, pluralize, WORDS } from "@/lib/format";
import { CONDITION_LABELS, INVENTORY_KIND_LABELS, STATUS, choiceLabel } from "@/lib/labels";
import { ButtonLink, Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/States";
import { Icon } from "@/components/ui/Icon";
import { IconButton } from "@/components/ui/IconButton";
import { MediaImage } from "@/components/ui/MediaImage";
import { QueryState } from "@/components/ui/QueryState";
import { Select, TextInput } from "@/components/ui/Field";
import { StatusBadge } from "@/components/ui/Badge";
import styles from "./rental.module.css";

const STATUS_OPTIONS = Object.entries(STATUS.inventory).map(([value, def]) => ({ value, label: def.label }));
const KIND_OPTIONS = Object.entries(INVENTORY_KIND_LABELS).map(([value, label]) => ({ value, label }));

/** «1 600 ₽ / сутки · 400 ₽ / час» — only the prices of the item's purpose. */
export function itemPrices(item: InventoryItem): Array<{ value: string; unit: string }> {
  const out: Array<{ value: string; unit: string }> = [];
  const rental = item.purpose === "rental" || item.purpose === "both";
  const sale = item.purpose === "sale" || item.purpose === "both";
  if (rental && item.rental_price_per_day) out.push({ value: formatMoney(item.rental_price_per_day, item.currency), unit: "/ сутки" });
  if (rental && item.rental_price_per_hour) out.push({ value: formatMoney(item.rental_price_per_hour, item.currency), unit: "/ час" });
  if (sale && item.sale_price) out.push({ value: formatMoney(item.sale_price, item.currency), unit: "продажа" });
  return out;
}

export function isInCatalog(item: InventoryItem): boolean {
  return item.is_published && item.status === "available" && (item.purpose === "rental" || item.purpose === "both");
}

export function InventoryCard({
  item,
  onEdit,
  onStatus,
  onDelete,
}: {
  item: InventoryItem;
  onEdit: (item: InventoryItem) => void;
  onStatus: (item: InventoryItem) => void;
  onDelete: (item: InventoryItem) => void;
}) {
  const kind = choiceLabel(item.kind, INVENTORY_KIND_LABELS) || item.kind_label;
  const condition = choiceLabel(item.condition, CONDITION_LABELS) || item.condition_label;
  const place = [item.region?.name, item.spot?.name].filter(Boolean).join(" · ");
  const prices = itemPrices(item);
  const sold = item.status === "sold";
  const muted = item.status === "retired" || sold;
  return (
    <article className={cx(styles.card, muted && styles.isMuted)} aria-labelledby={`inv-${item.id}`}>
      <div className={styles.media}>
        <MediaImage media={item.cover} alt={item.title} prefer="thumb" />
        <div className={styles.mediaBadges}>
          <StatusBadge domain="inventory" status={item.status} />
          {!item.is_published && (
            <span className={styles.hidden}>
              <Icon name="lock" size={12} /> Скрыто из каталога
            </span>
          )}
        </div>
        {item.photos_count > 1 && (
          <span className={styles.photoCount}>
            <Icon name="photo" size={13} /> {item.photos_count} {plural(item.photos_count, WORDS.photo)}
          </span>
        )}
      </div>
      <div className={styles.body}>
        <h4 id={`inv-${item.id}`} className={cx(styles.title, "gv-clamp-2")} title={item.title}>
          {item.title}
        </h4>
        <p className={styles.meta}>{[kind, item.size, condition && `состояние: ${condition.toLowerCase()}`].filter(Boolean).join(" · ")}</p>
        {place && (
          <p className={cx(styles.meta, styles.metaRow)}>
            <Icon name="map-pin" size={14} />
            <span>{place}</span>
          </p>
        )}
        {item.pickup_location && (
          <p className={cx(styles.meta, styles.metaRow)}>
            <Icon name="target" size={14} />
            <span className="gv-clamp-2" title={item.pickup_location}>
              {item.pickup_location}
            </span>
          </p>
        )}
        {item.available_hours && (
          <p className={cx(styles.meta, styles.metaRow)}>
            <Icon name="clock" size={14} />
            <span>{item.available_hours}</span>
          </p>
        )}
        {prices.length > 0 ? (
          <p className={styles.price}>
            {prices.map((p, i) => (
              <span key={p.unit}>
                {i > 0 && " · "}
                {p.value} <small>{p.unit}</small>
              </span>
            ))}
          </p>
        ) : (
          <p className={styles.meta}>Цена не указана · {PURPOSE_LABELS[item.purpose] ?? ""}</p>
        )}
        {item.variant && (
          <p className={styles.variant} title={item.variant.sku}>
            Модель мастерской: <b>{item.variant.model_name}</b> · {item.variant.dimensions_display} · арт. {item.variant.sku}
          </p>
        )}
      </div>
      <div className={styles.cardActions}>
        {!sold && <IconButton icon="pencil" label={`Изменить «${item.title}»`} shape="round" iconSize={18} onClick={() => onEdit(item)} />}
        {!sold && (
          <Button variant="soft" size="sm" onClick={() => onStatus(item)} aria-label={`Сменить статус «${item.title}»`}>
            Статус
          </Button>
        )}
        <IconButton icon="trash" label={`Удалить «${item.title}»`} shape="round" iconSize={18} onClick={() => onDelete(item)} />
        <span className={styles.spacer} />
        {isInCatalog(item) && (
          <ButtonLink href={item.public_url} variant="link" size="sm" iconRight="external" aria-label={`«${item.title}» в каталоге аренды`}>
            В каталоге
          </ButtonLink>
        )}
      </div>
    </article>
  );
}

export function InventoryList({
  organization,
  onEdit,
  onStatus,
  onDelete,
  onCreate,
  canCreate,
}: {
  organization: string | null;
  onEdit: (item: InventoryItem) => void;
  onStatus: (item: InventoryItem) => void;
  onDelete: (item: InventoryItem) => void;
  onCreate: () => void;
  canCreate: boolean;
}) {
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const query = useDeferredValue(q.trim());
  const filter: InventoryFilter = { status: status || undefined, kind: kind || undefined, q: query || undefined };
  const filtered = Boolean(status || kind || query);
  const list = useQuery({
    queryKey: inventoryKeys.list(organization, filter),
    queryFn: () => inventoryApi.list(organization, filter),
    placeholderData: keepPreviousData,
  });

  return (
    <div>
      <div className={styles.filters} role="search" aria-label="Фильтры снаряжения">
        <TextInput label="Поиск" type="search" placeholder="Название снаряжения" value={q} onChange={(e) => setQ(e.target.value)} />
        <Select label="Статус" placeholder="Все статусы" options={STATUS_OPTIONS} value={status} onChange={(e) => setStatus(e.target.value)} />
        <Select label="Вид" placeholder="Все виды" options={KIND_OPTIONS} value={kind} onChange={(e) => setKind(e.target.value)} />
      </div>
      <QueryState
        query={list}
        isEmpty={(d) => d.results.length === 0}
        empty={
          filtered ? (
            <EmptyState
              compact
              title="Ничего не нашлось"
              text="Попробуйте другой статус, вид или запрос."
              action={{
                label: "Сбросить фильтры",
                icon: "refresh",
                onClick: () => {
                  setStatus("");
                  setKind("");
                  setQ("");
                },
              }}
            />
          ) : (
            <EmptyState
              compact
              title="Снаряжения пока нет"
              text="Добавьте доску, гидрокостюм или другое снаряжение: фото, состояние, место получения и цену. После публикации оно появится в каталоге аренды."
              action={canCreate ? { label: "Добавить снаряжение", icon: "plus", onClick: onCreate } : undefined}
            />
          )
        }
      >
        {(data) => (
          <>
            <p className={styles.count} aria-live="polite">
              {filtered ? "Найдено" : "Всего"}: {pluralize(data.count, ["экземпляр", "экземпляра", "экземпляров"])}
            </p>
            <ul className={styles.grid}>
              {data.results.map((item) => (
                <li key={item.id}>
                  <InventoryCard item={item} onEdit={onEdit} onStatus={onStatus} onDelete={onDelete} />
                </li>
              ))}
            </ul>
          </>
        )}
      </QueryState>
    </div>
  );
}
