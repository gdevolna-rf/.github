"use client";
/**
 * «Как это видит клиент» — live preview of the public catalogue card (PUBLIC_SCREENS §3.2 `article.person-card`)
 * built from the unsaved form. Display only: the real card, rating and certificate badge come from the server.
 */
import type { Media } from "@/lib/api/types";
import { formatPriceFrom, plural, WORDS } from "@/lib/format";
import { RIDING_LEVEL_LABELS } from "@/lib/labels";
import { CertificateBadge } from "@/components/ui/CertificateBadge";
import { ClampText } from "@/components/ui/ClampText";
import { Icon } from "@/components/ui/Icon";
import { MediaImage } from "@/components/ui/MediaImage";
import { Rating } from "@/components/ui/Rating";
import { LANGUAGE_LABELS, LESSON_FORMAT_LABELS, listLabels, STUDENT_LEVEL_LABELS } from "@/components/learning-cabinet/dictionaries";
import { experienceYears, type ProfileForm } from "./profileForm";

export function InstructorCardPreview({
  form,
  name,
  photo,
  regionNames,
  spotNames,
  boardNames,
  certificate,
  ratingAvg,
  ratingCount,
  effectivePrice,
}: {
  form: ProfileForm;
  name: string;
  photo: Media | null;
  regionNames: string[];
  spotNames: string[];
  boardNames: string[];
  certificate: string;
  ratingAvg: string | number;
  ratingCount: number;
  /** server «от» price (min of price_from and active offers) when the form price is empty */
  effectivePrice: string | null;
}) {
  const years = experienceYears(form);
  const fact = form.fun_facts.map((f) => f.trim()).find(Boolean);
  const price = form.price_from.trim() ? form.price_from.replace(",", ".") : effectivePrice;
  const students = listLabels(STUDENT_LEVEL_LABELS, form.student_levels);
  return (
    <aside className="lc-preview" aria-labelledby="ins-preview-title">
      <div className="lc-preview-head">
        <h3 id="ins-preview-title">Как это видит клиент</h3>
        <small>Предпросмотр обновляется сразу, на сайте — после сохранения.</small>
      </div>
      <article className="person-card lc-preview-card" aria-label={`Карточка в каталоге: ${name}`}>
        <div className="person-photo">
          <MediaImage media={photo} alt={`Фото: ${name}`} placeholder="Фото пока нет" />
          {regionNames[0] && (
            <span className="tag region-tag" title={`Регион работы: ${regionNames.join(", ")}`}>
              <Icon name="map-pin" size={12} /> {regionNames[0]}
            </span>
          )}
        </div>
        <div className="person-body">
          <div className="person-name">
            <h3 className="gv-clamp-2" title={name}>
              {name}
            </h3>
            <Rating value={ratingAvg} count={ratingCount} />
          </div>
          {form.headline.trim() && <p className="lc-preview-headline gv-clamp-2">{form.headline.trim()}</p>}
          <div className="fieldline">
            <span className="sym">
              <Icon name="clover" size={16} />
            </span>
            <span>
              Инструктор по сёрфингу <CertificateBadge status={certificate} compact />
            </span>
          </div>
          <div className="fieldline">
            <span className="sym">
              <Icon name="target" size={16} />
            </span>
            <span>
              <b>Споты</b>
              {spotNames.length ? spotNames.join(", ") : "Споты уточняются"}
            </span>
          </div>
          {boardNames.length > 0 && (
            <div className="fieldline">
              <span className="sym">
                <Icon name="board" size={16} />
              </span>
              <span>
                <b>Доски</b>
                {boardNames.join(", ")}
              </span>
            </div>
          )}
          <div className="tiny-cols">
            <div className="fieldline">
              <span className="sym">
                <Icon name="clock" size={16} />
              </span>
              <span>
                <b>Опыт</b>
                {years !== null ? `${years} ${plural(years, WORDS.year)}` : "не указан"}
              </span>
            </div>
            <div className="fieldline">
              <span className="sym">
                <Icon name="users" size={16} />
              </span>
              <span>
                <b>Уровень учеников</b>
                {students || "любой"}
              </span>
            </div>
          </div>
          {fact && (
            <div className="fact">
              <Icon name="sun" size={14} /> <strong>Забавный факт</strong>
              <ClampText lines={3}>{fact}</ClampText>
            </div>
          )}
          <div className="lc-preview-price">
            Занятие <b>{formatPriceFrom(price, form.currency)}</b>
          </div>
        </div>
      </article>
      <dl className="lc-preview-facts">
        {form.formats.length > 0 && (
          <>
            <dt>Форматы</dt>
            <dd>{listLabels(LESSON_FORMAT_LABELS, form.formats)}</dd>
          </>
        )}
        {form.languages.length > 0 && (
          <>
            <dt>Языки</dt>
            <dd>{listLabels(LANGUAGE_LABELS, form.languages)}</dd>
          </>
        )}
        {form.riding_level && (
          <>
            <dt>Свой уровень</dt>
            <dd>{RIDING_LEVEL_LABELS[form.riding_level] ?? ""}</dd>
          </>
        )}
        {form.contact_note.trim() && (
          <>
            <dt>Как договориться</dt>
            <dd>{form.contact_note.trim()}</dd>
          </>
        )}
      </dl>
      {form.about.trim() && (
        <div className="lc-preview-about">
          <b>О себе</b>
          <ClampText lines={5}>{form.about.trim()}</ClampText>
        </div>
      )}
    </aside>
  );
}
