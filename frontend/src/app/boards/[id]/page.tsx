/**
 * Board model page «Фото и параметры» (BRD-02/03/08/10, AT-01, F01): gallery (cover first, ≤10 photos + separate
 * video tile), parameters with size/volume/fins icons, size variants with SKU/price/availability and «Заказать» →
 * InquiryDialog (board_purchase on the model or a variant), favourites, complaint, workshop card.
 * Server Component (SEO, JSON-LD Product); viewer-specific bits are client islands.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BoardOrderButton, ShaperActions } from "@/components/boards/BoardActions";
import { boardPriceLabel } from "@/components/boards/BoardCard";
import { MediaGallery } from "@/components/boards/MediaGallery";
import { ShaperAvatar } from "@/components/boards/ShaperAvatar";
import { VariantsTable } from "@/components/boards/VariantsTable";
import { ViewTracker } from "@/components/boards/ViewTracker";
import "@/components/boards/boards.css";
import { ReportButton } from "@/components/trust/ReportButton";
import { ClampText, HeartButton, Icon, Rating, StatusBadge, Tag } from "@/components/ui";
import { placeLine, silhouetteSrc, type BoardDetail, type VariantPublic } from "@/lib/api/boards";
import { isApiError } from "@/lib/api/errors";
import { serverFetch } from "@/lib/api/server";
import { pluralize, truncate, WORDS } from "@/lib/format";
import { routes } from "@/lib/routes";
import { absoluteUrl, buildMetadata, jsonLd } from "@/lib/seo";

export const revalidate = 120;

type Props = { params: Promise<{ id: string }> };

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function getBoard(id: string): Promise<BoardDetail> {
  if (!UUID_RE.test(id)) notFound();
  try {
    return await serverFetch<BoardDetail>(`boards/${id}`, { revalidate: 120, tags: ["boards", `board:${id}`] });
  } catch (err) {
    if (isApiError(err) && err.isNotFound) notFound();
    throw err;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  if (!UUID_RE.test(id)) return buildMetadata({ title: "Доска не найдена", path: routes.board(id), noindex: true });
  try {
    const b = await serverFetch<BoardDetail>(`boards/${id}`, { revalidate: 120, tags: ["boards", `board:${id}`] });
    return buildMetadata({
      title: `${b.name} — ${b.board_type.name}, ${b.shaper.name}`,
      description: truncate(
        b.description || `${b.board_type.name} ${b.length_range_display ?? ""} от мастерской ${b.shaper.name}${b.shaper.region ? ` (${b.shaper.region.name})` : ""}: размеры, объём, цена и наличие.`,
        160,
      ),
      path: routes.board(id),
      image: b.cover?.url ?? null,
    });
  } catch {
    return buildMetadata({ title: "Модель доски", path: routes.board(id) });
  }
}

function materials(variants: VariantPublic[]): string {
  return Array.from(new Set(variants.map((v) => v.material?.name).filter(Boolean))).join(", ");
}

function fins(variants: VariantPublic[]): string {
  return Array.from(new Set(variants.filter((v) => v.fin_system !== "none").map((v) => [v.fin_system_label, v.fin_setup].filter(Boolean).join(" ")))).join(", ");
}

export default async function BoardPage({ params }: Props) {
  const { id } = await params;
  const board = await getBoard(id);
  const v = board.primary_variant;
  const widthThickness = v ? [v.width_display, v.thickness_display].filter(Boolean).join(" × ") : "";
  const finsText = fins(board.variants);
  const materialText = materials(board.variants);
  const photos = board.photos.length
    ? board.photos
    : board.variants.flatMap((variant) => variant.photos).filter((p, i, all) => all.findIndex((x) => x.media.id === p.media.id) === i);
  const place = placeLine(board.shaper.region, board.shaper.city);

  return (
    <div className="wrap">
      <div className="gv-shapers gv-shapers-page gv-board-page">
        <nav className="gv-breadcrumbs" aria-label="Навигационная цепочка">
          <Link href={routes.home}>Главная</Link> <span aria-hidden="true">/</span> <Link href={routes.boardsCatalog}>Доски</Link> <span aria-hidden="true">/</span>{" "}
          <Link href={routes.shaper(board.shaper.slug)}>{board.shaper.name}</Link> <span aria-hidden="true">/</span> <span aria-current="page">{board.name}</span>
        </nav>

        <article className="card gv-board-detail">
          <header className="gv-board-head">
            <div className="gv-board-head-text">
              <p className="gv-profile-topline">Фото и параметры</p>
              <h1>{board.name}</h1>
              <p className="gv-modal-subtitle">
                {v?.sku ? <>Артикул: {v.sku}</> : "Каталог досок"}
                {board.variants_count > 1 ? ` · ${pluralize(board.variants_count, ["вариант", "варианта", "вариантов"])}` : ""}
              </p>
              <div className="gv-board-tags">
                <Tag variant="soft">{board.board_type.name}</Tag>
                <StatusBadge domain="availability" status={board.availability} />
                {board.has_video && (
                  <Tag variant="soft" icon="video">
                    Есть видео
                  </Tag>
                )}
              </div>
            </div>
            <HeartButton type="board_model" id={board.id} name={board.name} variant="pill" />
          </header>

          <div className="gv-board-grid">
            <MediaGallery
              photos={photos.map((p) => ({ id: p.id, media: p.media }))}
              video={board.video}
              title={board.name}
              fallback={{ src: silhouetteSrc(board.board_type), caption: "Фото пока нет — показан силуэт типа доски" }}
            />

            <div className="gv-board-side">
              <dl className="gv-board-specs">
                <div>
                  <dt>
                    <Icon name="board" size={16} /> Тип
                  </dt>
                  <dd>{board.board_type.name}</dd>
                </div>
                <div>
                  <dt>
                    <Icon name="ruler" size={16} /> Длина
                  </dt>
                  <dd>{board.length_range_display || "Уточняется"}</dd>
                </div>
                <div>
                  <dt>
                    <Icon name="ruler" size={16} /> Ширина / толщина
                  </dt>
                  <dd>{widthThickness || "Уточняется"}</dd>
                </div>
                <div>
                  <dt>
                    <Icon name="droplets" size={16} /> Объём
                  </dt>
                  <dd>{board.volume_range_display || "Не указан"}</dd>
                </div>
                <div>
                  <dt>
                    <Icon name="fins" size={16} /> Вид закладных
                  </dt>
                  <dd>{finsText || "Не указан"}</dd>
                </div>
                <div>
                  <dt>
                    <Icon name="sparkle" size={16} /> Материалы
                  </dt>
                  <dd>{materialText || "Не указаны"}</dd>
                </div>
              </dl>

              <div className="gv-board-buy">
                <div className="model-price gv-board-price">{boardPriceLabel(board)}</div>
                <BoardOrderButton
                  target={{ modelId: board.id, modelName: board.name, workshopId: board.shaper.id, workshopName: board.shaper.name, isOwn: board.is_own }}
                  label="Заказать доску"
                  className="gv-block"
                />
                <p className="form-help">Заявка сразу открывает чат с мастером. Оплата и доставка обсуждаются с шейпером — сайт не списывает деньги.</p>
              </div>

              <section className="gv-board-maker" aria-labelledby="board-maker-title">
                <div className="gv-maker-person">
                  <ShaperAvatar logo={board.shaper.logo} name={board.shaper.name} size={48} />
                  <div>
                    <h2 id="board-maker-title" className="gv-board-maker-name">
                      <Link href={routes.shaper(board.shaper.slug)}>{board.shaper.name}</Link>
                    </h2>
                    {place && <div className="gv-region">{place}</div>}
                    <Rating value={board.shaper.rating_avg} count={board.shaper.rating_count} />
                  </div>
                </div>
                <p className="gv-maker-kpi">
                  Изготовление: {board.shaper.lead_time || "уточняйте у мастера"}
                  {board.shaper.does_repair ? " · делает ремонт" : ""}
                </p>
                <ShaperActions workshopId={board.shaper.id} workshopName={board.shaper.name} doesRepair={board.shaper.does_repair} isOwn={board.is_own} layout="row" />
              </section>
            </div>
          </div>

          {board.description && (
            <section className="gv-board-section" aria-labelledby="board-about">
              <h2 id="board-about">О модели</h2>
              <div className="gv-profile-description">
                <ClampText lines={6}>{board.description}</ClampText>
              </div>
            </section>
          )}

          <section className="gv-board-section" aria-labelledby="board-variants">
            <h2 id="board-variants">Размеры и наличие</h2>
            <VariantsTable board={board} />
          </section>

          {board.tags.length > 0 && (
            <div className="gv-profile-chips" aria-label="Теги">
              {board.tags.map((t) => (
                <span key={t} className="gv-profile-chip">
                  {t}
                </span>
              ))}
            </div>
          )}

          <footer className="gv-board-foot">
            <Link href={routes.boardsCatalog} className="plain">
              <Icon name="arrow-left" size={14} /> Все доски
            </Link>
            <ReportButton targetType="board_model" targetId={board.id} label="Пожаловаться на объявление" />
          </footer>
        </article>
      </div>
      <ViewTracker type="board_model" id={board.id} />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={jsonLd({
          "@context": "https://schema.org",
          "@type": "Product",
          name: board.name,
          sku: v?.sku,
          category: board.board_type.name,
          description: board.description || undefined,
          image: photos.map((p) => p.media.url && absoluteUrl(p.media.url)).filter(Boolean),
          brand: { "@type": "Brand", name: board.shaper.name },
          url: absoluteUrl(routes.board(board.id)),
          offers: board.variants
            .filter((x) => x.price)
            .map((x) => ({
              "@type": "Offer",
              sku: x.sku,
              price: x.price,
              priceCurrency: x.currency,
              availability:
                x.availability === "in_stock"
                  ? "https://schema.org/InStock"
                  : x.availability === "made_to_order"
                    ? "https://schema.org/PreOrder"
                    : "https://schema.org/OutOfStock",
            })),
        })}
      />
    </div>
  );
}
