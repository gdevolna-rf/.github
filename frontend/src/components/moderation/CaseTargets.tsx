"use client";
/**
 * Case body by target type: spot change (diff, author, source, evidence), review (published vs pending
 * revision), certificate (fields + private scan), organization (public card preview), complaint/appeal
 * (target snapshot, reporter, owner history, appeal text).
 */
import Link from "next/link";
import type { ReactNode } from "react";
import type {
  CertificateCaseTarget,
  ComplaintCaseTarget,
  ComplaintSnapshot,
  ModeratorMedia,
  OrganizationCaseTarget,
  ReviewCaseTarget,
  SpotChangeTarget,
} from "@/lib/api/moderation";
import { formatDate, formatMoney } from "@/lib/format";
import { choiceCode, choiceLabel, ORGANIZATION_KIND_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { StatusBadge, Tag } from "@/components/ui/Badge";
import { ClampText } from "@/components/ui/ClampText";
import { Icon } from "@/components/ui/Icon";
import { MediaImage } from "@/components/ui/MediaImage";
import { Stars } from "@/components/ui/Rating";
import { Facts, MediaGrid, PersonLine, SectionTitle, When } from "./Bits";
import { COMPLAINT_ACTION_LABELS, COMPLAINT_REASON_LABELS, COMPLAINT_TARGET_LABELS, REVIEW_TARGET_LABELS } from "./labels";
import { modRoutes } from "./routes";
import { SpotDiff } from "./SpotDiff";

const ext = { target: "_blank", rel: "noreferrer noopener" } as const;

function PublicLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} {...ext} className="gv-mod-link">
      {children}
      <Icon name="external" size={13} />
      <span className="sr-only"> (откроется в новой вкладке)</span>
    </Link>
  );
}

function Quote({ children, label }: { children: string; label?: string }) {
  if (!children?.trim()) return null;
  return (
    <figure className="gv-mod-quote-fig">
      {label && <figcaption>{label}</figcaption>}
      <blockquote className="gv-mod-quote">
        <ClampText lines={6}>{children}</ClampText>
      </blockquote>
    </figure>
  );
}

/* ---------------- spot change ---------------- */

export function SpotChangeView({ t, onExpired }: { t: SpotChangeTarget; onExpired: () => void }) {
  return (
    <>
      <section className="gv-mod-block" aria-labelledby="sc-head">
        <SectionTitle icon="map-pin">
          <span id="sc-head">
            Спот <PublicLink href={routes.spot(t.spot.slug)}>{t.spot.name}</PublicLink>
          </span>
        </SectionTitle>
        <Facts
          items={[
            ["Регион", t.spot.region],
            ["Статус правки", <StatusBadge key="s" domain="proposal" status={choiceCode(t.status)} />],
            ["Автор", <PersonLine key="a" person={t.author} />],
            ["Отправлено", <When key="w" value={t.created_at} />],
            ["Источник", t.source || <span className="gv-mod-muted">не указан</span>],
            ["Решение", t.decided_at ? <When key="d" value={t.decided_at} /> : null],
            ["Модератор", t.moderator ? <PersonLine key="m" person={t.moderator} size={24} /> : null],
            ["Откат", t.reverted_at ? <When key="r" value={t.reverted_at} prefix="откатано" /> : null],
          ]}
        />
        <Quote label="Комментарий автора">{t.comment}</Quote>
        <Quote label="Комментарий модератора">{t.moderator_comment}</Quote>
      </section>
      <section className="gv-mod-block" aria-labelledby="sc-diff">
        <SectionTitle icon="edit">
          <span id="sc-diff">Изменения</span>
        </SectionTitle>
        <SpotDiff items={t.diff} />
      </section>
      <section className="gv-mod-block" aria-labelledby="sc-evidence">
        <SectionTitle icon="camera">
          <span id="sc-evidence">Фото-доказательства</span>
        </SectionTitle>
        <MediaGrid items={t.evidence} label="Фото-доказательства" onExpired={onExpired} empty="Автор не приложил фото." />
      </section>
    </>
  );
}

/* ---------------- review ---------------- */

