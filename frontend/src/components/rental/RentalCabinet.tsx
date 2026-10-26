"use client";
/**
 * «Прокат · снаряжение» (/account/rental, RENT-01…05, ACC-05): whose inventory (personal or an organization —
 * `?organization=`), availability row «Свободных бордов» / «Забронировано», the equipment list and the
 * interval timeline. Incoming rental bookings live in the unified «Бронирования» (box=provider) — linked, not
 * duplicated. URL keeps the owner, tab, period and kind so every view is shareable (NAV-05).
 */
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { Me } from "@/lib/api/auth";
import { inventoryApi, inventoryKeys, type InventoryItem } from "@/lib/api/inventory";
import { shaperApi, shaperKeys } from "@/lib/api/shaper";
import { isApiError } from "@/lib/api/errors";
import { useMe } from "@/lib/auth/hooks";
import { routes } from "@/lib/routes";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { ErrorState, LoadingState, NoAccess } from "@/components/ui/States";
import { QueryState } from "@/components/ui/QueryState";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { AvailabilityControls, AvailabilityStrip, AvailabilityTimeline, type PeriodState } from "./Availability";
import { InventoryFormModal } from "./InventoryFormModal";
import { InventoryList } from "./InventoryList";
import { DeleteDialog, StatusDialog } from "./ItemDialogs";
import { ownerOptions, ownerOrganization, ownerSearch, ownerTitle, ownerValue, resolveOwner, type RentalOwner } from "./owner";
import { PERIOD_PRESETS, presetRange, rangeError, type PeriodPreset } from "./timeline";
import styles from "./rental.module.css";

type View = "inventory" | "availability";

function readPeriod(params: URLSearchParams, now: Date): PeriodState {
  const raw = params.get("period");
  if (raw === "custom") {
    const fallback = presetRange("week", now);
    return { preset: "custom", from: params.get("from") || fallback.from, to: params.get("to") || fallback.to };
  }
  const preset = (PERIOD_PRESETS.some((p) => p.value === raw) ? raw : "today") as Exclude<PeriodPreset, "custom">;
  return { preset, ...presetRange(preset, now) };
}

export function bookingsHref(owner: RentalOwner): string {
  const base = `${routes.account.bookings}?box=provider&kind=rental`;
  return owner.type === "organization" ? `${base}&organization=${encodeURIComponent(owner.id)}` : base;
}

export function RentalCabinet() {
  const { me } = useMe();
  if (!me) return <LoadingState label="Открываем прокат…" />;
  return <RentalWorkspace me={me} />;
}

function NoRental() {
  return (
    <section className="gv-ac-panel" aria-labelledby="rental-title">
      <h2 id="rental-title">Прокат · снаряжение</h2>
      <p className="gv-ac-desc">
        Здесь сдают в аренду доски, гидрокостюмы и другое снаряжение: фото, состояние, место получения, цены и доступность по
        датам.
      </p>
      <div className="gv-ac-empty">
        <p style={{ margin: "0 0 12px" }}>
          Раздел откроется, когда вы подключите направление «Прокат» — без новой регистрации, в том же аккаунте. Если снаряжение
          принадлежит школе или прокату, попросите владельца организации пригласить вас в команду.
        </p>
        <ButtonLink href={routes.account.specialties} variant="primary" iconRight="arrow">
          Мои направления
        </ButtonLink>
      </div>
    </section>
  );
}

