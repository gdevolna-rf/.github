"use client";
/**
 * Availability (RENT-03/04): period + kind controls, the own row «Свободных бордов» / «Забронировано» (server
 * summary, MET-02 — availability-specific numbers) and a per-item interval timeline for the chosen period.
 * Busy intervals are only confirmed / issued bookings (the server source of truth, RENT-05) — never computed here.
 */
import Link from "next/link";
import type { AvailabilityItem, AvailabilityOverview, InventoryItem } from "@/lib/api/inventory";
import { cx } from "@/lib/cx";
import { DEFAULT_TIME_ZONE, formatDate, formatDateRange, formatUtcOffset } from "@/lib/format";
import { INVENTORY_KIND_LABELS, STATUS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { StatusBadge, Badge } from "@/components/ui/Badge";
import { Segmented } from "@/components/ui/Segmented";
import { Select, TextInput } from "@/components/ui/Field";
import { StatStrip, type StatItem } from "@/components/ui/StatStrip";
import { EmptyState } from "@/components/ui/States";
import { PERIOD_PRESETS, bookedShare, rangeError, timelineSegments, type PeriodPreset } from "./timeline";
import styles from "./rental.module.css";

export interface PeriodState {
  preset: PeriodPreset;
  from: string;
  to: string;
}

const KIND_OPTIONS = [{ value: "all", label: "Всё снаряжение" }, ...Object.entries(INVENTORY_KIND_LABELS).map(([value, label]) => ({ value, label }))];

export function AvailabilityControls({
  period,
  onPreset,
  onCustom,
  kind,
  onKind,
}: {
  period: PeriodState;
  onPreset: (preset: PeriodPreset) => void;
  onCustom: (from: string, to: string) => void;
  kind: string;
  onKind: (kind: string) => void;
}) {
  const error = period.preset === "custom" ? rangeError(period.from, period.to) : null;
  return (
    <div className={styles.toolbar}>
      <Segmented<PeriodPreset>
        ariaLabel="Период доступности"
        size="sm"
        value={period.preset}
        onChange={onPreset}
        options={[...PERIOD_PRESETS.map((p) => ({ value: p.value, label: p.label })), { value: "custom" as const, label: "Свои даты" }]}
      />
      <Select className={styles.kindField} label="Вид" options={KIND_OPTIONS} value={kind} onChange={(e) => onKind(e.target.value)} />
      {period.preset === "custom" && (
        <div className={styles.dates}>
          <TextInput label="С" type="date" value={period.from} onChange={(e) => onCustom(e.target.value, period.to)} />
          <TextInput label="По (включительно)" type="date" value={period.to} min={period.from} onChange={(e) => onCustom(period.from, e.target.value)} />
          {error && (
            <p className={styles.rangeError} role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** RENT-04: «Свободных бордов» (only boards) or «Свободно сейчас» (other kinds) + «Забронировано». */
export function availabilityStats(data: AvailabilityOverview | undefined, kind: string): StatItem[] {
  const s = data?.summary;
  const dash = "—";
  return [
    {
      label: kind === "board" ? "Свободных бордов" : "Свободно сейчас",
      value: s ? s.free_now : dash,
      hint: "Экземпляры в статусе «Доступен» без подтверждённой или выданной брони в эту минуту",
    },
    { label: "Забронировано", value: s ? s.booked_now : dash, hint: "Подтверждённые или выданные брони, идущие сейчас" },
    { label: "На обслуживании", value: s ? s.maintenance : dash, tone: "muted" },
    { label: "Свободно в периоде", value: s ? s.free_in_range : dash, hint: "Доступные экземпляры без броней в выбранном периоде" },
    { label: "Заняты в периоде", value: s ? s.booked_in_range : dash, hint: "Экземпляры хотя бы с одной бронью в выбранном периоде" },
  ];
}

export function AvailabilityStrip({ data, kind }: { data: AvailabilityOverview | undefined; kind: string }) {
  return <StatStrip ariaLabel="Доступность снаряжения" items={availabilityStats(data, kind)} />;
}

function itemTimeZone(item: InventoryItem | undefined, zones: Map<number, string>): string {
  const regionId = item?.region?.id;
  return (regionId !== undefined && zones.get(Number(regionId))) || DEFAULT_TIME_ZONE;
}

function TimelineRow({
  row,
  from,
  to,
  timeZone,
  now,
}: {
  row: AvailabilityItem;
  from: string;
  to: string;
  timeZone: string;
  now: Date;
}) {
  const segments = timelineSegments(from, to, row.booked);
  const share = bookedShare(from, to, row.booked);
  const start = new Date(from).getTime();
  const end = new Date(to).getTime();
  const nowPct = now.getTime() > start && now.getTime() < end ? ((now.getTime() - start) / (end - start)) * 100 : null;
  const unavailable = row.status !== "available";
  const statusDef = STATUS.inventory[row.status as keyof typeof STATUS.inventory];
  const lastDay = new Date(end - 1);
  const local = timeZone !== DEFAULT_TIME_ZONE ? ` (местное время, ${formatUtcOffset(timeZone, from)})` : "";
  return (
    <li className={styles.row}>
      <div className={styles.rowHead}>
        <h4 className={styles.rowTitle}>
          {row.title} {row.size && <small>· {row.size}</small>}
        </h4>
        <div className={styles.rowBadges}>
          <StatusBadge domain="inventory" status={row.status} />
          {row.is_booked_now ? <Badge tone="new">Сейчас забронирован</Badge> : !unavailable ? <Badge tone="ok">Сейчас свободен</Badge> : null}
          {!row.is_published && <Badge tone="muted">Скрыт из каталога</Badge>}
        </div>
      </div>
      <div
        className={cx(styles.bar, unavailable && styles.isUnavailable)}
        role="img"
        aria-label={
          unavailable
            ? `${statusDef?.label ?? "Недоступен"} — не выдаётся в этом периоде`
            : share > 0
              ? `Занято ${String(share).replace(".", ",")}% периода`
              : "Свободен весь период"
        }
      >
        {segments.map((seg) => (
          <span
            key={seg.interval.booking_id}
            className={cx(
              styles.segment,
              seg.interval.status === "in_progress" && styles.isIssued,
              seg.clippedStart && styles.clipStart,
              seg.clippedEnd && styles.clipEnd,
            )}
            style={{ left: `${seg.left}%`, width: `${seg.width}%` }}
          />
        ))}
        {nowPct !== null && <span className={styles.nowMark} style={{ left: `${nowPct}%` }} aria-hidden="true" />}
      </div>
      <div className={styles.barLabels} aria-hidden="true">
        <span>{formatDate(from, { timeZone: DEFAULT_TIME_ZONE, style: "dayMonth" })}</span>
        <span>{formatDate(lastDay, { timeZone: DEFAULT_TIME_ZONE, style: "dayMonth" })}</span>
      </div>
      {row.booked.length > 0 ? (
        <ul className={styles.intervals} aria-label={`Брони «${row.title}» в периоде${local}`}>
          {row.booked.map((b) => (
            <li key={b.booking_id}>
              <span>
                {formatDateRange(b.starts_at, b.ends_at, { timeZone, now })}
                {local && <small className={styles.tz}>{local}</small>}
              </span>
              <StatusBadge domain="rentalBooking" status={b.status} />
              <Link href={routes.account.booking(b.booking_id)}>Открыть бронь</Link>
            </li>
          ))}
        </ul>
      ) : unavailable ? (
        <p className={styles.meta} style={{ marginTop: 8 }}>
          {row.status === "maintenance" ? "На обслуживании — брони не принимаются, пока не вернёте статус «Доступен»." : "Не выдаётся."}
        </p>
      ) : (
        <p className={styles.free}>Свободен весь период — броней нет.</p>
      )}
    </li>
  );
}

export function AvailabilityTimeline({
  data,
  items,
  zones,
  now = new Date(),
}: {
  data: AvailabilityOverview;
  /** cabinet items by id (region → time zone) */
  items: Map<string, InventoryItem>;
  /** region id → IANA time zone */
  zones: Map<number, string>;
  now?: Date;
}) {
  if (!data.items.length) {
    return (
      <EmptyState
        compact
        title="Нет снаряжения для аренды"
        text="Здесь появятся экземпляры с назначением «Аренда» или «Продажа и аренда» (кроме списанных и проданных)."
      />
    );
  }
  const lastDay = new Date(new Date(data.to).getTime() - 1);
  const first = formatDate(data.from, { timeZone: DEFAULT_TIME_ZONE, style: "dayMonth" });
  const last = formatDate(lastDay, { timeZone: DEFAULT_TIME_ZONE, style: "dayMonth" });
  return (
    <div>
      <p className={styles.periodNote}>
        Период: {first === last ? first : `${first} — ${last}`} (границы суток — по московскому времени; брони — по местному времени
        экземпляра)
      </p>
      <div className={styles.legend} aria-hidden="true">
        <span>
          <i className={styles.swatch} /> Подтверждено
        </span>
        <span>
          <i className={cx(styles.swatch, styles.isIssued)} /> Выдано
        </span>
        <span>
          <i className={cx(styles.swatch, styles.isFree)} /> Свободно
        </span>
        <span>
          <i className={cx(styles.swatch, styles.isNow)} /> Сейчас
        </span>
      </div>
      <ul className={styles.timeline}>
        {data.items.map((row) => (
          <TimelineRow key={row.id} row={row} from={data.from} to={data.to} timeZone={itemTimeZone(items.get(row.id), zones)} now={now} />
        ))}
      </ul>
    </div>
  );
}