function ReviewVersion({ title, rating, text, photos, onExpired, tone }: { title: string; rating: number | null; text: string; photos: ModeratorMedia[]; onExpired: () => void; tone?: "new" }) {
  return (
    <div className={tone === "new" ? "gv-mod-version is-new" : "gv-mod-version"}>
      <span className="gv-mod-diff-head">{title}</span>
      {rating ? (
        <div className="gv-mod-rating">
          <Stars value={rating} size={16} />
          <b>{rating} из 5</b>
        </div>
      ) : null}
      {text ? <ClampText lines={8}>{text}</ClampText> : <p className="gv-mod-muted">Без текста</p>}
      {photos.length > 0 && <MediaGrid items={photos} label={`${title}: фото`} onExpired={onExpired} />}
    </div>
  );
}

export function ReviewView({ t, onExpired }: { t: ReviewCaseTarget; onExpired: () => void }) {
  return (
    <>
      <section className="gv-mod-block" aria-labelledby="rv-head">
        <SectionTitle icon="star">
          <span id="rv-head">
            Отзыв о <PublicLink href={t.target.link}>{t.target.name}</PublicLink>
          </span>
        </SectionTitle>
        <Facts
          items={[
            ["Объект", REVIEW_TARGET_LABELS[t.target_type] ?? t.target.type],
            ["Статус", <StatusBadge key="s" domain="review" status={choiceCode(t.status)} />],
            ["Автор", <PersonLine key="a" person={t.author} />],
            ["Контекст услуги", t.context_label],
            ["Написан", <When key="c" value={t.created_at} />],
            ["Опубликован", t.published_at ? <When key="p" value={t.published_at} /> : null],
            ["Заметка модератора", t.moderation_note],
          ]}
        />
      </section>
      <section className="gv-mod-block" aria-labelledby="rv-text">
        <SectionTitle icon="chat">
          <span id="rv-text">{t.has_pending_revision ? "Опубликованная версия и новая редакция" : "Текст отзыва"}</span>
        </SectionTitle>
        {t.has_pending_revision ? (
          <div className="gv-mod-versions">
            <ReviewVersion title="Опубликовано сейчас" rating={t.rating} text={t.text} photos={t.photos} onExpired={onExpired} />
            <ReviewVersion
              title="Новая редакция на модерации"
              rating={t.pending_rating}
              text={t.pending_text}
              photos={t.pending_photos}
              onExpired={onExpired}
              tone="new"
            />
          </div>
        ) : (
          <ReviewVersion title="Отзыв" rating={t.rating} text={t.text} photos={t.photos} onExpired={onExpired} />
        )}
      </section>
    </>
  );
}

/* ---------------- certificate ---------------- */

function isExpired(date: string | null): boolean {
  if (!date) return false;
  return new Date(`${date}T23:59:59`).getTime() < Date.now();
}

export function CertificateView({ t, onExpired }: { t: CertificateCaseTarget; onExpired: () => void }) {
  const doc = t.document;
  const url = doc?.signed_url ?? null;
  const isImage = doc && (doc.kind === "image" || (doc.content_type || "").startsWith("image/"));
  return (
    <>
      <section className="gv-mod-block" aria-labelledby="ct-head">
        <SectionTitle icon="shield">
          <span id="ct-head">{t.title}</span>
        </SectionTitle>
        <Facts
          items={[
            ["Статус", <StatusBadge key="s" domain="certificate" status={choiceCode(t.status)} />],
            ["Кем выдан", t.issuer || <span className="gv-mod-muted">не указано</span>],
            ["Дата выдачи", t.issued_on ? formatDate(t.issued_on, { style: "long" }) : null],
            [
              "Действует до",
              t.valid_until ? (
                <span key="v">
                  {formatDate(t.valid_until, { style: "long" })} {isExpired(t.valid_until) && <Tag variant="plain" className="gv-mod-expired">срок истёк</Tag>}
                </span>
              ) : (
                "бессрочно"
              ),
            ],
            ["Показ скана на карточке", t.allow_public_scan ? "Разрешён инструктором" : "Не разрешён"],
            ["Инструктор", <PersonLine key="i" person={t.instructor.account} role={t.instructor.headline || undefined} />],
            ["Карточка инструктора", choiceLabel(t.instructor.status, { draft: "Черновик", published: "Опубликована", hidden: "Скрыта модератором", archived: "В архиве" }) || t.instructor.status],
            ["Загружен", <When key="c" value={t.created_at} />],
            ["Решение", t.decided_at ? <When key="d" value={t.decided_at} /> : null],
          ]}
        />
        <Quote label="Комментарий модератора">{t.moderator_comment}</Quote>
      </section>
      <section className="gv-mod-block" aria-labelledby="ct-scan">
        <SectionTitle icon="paperclip">
          <span id="ct-scan">Скан документа</span>
        </SectionTitle>
        <p className="gv-ac-note gv-mod-pd">
          <Icon name="lock" size={15} /> Скан может содержать персональные данные. Ссылка действует 2 минуты, просмотр записан в журнал.
        </p>
        {!doc ? (
          <p className="gv-mod-muted">Документ не найден.</p>
        ) : !url ? (
          <p className="gv-mod-muted">
            Ссылка на файл недоступна.{" "}
            <button type="button" className="feature-link" onClick={onExpired}>
              Обновить
            </button>
          </p>
        ) : isImage ? (
          <MediaGrid items={[doc]} label="Скан сертификата" onExpired={onExpired} />
        ) : (
          <div className="gv-mod-pdf">
            <object data={url} type={doc.content_type || "application/pdf"} aria-label="Скан сертификата (PDF)">
              <p className="gv-mod-muted">Браузер не показывает PDF во встроенном виде.</p>
            </object>
            <a className="feature-link" href={url} {...ext}>
              Открыть «{doc.original_filename || "скан"}» в новой вкладке <Icon name="external" size={14} />
            </a>
          </div>
        )}
      </section>
    </>
  );
}

