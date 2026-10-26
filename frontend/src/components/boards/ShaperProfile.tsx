/**
 * Shaper (workshop) profile body (SHP-02/03/04/08/10/11, SHAPERS_SCREENS §3.4). Rendered both inside the modal
 * over the catalogue (intercepting route) and on the standalone SEO page /shapers/[slug].
 * Aside: round photo, master, region, rating, repair badge, specialisation / services / materials, actions.
 * Details: about, facts, promo video, works gallery, models grid with «Заказать».
 */
import Link from "next/link";
import { ClampText, Icon, Rating, Tag } from "@/components/ui";
import { ReportButton } from "@/components/trust/ReportButton";
import { boardImage, placeLine, type ShaperDetail } from "@/lib/api/boards";
import { formatMoney, pluralize, WORDS } from "@/lib/format";
import { routes } from "@/lib/routes";
import { BoardOrderButton, ShaperActions } from "./BoardActions";
import { VideoPlayer } from "./PromoVideo";
import { ShaperAvatar } from "./ShaperAvatar";
import { specializationTags } from "./ShaperCard";

function experienceText(shaper: ShaperDetail): string {
  if (shaper.experience_years) return `${pluralize(shaper.experience_years, WORDS.year)} (с ${shaper.experience_since})`;
  if (shaper.experience_since) return `с ${shaper.experience_since} года`;
  return "Не указан";
}

function safeUrl(url: string): string | null {
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.toString() : null;
  } catch {
    return null;
  }
}

