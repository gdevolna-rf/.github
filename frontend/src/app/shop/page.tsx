/** /shop — витрина фирменных термосов и мерча ГДеволна (SHOP-01..04, M3): без оплаты до утверждения модели (PAY-03). */
import type { Metadata } from "next";
import Link from "next/link";
import { Hero } from "@/components/layout/PageBlocks";
import { MediaImage } from "@/components/ui";
import type { ProductCard } from "@/lib/api/publicCatalogs";
import { serverFetchSafe } from "@/lib/api/server";
import type { Paginated } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 300;
export const metadata: Metadata = buildMetadata({ title: "Мерч ГДеволна", description: "Фирменные термосы и мерч ГДеволна — скоро.", path: routes.shop });

export default async function ShopPage() {
  const data = await serverFetchSafe<Paginated<ProductCard>>("shop/products", { revalidate: 300 });
  return (
    <>
      <Hero title="Мерч ГДеволна" text="Термосы, которые держат тепло после утренней сессии, и вещи с логотипом. Онлайн-оплата появится позже — подпишитесь на поступление." />
      <div className="wrap gv-page-body">
        {!data || data.results.length === 0 ? (
          <p className="muted">Скоро здесь появятся первые товары.</p>
        ) : (
          <div className="grid-3">
            {data.results.map((p) => (
              <article key={p.id} className="spot-card">
                <Link href={routes.product(p.slug)} className="spot-pic" aria-hidden tabIndex={-1}>
                  <MediaImage media={p.cover} alt="" />
                </Link>
                <div className="spot-body">
                  <div className="micro muted">
                    {p.category_label} · {p.status_label}
                  </div>
                  <h3>
                    <Link href={routes.product(p.slug)}>{p.title}</Link>
                  </h3>
                  {p.price_from && <p className="spot-signal">от {formatMoney(p.price_from, p.currency)}</p>}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
