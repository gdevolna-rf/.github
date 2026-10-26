/**
 * «По шейперам» card (SHP-08/09, SHAPERS_SCREENS §3.3): round photo left of the name, region, master, rating,
 * 3-line intro, specialisation/services tags (repair in green, SHP-04), «N моделей · Изготовление: …», models carousel
 * inside the card, and «Перейти в профиль» pinned bottom-left (also on phones — below the carousel).
 */
import Link from "next/link";
import { Icon, Rating } from "@/components/ui";
import { placeLine, type ShaperCard as ShaperCardData } from "@/lib/api/boards";
import { pluralize, WORDS } from "@/lib/format";
import { routes } from "@/lib/routes";
import { ModelCarousel } from "./ModelCarousel";
import { PromoVideoButton } from "./PromoVideo";
import { ShaperAvatar } from "./ShaperAvatar";

/** «Шортборд, Фанборд» → ["Шортборд", "Фанборд"] (max 3). */
export function specializationTags(text: string, max = 3): string[] {
  return text
    .split(/[,;·\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, max);
}

export function acceptsCustomOrders(services: string[]): boolean {
  return services.some((s) => /индивидуал|под заказ|кастом/i.test(s));
}

export function ShaperCard({ shaper }: { shaper: ShaperCardData }) {
  const tags = specializationTags(shaper.specialization);
  const custom = acceptsCustomOrders(shaper.services);
  const profileHref = routes.shaper(shaper.slug);
  return (
    <article className="card maker-card gv-maker-card-v3 gv-shaper-card" aria-labelledby={`shaper-${shaper.id}`}>
      <div className="gv-maker-main gv-maker-grid">
        <div className="gv-maker-profile">
          <div className="gv-maker-person">
            <ShaperAvatar logo={shaper.logo} owner={shaper.owner} name={shaper.name} />
            <div className="gv-maker-title">
              <h3 id={`shaper-${shaper.id}`}>
                <Link href={profileHref} scroll={false} className="gv-maker-name-link">
                  {shaper.name}
                </Link>
              </h3>
              {shaper.region && <div className="gv-region">{placeLine(shaper.region, shaper.city)}</div>}
              {shaper.owner && <small className="muted">{shaper.owner.display_name}</small>}
            </div>
          </div>
          <Rating value={shaper.rating_avg} count={shaper.rating_count} className="gv-maker-rating" />
          {shaper.short_description && <p className="gv-maker-intro">{shaper.short_description}</p>}
          <div className="gv-maker-tags">
            {tags.map((t) => (
              <span key={t}>{t}</span>
            ))}
            {shaper.does_repair && <span className="gv-tag-repair">Ремонт досок</span>}
            {custom && <span>Индивидуальный шейпинг</span>}
          </div>
          <div className="gv-maker-kpi">
            {pluralize(shaper.models_count, WORDS.model)} · Изготовление: {shaper.lead_time || "уточняйте у мастера"}
            {shaper.experience_years ? ` · Опыт: ${pluralize(shaper.experience_years, WORDS.year)}` : ""}
          </div>
        </div>
        <ModelCarousel models={shaper.models} total={shaper.models_count} shaperName={shaper.name} shaperSlug={shaper.slug} />
        <div className="gv-maker-action">
          <Link href={profileHref} scroll={false} className="primary">
            Перейти в профиль <Icon name="arrow" size={15} />
          </Link>
          {shaper.promo_video && <PromoVideoButton video={shaper.promo_video} shaperName={shaper.name} />}
        </div>
      </div>
    </article>
  );
}