/* ---------------- organization ---------------- */

const FORMAT_LABELS: Record<string, string> = { individual: "Индивидуально", pair: "Вдвоём", group: "Группа", kids: "Дети", online: "Онлайн" };
const LANGUAGE_LABELS: Record<string, string> = { ru: "Русский", en: "Английский", zh: "Китайский", ja: "Японский", ko: "Корейский", de: "Немецкий", fr: "Французский", es: "Испанский" };

export function OrganizationView({ t }: { t: OrganizationCaseTarget }) {
  const kindCode = choiceCode(t.kind) ?? "";
  const publicHref = kindCode === "school" ? routes.school(t.slug) : kindCode === "workshop" ? routes.shaper(t.slug) : null;
  return (
    <>
      <section className="gv-mod-block" aria-labelledby="org-head">
        <SectionTitle icon="school">
          <span id="org-head">Карточка, как её увидят посетители</span>
        </SectionTitle>
        <article className="gv-mod-org-card">
          <div className="gv-mod-org-cover">
            <MediaImage media={t.cover} alt={`Обложка «${t.name}»`} placeholder="Обложки нет" />
          </div>
          <div className="gv-mod-org-main">
            <div className="gv-mod-org-title">
              {t.logo && (
                <span className="gv-mod-org-logo">
                  <MediaImage media={t.logo} alt="" prefer="thumb" />
                </span>
              )}
              <div>
                <span className="gv-mod-kicker">{choiceLabel(t.kind, ORGANIZATION_KIND_LABELS)}</span>
                <h4 className="gv-clamp-2" title={t.name}>
                  {t.name}
                </h4>
                <p className="gv-mod-muted">{[t.region, t.city].filter(Boolean).join(" · ") || "Регион не указан"}</p>
              </div>
            </div>
            {t.short_description && <p className="gv-mod-lead">{t.short_description}</p>}
            {t.description ? <ClampText lines={5}>{t.description}</ClampText> : <p className="gv-mod-muted">Описания нет.</p>}
          </div>
        </article>
        <Facts
          items={[
            ["Статус", <StatusBadge key="s" domain="organization" status={t.status} />],
            ["Владелец", <PersonLine key="o" person={t.owner} />],
            ["Адрес", t.address],
            ["Телефон", t.phone],
            ["Email", t.email],
            ["Сайт", t.website ? <a key="w" href={t.website} {...ext} className="gv-mod-link">{t.website}</a> : null],
            ["Форматы", t.formats?.map((f) => FORMAT_LABELS[f] ?? f).join(", ")],
            ["Языки", t.languages?.map((l) => LANGUAGE_LABELS[l] ?? l).join(", ")],
            ["Цена от", t.price_from ? formatMoney(t.price_from, t.currency || "RUB") : null],
            [
              "Споты",
              t.spots?.length ? (
                <span key="sp" className="gv-mod-inline-list">
                  {t.spots.map((s) => (
                    <PublicLink key={s.id} href={routes.spot(s.slug)}>
                      {s.name}
                    </PublicLink>
                  ))}
                </span>
              ) : null,
            ],
            ["Соцсети", t.social_links && Object.keys(t.social_links).length ? Object.values(t.social_links).join(", ") : null],
            ["Отправлено", <When key="c" value={t.created_at} />],
            ["Заметка модератора", t.moderation_note],
          ]}
        />
        {publicHref && t.status === "published" && <PublicLink href={publicHref}>Открыть публичную карточку</PublicLink>}
      </section>
      {t.gallery?.length > 0 && (
        <section className="gv-mod-block" aria-labelledby="org-gallery">
          <SectionTitle icon="photo">
            <span id="org-gallery">Галерея</span>
          </SectionTitle>
          <MediaGrid items={t.gallery} label="Галерея организации" />
        </section>
      )}
    </>
  );
}