/** `modelsHeading` — level of the «Модели мастерской» heading: 3 inside the modal (title is h2), 2 on the page (h1). */
export function ShaperProfile({ shaper, modelsHeading = 3 }: { shaper: ShaperDetail; modelsHeading?: 2 | 3 }) {
  const tags = specializationTags(shaper.specialization, 8);
  const types = shaper.board_types.map((t) => t.name);
  const specialization = tags.length ? tags : types;
  const about = shaper.description || shaper.short_description;
  const website = shaper.website ? safeUrl(shaper.website) : null;
  const H = modelsHeading === 2 ? "h2" : "h3";
  return (
    <div className="gv-shaper-profile">
      <div className="gv-profile-content">
        <aside className="gv-profile-aside" aria-label="О мастере">
          <ShaperAvatar logo={shaper.logo} owner={shaper.owner} name={shaper.name} size={82} />
          <h3>{shaper.owner?.display_name || shaper.name}</h3>
          {shaper.region && <div className="gv-region">{placeLine(shaper.region, shaper.city)}</div>}
          <div className="gv-profile-rating">
            <Rating value={shaper.rating_avg} count={shaper.rating_count} variant="full" />
          </div>
          {shaper.does_repair && (
            <div className="gv-profile-badges">
              <Tag variant="verified" icon="check">
                Делаю ремонт
              </Tag>
            </div>
          )}
          <div className="gv-profile-smalltitle">Специализация</div>
          <div className="gv-profile-chips">
            {specialization.length ? specialization.map((t) => <span key={t} className="gv-profile-chip">{t}</span>) : <span className="muted">Не указана</span>}
          </div>
          <div className="gv-profile-smalltitle">Услуги</div>
          <div className="gv-profile-chips">
            {shaper.services.length ? (
              shaper.services.map((s) => (
                <span key={s} className="gv-profile-chip">
                  {s}
                </span>
              ))
            ) : (
              <span className="muted">Создание моделей досок</span>
            )}
          </div>
          <div className="gv-profile-smalltitle">Материалы</div>
          <div className="gv-profile-chips">
            {shaper.materials.length ? (
              shaper.materials.map((m) => (
                <span key={m.id} className="gv-profile-chip">
                  {m.name}
                </span>
              ))
            ) : (
              <span className="muted">Уточняйте у мастера</span>
            )}
          </div>
          {website && (
            <>
              <div className="gv-profile-smalltitle">Сайт</div>
              <a href={website} className="gv-profile-contact" target="_blank" rel="noopener noreferrer nofollow">
                {website.replace(/^https?:\/\//, "").replace(/\/$/, "")} <Icon name="external" size={12} />
              </a>
            </>
          )}
          <ShaperActions workshopId={shaper.id} workshopName={shaper.name} doesRepair={shaper.does_repair} isOwn={shaper.is_own} />
        </aside>

        <div className="gv-profile-details">
          {about ? (
            <div className="gv-profile-description">
              <ClampText lines={6}>{about}</ClampText>
            </div>
          ) : (
            <p className="gv-profile-description muted">Мастер пока не рассказал о мастерской.</p>
          )}
          <div className="gv-profile-facts">
            <div className="gv-profile-fact">
              <small>Опыт шейпинга</small>
              <strong>{experienceText(shaper)}</strong>
            </div>
            <div className="gv-profile-fact">
              <small>Срок изготовления</small>
              <strong>{shaper.lead_time || "Уточняйте у мастера"}</strong>
            </div>
            <div className="gv-profile-fact">
              <small>Ремонт досок</small>
              <strong>{shaper.does_repair ? shaper.repair_note || "Да, принимаем в ремонт" : "Не выполняет"}</strong>
            </div>
          </div>

          {shaper.promo_video && (
            <section className="gv-profile-section" aria-labelledby={`promo-${shaper.id}`} id="promo">
              <h4 id={`promo-${shaper.id}`} className="gv-profile-section-title">
                <Icon name="video" size={16} /> Промо-видео
              </h4>
              <VideoPlayer video={shaper.promo_video} title={`Промо-видео мастерской ${shaper.name}`} />
            </section>
          )}

          {shaper.gallery.length > 0 && (
            <section className="gv-profile-section" aria-labelledby={`works-${shaper.id}`}>
              <h4 id={`works-${shaper.id}`} className="gv-profile-section-title">
                <Icon name="photo" size={16} /> Фотографии работ
              </h4>
              <ul className="gv-works-grid">
                {shaper.gallery.slice(0, 12).map((m) => (
                  <li key={m.id}>
                    <a href={m.url ?? "#"} target="_blank" rel="noopener noreferrer" aria-label={m.alt_text || `Работа мастерской ${shaper.name}`}>
                      <img src={m.thumbnail_url || m.url || ""} alt={m.alt_text || ""} loading="lazy" decoding="async" />
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <hr className="gv-profile-divider" />
          <div className="section-head">
            <H className="gv-profile-models-title">Модели мастерской</H>
            <span className="muted">{pluralize(shaper.models_count, WORDS.model)}</span>
          </div>
          {shaper.models.length === 0 ? (
            <p className="gv-maker-empty">Модели пока не опубликованы. Можно написать мастеру и обсудить индивидуальный заказ.</p>
          ) : (
            <ul className="gv-profile-models">
              {shaper.models.map((m) => (
                <li key={m.id} className="gv-profile-board">
                  <Link href={routes.board(m.id)} className="gv-board-photo" aria-label={`Фото и параметры: ${m.name}`}>
                    <img src={boardImage(m)} alt="" loading="lazy" decoding="async" />
                  </Link>
                  <strong>
                    <Link href={routes.board(m.id)} className="gv-profile-board-link">
                      {m.name}
                    </Link>
                  </strong>
                  <small>{[m.board_type?.name, m.length_range_display || "размер уточняется", m.volume_range_display].filter(Boolean).join(" · ")}</small>
                  <span className="gv-profile-price">{formatMoney(m.price_from, m.currency) || "Цена по запросу"}</span>
                  <BoardOrderButton
                    target={{ modelId: m.id, modelName: m.name, workshopId: shaper.id, workshopName: shaper.name, isOwn: shaper.is_own }}
                    label="Оставить заявку"
                    size="sm"
                    className="gv-block"
                  />
                </li>
              ))}
            </ul>
          )}
          <div className="gv-profile-report">
            <ReportButton targetType="organization" targetId={shaper.id} label="Пожаловаться на мастерскую" />
          </div>
        </div>
      </div>
    </div>
  );
}
