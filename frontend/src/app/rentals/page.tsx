/** /rentals — каталог аренды снаряжения (RENT-01..05). SSR; фильтры — GET-параметры (ссылки шарятся). */
import type { Metadata } from "next";
import Link from "next/link";
import { Hero } from "@/components/layout/PageBlocks";
import { HeartButton, MediaImage } from "@/components/ui";
import { serverFetchSafe } from "@/lib/api/server";
import type { RentalCard } from "@/lib/api/publicCatalogs";
import type { Paginated } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 60;
type SP = Promise<Record<string, string | string[] | undefined>>;

export const metadata: Metadata = buildMetadata({
  title: "Аренда сёрф-снаряжения",
  description: "Доски, гидрокостюмы и SUP в аренду у своих — по регионам и спотам России.",
  path: routes.rentals,
});

const KINDS = [
  ["", "Всё снаряжение"],
  ["board", "Доски"],
  ["wetsuit", "Гидрокостюмы"],
  ["sup", "SUP"],
  ["accessory", "Аксессуары"],
];

export default async function RentalsPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const q = new URLSearchParams();
  for (const k of ["kind", "region", "spot", "organization", "price_max", "q", "from", "to", "page"]) {
    const v = sp[k];
    if (typeof v === "string" && v) q.set(k, v);
  }
  const [data, regions] = await Promise.all([
    serverFetchSafe<Paginated<RentalCard>>(`rentals?${q.toString()}`, { revalidate: 60, tags: ["rentals"] }),
    serverFetchSafe<Array<{ slug: string; name: string }>>("regions", { revalidate: 3600 }),
  ]);
  const items = data?.results ?? [];
  return (
    <>
      <Hero title="Аренда снаряжения" text="Доска или гидрокостюм на пару дней — найдите снаряжение у своих в нужном регионе." />
      <div className="wrap gv-page-body">
        <form className="rent-filterbar" method="get" action={routes.rentals}>
          <label className="filter">
            <span>Регион</span>
            <select name="region" defaultValue={typeof sp.region === "string" ? sp.region : ""}>
              <option value="">Все регионы</option>
              {(regions ?? []).map((r) => (
                <option key={r.slug} value={r.slug}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            <span>Категория</span>
            <select name="kind" defaultValue={typeof sp.kind === "string" ? sp.kind : ""}>
              {KINDS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            <span>Свободно с</span>
            <input type="date" name="from" defaultValue={typeof sp.from === "string" ? sp.from : ""} />
          </label>
          <label className="filter">
            <span>по</span>
            <input type="date" name="to" defaultValue={typeof sp.to === "string" ? sp.to : ""} />
          </label>
          {typeof sp.organization === "string" && <input type="hidden" name="organization" value={sp.organization} />}
          <button className="btn primary" type="submit">
            Показать
          </button>
          <Link className="pill" href={routes.rentals}>
            Сбросить
          </Link>
        </form>
        <p className="small muted">Показано {data?.count ?? 0} предложений. Цены указывают владельцы; бронь подтверждает владелец.</p>
        {data === null ? (
          <p className="muted">Каталог временно недоступен. Обновите страницу.</p>
        ) : items.length === 0 ? (
          <div className="gv-spot-empty">
            <h3>Эти доски укатили на волну</h3>
            <p>Попробуйте другой регион, даты или категорию.</p>
          </div>
        ) : (
          <div className="rent-grid">
            {items.map((i) => (
              <article key={i.id} className="rent-card">
                <Link href={routes.rental(i.id)} className="rent-art" aria-hidden tabIndex={-1}>
                  <MediaImage media={i.cover} alt="" />
                </Link>
                <div className="rent-card-body">
                  <div className="micro muted">
                    {[i.region?.name, i.spot?.name].filter(Boolean).join(" · ")}
                    <HeartButton type="inventory_item" id={i.id} name={i.title} />
                  </div>
                  <h3>
                    <Link href={routes.rental(i.id)}>{i.title}</Link>
                  </h3>
                  <div className="rent-chips">
                    {i.size && <span>{i.size}</span>}
                    <span>{i.kind_label}</span>
                    <span>У {i.owner.name}</span>
                  </div>
                  <div className="rent-card-footer">
                    <b>{i.rental_price_per_day ? formatMoney(i.rental_price_per_day, i.currency) : i.rental_price_per_hour ? formatMoney(i.rental_price_per_hour, i.currency) : "по запросу"}</b>
                    <span className="muted">{i.rental_price_per_day ? " / день" : i.rental_price_per_hour ? " / час" : ""}</span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
        <p className="spot-safety">
          <b>Бережно относимся к чужим вещам.</b> Акты выдачи и возврата фиксируют состояние; залог и онлайн-оплата появятся после утверждения
          коммерческих правил. Сейчас списаний нет.
        </p>
      </div>
    </>
  );
}
