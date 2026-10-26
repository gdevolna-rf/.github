import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";
import { ProductInterestButton } from "@/components/public/CatalogIslands";
import { MediaImage } from "@/components/ui";
import { isApiError } from "@/lib/api/errors";
import type { ProductDetail } from "@/lib/api/publicCatalogs";
import { serverFetch } from "@/lib/api/server";
import { formatMoney } from "@/lib/format";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 300;
type Params = Promise<{ slug: string }>;

const load = cache(async (slug: string) => {
  try {
    return await serverFetch<ProductDetail>(`shop/products/${encodeURIComponent(slug)}`, { revalidate: 300 });
  } catch (e) {
    if (isApiError(e) && e.isNotFound) return null;
    throw e;
  }
});

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const p = await load((await params).slug);
  return p ? buildMetadata({ title: p.title, description: p.description.slice(0, 160), path: routes.product(p.slug) }) : { title: "Товар" };
}

export default async function ProductPage({ params }: { params: Params }) {
  const p = await load((await params).slug);
  if (!p) notFound();
  return (
    <div className="wrap gv-page-body">
      <nav className="small muted">
        <Link href={routes.shop}>Мерч</Link>
      </nav>
      <div className="gv-spot-layout">
        <article className="spot-body">
          <div className="kicker">
            {p.category_label} · {p.status_label}
          </div>
          <h1 className="spot-title">{p.title}</h1>
          {[p.cover, ...p.gallery].filter(Boolean).map((m) => (
            <MediaImage key={m!.id} media={m} alt={p.title} />
          ))}
          <p className="spot-summary">{p.description}</p>
          {Object.keys(p.specs).length > 0 && (
            <dl className="gv-facts">
              {Object.entries(p.specs).map(([k, v]) => (
                <div key={k} className="gv-fact">
                  <dt>{k}</dt>
                  <dd>{String(v)}</dd>
                </div>
              ))}
            </dl>
          )}
        </article>
        <aside className="gv-spot-aside">
          <section className="gv-ac-panel">
            {p.variants.length > 0 && (
              <ul className="lc-list">
                {p.variants.map((v) => (
                  <li key={v.id} className="lc-list-row">
                    <span className="lc-grow">{v.name}</span>
                    <b>{formatMoney(v.price, v.currency)}</b>
                  </li>
                ))}
              </ul>
            )}
            <p className="small muted">{p.purchase_note || "Онлайн-покупка пока недоступна."}</p>
            <ProductInterestButton productId={p.id} slug={p.slug} />
            {p.delivery_note && <p className="small">Доставка: {p.delivery_note}</p>}
            {p.returns_note && <p className="small">Возврат: {p.returns_note}</p>}
          </section>
        </aside>
      </div>
    </div>
  );
}