/* ---------------- complaint / appeal ---------------- */

function Snapshot({ type, s, onExpired }: { type: string; s: ComplaintSnapshot; onExpired: () => void }) {
  if (!s.exists) return <p className="gv-mod-muted">Объект удалён — решение можно принять только по владельцу.</p>;
  switch (type) {
    case "spot":
      return <Facts items={[["Спот", s.link ? <PublicLink key="l" href={s.link}>{s.name}</PublicLink> : s.name], ["Регион", s.region], ["Статус", s.status ? <StatusBadge key="st" domain="publication" status={s.status} /> : null]]} />;
    case "account":
      return (
        <>
          <PersonLine person={s.account} />
          {s.is_active === false && <Tag variant="plain">Аккаунт деактивирован</Tag>}
          <Quote label="О себе">{s.bio ?? ""}</Quote>
        </>
      );
    case "review":
      return (
        <>
          <Facts
            items={[
              ["Отзыв о", s.target ? <PublicLink key="t" href={s.target.link}>{s.target.name}</PublicLink> : null],
              ["Автор", s.author ? <PersonLine key="a" person={s.author} size={24} /> : null],
              ["Оценка", s.rating ? <Stars key="r" value={s.rating} /> : null],
              ["Статус", s.status ? <StatusBadge key="st" domain="review" status={s.status} /> : null],
            ]}
          />
          <Quote>{s.text ?? ""}</Quote>
        </>
      );
    case "message":
      return (
        <>
          <Facts
            items={[
              ["Отправитель", s.sender ? <PersonLine key="s" person={s.sender} size={24} /> : "—"],
              ["Отправлено", s.created_at ? <When key="c" value={s.created_at} /> : null],
              ["Видимость", s.is_hidden ? "Скрыто модератором" : "Видно участникам диалога"],
            ]}
          />
          <p className="gv-ac-note gv-mod-pd">
            <Icon name="lock" size={15} /> Просмотр сообщения модератором записан в журнал.
          </p>
          <Quote>{s.body ?? ""}</Quote>
          {s.attachments && s.attachments.length > 0 && <MediaGrid items={s.attachments} label="Вложения" onExpired={onExpired} />}
        </>
      );
    case "board_model":
      return (
        <>
          <Facts
            items={[
              ["Модель", s.link ? <PublicLink key="l" href={s.link}>{s.name}</PublicLink> : s.name],
              ["Мастерская", s.workshop ? <PublicLink key="w" href={routes.shaper(s.workshop.slug)}>{s.workshop.name}</PublicLink> : null],
              ["Статус", s.status ? <StatusBadge key="st" domain="publication" status={s.status} /> : null],
            ]}
          />
          <Quote>{s.description ?? ""}</Quote>
        </>
      );
    case "inventory_item":
      return (
        <>
          <Facts
            items={[
              ["Объявление", s.link ? <PublicLink key="l" href={s.link}>{s.title}</PublicLink> : s.title],
              ["Опубликовано", s.is_published ? "Да" : "Нет"],
              ["Владелец", s.owner ? <PersonLine key="o" person={s.owner} size={24} /> : null],
              ["Организация", s.organization?.name],
            ]}
          />
          <Quote>{s.description ?? ""}</Quote>
        </>
      );
    case "organization":
      return (
        <Facts
          items={[
            ["Организация", s.name],
            ["Тип", s.kind ? ORGANIZATION_KIND_LABELS[s.kind as keyof typeof ORGANIZATION_KIND_LABELS] ?? s.kind : null],
            ["Статус", s.status ? <StatusBadge key="st" domain="organization" status={s.status} /> : null],
          ]}
        />
      );
    case "media":
      return s.media ? <MediaGrid items={[s.media]} label="Медиафайл" onExpired={onExpired} /> : null;
    case "club_event":
      return (
        <Facts
          items={[
            ["Событие", s.link ? <PublicLink key="l" href={s.link}>{s.title}</PublicLink> : s.title],
            ["Начало", s.starts_at ? <When key="s" value={s.starts_at} /> : null],
            ["Статус", s.status ? <StatusBadge key="st" domain="event" status={s.status} /> : null],
          ]}
        />
      );
    default:
      return <pre className="gv-mod-pre">{JSON.stringify(s, null, 2)}</pre>;
  }
}