function RentalWorkspace({ me }: { me: Me }) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname() || routes.account.rental;
  const [now] = useState(() => new Date());

  const owner = resolveOwner(me, { organization: params.get("organization"), owner: params.get("owner") });
  const organization = ownerOrganization(owner);
  const view: View = params.get("view") === "availability" ? "availability" : "inventory";
  const period = readPeriod(params, now);
  const kind = params.get("kind") || "board";

  const [editing, setEditing] = useState<InventoryItem | null>(null);
  const [creating, setCreating] = useState(false);
  const [statusItem, setStatusItem] = useState<InventoryItem | null>(null);
  const [deleting, setDeleting] = useState<InventoryItem | null>(null);

  const replaceParams = (mutate: (p: URLSearchParams) => void) => {
    // read the live URL: two quick changes (tab, then period) must not overwrite each other
    const p = new URLSearchParams(typeof window !== "undefined" ? window.location.search : params.toString());
    mutate(p);
    const qs = p.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  const periodValid = period.preset !== "custom" || !rangeError(period.from, period.to);
  const availability = useQuery({
    queryKey: inventoryKeys.availability(organization, period.from, period.to, kind),
    queryFn: () => inventoryApi.availability({ organization, from: period.from, to: period.to, kind: kind === "all" ? undefined : kind }),
    enabled: owner.type !== "none" && periodValid,
    placeholderData: keepPreviousData,
  });
  // all items (no filters) — region → time zone for the timeline, and the tab counter
  const allItems = useQuery({
    queryKey: inventoryKeys.list(organization, {}),
    queryFn: () => inventoryApi.list(organization),
    enabled: owner.type !== "none",
  });
  const regions = useQuery({ queryKey: shaperKeys.regions, queryFn: shaperApi.regions, staleTime: 60 * 60_000 });
  const zones = useMemo(() => new Map((regions.data ?? []).filter((r) => r.timezone).map((r) => [Number(r.id), r.timezone as string])), [regions.data]);
  const itemsById = useMemo(() => new Map((allItems.data?.results ?? []).map((i) => [i.id, i])), [allItems.data]);

  if (owner.type === "none") return <NoRental />;

  const forbidden = isApiError(allItems.error) && allItems.error.isForbidden;
  const options = ownerOptions(me, owner);
  const orgMeta = owner.type === "organization" ? me.organizations.find((o) => o.id === owner.id) : undefined;
  const defaultRegionId = owner.type === "personal" ? (me.region?.id ?? null) : null;
  const bookings = bookingsHref(owner);

  return (
    <section className="gv-ac-panel" aria-labelledby="rental-title">
      <div className={styles.head}>
        <div>
          <h2 id="rental-title">Прокат · снаряжение</h2>
          <p className="gv-ac-desc">
            Снаряжение, его состояние и доступность по датам. Занятость считается только по подтверждённым и выданным бронированиям.
          </p>
        </div>
      </div>

      <div className={styles.owner}>
        {options.length > 1 ? (
          <Select
            label="Чей инвентарь"
            options={options}
            value={ownerValue(owner)}
            onChange={(e) =>
              router.replace(`${pathname}?${ownerSearch(e.target.value, new URLSearchParams(window.location.search))}`, { scroll: false })
            }
          />
        ) : (
          <p className={styles.ownerName}>
            Инвентарь: <b>{ownerTitle(owner)}</b>
            {orgMeta?.role && orgMeta.role !== "owner" ? " · вы сотрудник организации" : ""}
          </p>
        )}
      </div>

      {forbidden ? (
        <NoAccess
          text="Вы не состоите в этой организации или ваш доступ отозван. Инвентарь организации доступен только её активным сотрудникам."
          action={{ label: "Мой прокат", href: routes.account.rental }}
        />
      ) : (
        <>
          <div className={styles.actions}>
            <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
              Добавить снаряжение
            </Button>
            <ButtonLink href={bookings} variant="soft" icon="calendar">
              Бронирования аренды
            </ButtonLink>
            <ButtonLink href={routes.rentals} variant="soft" iconRight="arrow">
              Каталог аренды
            </ButtonLink>
          </div>

          <div className={styles.availability} aria-labelledby="rental-availability">
            <div className={styles.availabilityHead}>
              <h3 id="rental-availability">Доступность</h3>
            </div>
            <AvailabilityControls
              period={period}
              kind={kind}
              onKind={(k) => replaceParams((p) => p.set("kind", k))}
              onPreset={(preset) =>
                replaceParams((p) => {
                  p.set("period", preset);
                  if (preset === "custom") {
                    p.set("from", period.from);
                    p.set("to", period.to);
                  } else {
                    p.delete("from");
                    p.delete("to");
                  }
                })
              }
              onCustom={(from, to) =>
                replaceParams((p) => {
                  p.set("period", "custom");
                  p.set("from", from);
                  p.set("to", to);
                })
              }
            />
            {availability.isError && availability.data === undefined ? (
              <ErrorState compact error={availability.error} onRetry={() => void availability.refetch()} />
            ) : (
              <AvailabilityStrip data={availability.data} kind={kind} />
            )}
          </div>

          <Tabs
            idPrefix="rental"
            ariaLabel="Разделы проката"
            value={view}
            onChange={(id) => replaceParams((p) => (id === "inventory" ? p.delete("view") : p.set("view", id)))}
            items={[
              { id: "inventory", label: allItems.data ? `Снаряжение · ${allItems.data.count}` : "Снаряжение" },
              { id: "availability", label: "Брони по датам" },
            ]}
          />
          <TabPanel idPrefix="rental" id="inventory" value={view}>
            <InventoryList
              organization={organization}
              canCreate
              onCreate={() => setCreating(true)}
              onEdit={setEditing}
              onStatus={setStatusItem}
              onDelete={setDeleting}
            />
          </TabPanel>
          <TabPanel idPrefix="rental" id="availability" value={view}>
            <div style={{ marginTop: 14 }}>
              {!periodValid ? (
                <p className="gv-ac-note">Исправьте даты периода, чтобы увидеть брони.</p>
              ) : (
                <QueryState query={availability}>
                  {(data) => <AvailabilityTimeline data={data} items={itemsById} zones={zones} now={now} />}
                </QueryState>
              )}
            </div>
          </TabPanel>
        </>
      )}

      <InventoryFormModal
        open={creating || Boolean(editing)}
        item={editing}
        organizationId={organization}
        defaultRegionId={defaultRegionId}
        canLinkVariants={me.specialties.includes("shaper") || me.organizations.some((o) => o.kind === "workshop")}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
      />
      <StatusDialog item={statusItem} onClose={() => setStatusItem(null)} bookingsHref={bookings} />
      <DeleteDialog item={deleting} onClose={() => setDeleting(null)} bookingsHref={bookings} />
    </section>
  );
}
