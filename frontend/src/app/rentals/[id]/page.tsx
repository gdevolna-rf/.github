/** /rentals/[id] — экземпляр в аренду: фото, условия, занятые интервалы, бронирование (RENT-03/05). */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";
import { TrackView } from "@/components/analytics/TrackView";
import { InquiryButton } from "@/components/commerce/InquiryDialog";
import { RentalBookingForm } from "@/components/public/CatalogIslands";
import { ReportButton } from "@/components/trust/ReportButton";
import { HeartButton, MediaImage } from "@/components/ui";
import { isApiError } from "@/lib/api/errors";
import { mediaSrc } from "@/lib/api/media";
import type { RentalDetail } from "@/lib/api/publicCatalogs";
import { serverFetch } from "@/lib/api/server";
import { formatDateTime, formatMoney } from "@/lib/format";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 60;
type Params = Promise<{ id: string }>;

const load = cache(async (id: string) => {
  try {
    return await serverFetch<RentalDetail>(`rentals/${encodeURIComponent(id)}`, { revalidate: 60, tags: ["rentals", `rental:${id}`] });
  } catch (e) {
    if (isApiError(e) && e.isNotFound) return null;
    throw e;
  }
});

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const item = await load((await params).id);
  if (!item) return { title: "Объявление не найдено" };
  return buildMetadata({ title: `${item.title} — аренда`, description: item.description.slice(0, 160), path: routes.rental(item.id), image: mediaSrc(item.cover) ?? undefined });
}

export default async function RentalPage({ params }: { params: Params }) {
  const item = await load((await params).id);
  if (!item) notFound();
  const ownerHref = item.owner.type === "account" && item.owner.handle ? routes.surfer(item.owner.handle) : item.owner.slug ? `${routes.rentals}?organization=${item.owner.slug}` : null;
  return (
    <div className="wrap gv-page-body">
      <TrackView subjectType="inventory_item" subjectId={item.id} />
      <nav className="small muted">
        <Link href={routes.rentals}>Аренда</Link>
      </nav>
      <div className="rental-detail gv-spot-layout">
        <article className="spot-body">
          <div className="kicker">ГДеволна · аренда</div>
          <h1 className="spot-title">{item.title}</h1>
          <div className="gv-spot-page-actions">
            <HeartButton type="inventory_item" id={item.id} name={item.title} variant="pill" />
            <ReportButton targetType="inventory_item" targetId={item.id} variant="link" />
          </div>
          <div className="spot-gallery">
            {(item.photos.length ? item.photos.map((p) => p.media) : item.cover ? [item.cover] : []).map((m) => (
              <MediaImage key={m.id} media={m} alt={item.title} />
            ))}
          </div>
          {item.description && <p className="spot-summary">{item.description}</p>}
          <dl className="gv-facts">
            <div className="gv-fact"><dt>Тип</dt><dd>{item.kind_label}</dd></div>
            {item.size && <div className="gv-fact"><dt>Размер</dt><dd>{item.size}</dd></div>}
            <div className="gv-fact"><dt>Состояние</dt><dd>{item.condition_label}</dd></div>
            <div className="gv-fact"><dt>Где</dt><dd>{[item.region?.name, item.spot?.name, item.pickup_location].filter(Boolean).join(", ")}</dd></div>
            {item.available_hours && <div className="gv-fact"><dt>Время выдачи</dt><dd>{item.available_hours}</dd></div>}
            <div className="gv-fact"><dt>Владелец</dt><dd>{ownerHref ? <Link href={ownerHref}>{item.owner.name}</Link> : item.owner.name}</dd></div>
            {item.variant && <div className="gv-fact"><dt>Модель</dt><dd>{item.variant.model_name} · {item.variant.dimensions_display}</dd></div>}
            {item.deposit_note && <div className="gv-fact"><dt>Залог</dt><dd>{item.deposit_note}</dd></div>}
          </dl>
          {item.restrictions && <p><b>Ограничения:</b> {item.restrictions}</p>}
        </article>
        <aside className="gv-spot-aside">
          <section className="gv-ac-panel">
            <div className="rental-bigprice">
              {item.rental_price_per_day ? `${formatMoney(item.rental_price_per_day, item.currency)} / день` : item.rental_price_per_hour ? `${formatMoney(item.rental_price_per_hour, item.currency)} / час` : "Цена по запросу"}
            </div>
            <RentalBookingForm item={item} />
            {!item.is_own && (
              <InquiryButton kind="rental" targetType="inventory_item" targetId={item.id} providerName={item.owner.name} title={item.title} variant="line">
                Задать вопрос владельцу
              </InquiryButton>
            )}
          </section>
          <section className="gv-ac-panel">
            <h2>Занято</h2>
            {item.booked_intervals.length === 0 ? (
              <p className="muted">Подтверждённых броней пока нет.</p>
            ) : (
              <ul className="small">
                {item.booked_intervals.map((b) => (
                  <li key={b.starts_at}>
                    {formatDateTime(b.starts_at)} — {formatDateTime(b.ends_at)}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