export function ComplaintView({ t, isAppeal, onExpired }: { t: ComplaintCaseTarget; isAppeal: boolean; onExpired: () => void }) {
  const targetType = choiceCode(t.target_type) ?? "";
  const h = t.owner_history;
  return (
    <>
      {isAppeal && (
        <section className="gv-mod-block gv-mod-appeal" aria-labelledby="ap-head">
          <SectionTitle icon="refresh">
            <span id="ap-head">Апелляция владельца</span>
          </SectionTitle>
          <Facts
            items={[
              ["Обжалуемая мера", choiceLabel(t.action_taken, COMPLAINT_ACTION_LABELS)],
              ["Подана", t.appealed_at ? <When key="a" value={t.appealed_at} /> : null],
              ["Владелец", t.target_owner ? <PersonLine key="o" person={t.target_owner} /> : null],
            ]}
          />
          <Quote label="Текст апелляции">{t.appeal_text}</Quote>
        </section>
      )}
      <section className="gv-mod-block" aria-labelledby="cp-head">
        <SectionTitle icon="alert">
          <span id="cp-head">Жалоба</span>
        </SectionTitle>
        <Facts
          items={[
            ["Причина", choiceLabel(t.reason, COMPLAINT_REASON_LABELS)],
            ["На что", choiceLabel(t.target_type, COMPLAINT_TARGET_LABELS)],
            ["Статус жалобы", <StatusBadge key="s" domain="complaint" status={choiceCode(t.status)} />],
            ["Мера", choiceCode(t.action_taken) !== "none" || choiceCode(t.status) === "resolved" ? choiceLabel(t.action_taken, COMPLAINT_ACTION_LABELS) : null],
            ["Автор жалобы", <PersonLine key="r" person={t.reporter} />],
            ["Подана", <When key="c" value={t.created_at} />],
          ]}
        />
        <Quote label="Текст жалобы">{t.text}</Quote>
      </section>
      <section className="gv-mod-block" aria-labelledby="cp-target">
        <SectionTitle icon="target">
          <span id="cp-target">Объект жалобы · {choiceLabel(t.target_type, COMPLAINT_TARGET_LABELS)}</span>
        </SectionTitle>
        <Snapshot type={targetType} s={t.target_snapshot} onExpired={onExpired} />
      </section>
      <section className="gv-mod-block" aria-labelledby="cp-owner">
        <SectionTitle icon="user">
          <span id="cp-owner">Владелец материала</span>
        </SectionTitle>
        {t.target_owner ? (
          <>
            <PersonLine person={t.target_owner} />
            {h && (
              <Facts
                className="gv-mod-facts-row"
                items={[
                  ["Жалоб на владельца", String(h.complaints_total)],
                  ["Подтверждено", String(h.complaints_upheld)],
                  ["Действующих ограничений", String(h.active_restrictions)],
                ]}
              />
            )}
            <Link href={modRoutes.account(t.target_owner.id)} className="feature-link">
              Сводка и ограничения аккаунта →
            </Link>
          </>
        ) : (
          <p className="gv-mod-muted">У объекта нет владельца (например, спот каталога). Доступны меры «Без действий» и «Материал скрыт».</p>
        )}
      </section>
    </>
  );
}

