"use client";
/**
 * Client islands of /instructors/[handle]: everything that depends on the viewer (self-view hides booking, inquiry,
 * review and complaint — BR-05, AT-03), the free-slot list with booking dialogs, the certificate scan link.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { InquiryButton } from "@/components/commerce/InquiryDialog";
import { BookingButton } from "@/components/learning/BookingDialog";
import { ReportButton } from "@/components/trust/ReportButton";
import { ReviewForm } from "@/components/trust/ReviewForm";
import { ReviewsSection } from "@/components/trust/ReviewsSection";
import { Button, ButtonLink, HeartButton, Icon, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { labelOf, LESSON_FORMAT_LABELS, STUDENT_LEVEL_LABELS, type LessonSession } from "@/lib/api/learning";
import type { PublicReview } from "@/lib/api/publicReviews";
import type { Paginated } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { formatMoney, formatTime, formatUtcOffset, plural, WORDS } from "@/lib/format";
import { routes } from "@/lib/routes";
import { groupSlotsByDay } from "./catalog";

/** true when the viewer is this instructor (client-side only; the server enforces it anyway). */
export function useIsSelf(handle: string): boolean {
  const { me } = useMe();
  return Boolean(me && me.handle && me.handle === handle);
}

interface ContactTarget {
  accountId: string | null;
  offerId: string | null;
}

export function ProfileActions({
  id,
  handle,
  name,
  contact,
}: {
  id: string;
  handle: string;
  name: string;
  contact: ContactTarget;
}) {
  const self = useIsSelf(handle);
  if (self) {
    return (
      <div className="gv-ins-actions">
        <p className="notice gv-ins-own-note" role="status">
          Это ваш публичный профиль — так его видят ученики.
        </p>
        <ButtonLink href={routes.account.instructor} variant="pill" icon="settings">
          Редактировать в кабинете
        </ButtonLink>
      </div>
    );
  }
  return (
    <div className="gv-ins-actions">
      <ButtonLink href="#schedule" variant="primary" icon="calendar" iconRight="arrow">
        Выбрать занятие
      </ButtonLink>
      <HeartButton type="instructor" id={id} name={name} variant="pill" />
      {contact.accountId || contact.offerId ? (
        <InquiryButton
          kind="lesson"
          variant="pill"
          providerName={name}
          {...(contact.accountId
            ? { providerAccountId: contact.accountId }
            : { targetType: "instructor_offer" as const, targetId: contact.offerId ?? undefined })}
        >
          Написать
        </InquiryButton>
      ) : (
        <span className="lesson-micro">Написать можно после публикации занятий инструктора.</span>
      )}
      {contact.accountId && <ReportButton targetType="account" targetId={contact.accountId} label="Пожаловаться" />}
    </div>
  );
}

export function OfferInquiry({ handle, offerId, providerName, title }: { handle: string; offerId: string; providerName: string; title: string }) {
  const self = useIsSelf(handle);
  if (self) return null;
  return (
    <InquiryButton
      kind="lesson"
      variant="pill"
      targetType="instructor_offer"
      targetId={offerId}
      providerName={providerName}
      contextLabel={`Предложение: ${title}`}
      className="gv-ins-offer-cta"
    >
      Написать об этом занятии
    </InquiryButton>
  );
}

const INITIAL_DAYS = 5;

export function SlotList({ handle, slots, instructorName }: { handle: string; slots: LessonSession[]; instructorName: string }) {
  const self = useIsSelf(handle);
  const [showAll, setShowAll] = useState(false);
  const days = groupSlotsByDay(slots);
  const visible = showAll ? days : days.slice(0, INITIAL_DAYS);
  const zones = Array.from(new Set(days.map((d) => d.timeZone)));

  return (
    <>
      {zones.length > 0 && (
        <p className="gv-ins-slot-tz">
          Время местное: {zones.map((z) => `${z.replace(/_/g, " ")} (${formatUtcOffset(z)})`).join(", ")}.
        </p>
      )}
      <div className="gv-ins-days">
        {visible.map((day) => (
          <section className="gv-ins-day" key={`${day.key}-${day.timeZone}`} aria-label={day.label}>
            <h3>{day.label}</h3>
            <ul className="gv-ins-slots">
              {day.slots.map((slot) => {
                const tz = slot.timezone || day.timeZone;
                const provider = slot.organization?.name ?? instructorName;
                const format = labelOf(LESSON_FORMAT_LABELS, slot.offer?.format ?? slot.program?.format);
                const level = labelOf(STUDENT_LEVEL_LABELS, slot.offer?.level ?? slot.program?.level);
                const price = slot.price ? formatMoney(slot.price, slot.currency || "RUB") : "";
                return (
                  <li className="gv-ins-slot" key={slot.id}>
                    <span className="gv-ins-slot-time">
                      {formatTime(slot.starts_at, tz)}–{formatTime(slot.ends_at, tz)}
                    </span>
                    <span className="gv-ins-slot-info">
                      <b className="gv-clamp-2" title={slot.title}>
                        {slot.title}
                      </b>
                      {[
                        slot.organization ? `Школа «${slot.organization.name}»` : "Частное занятие",
                        format,
                        level,
                        slot.spot?.name,
                        price,
                        `свободно ${slot.free_seats} ${plural(slot.free_seats, WORDS.seat)}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                    {!self && <BookingButton session={slot} providerName={provider} size="sm" />}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
      {days.length > INITIAL_DAYS && (
        <div className="gv-ins-more">
          <Button variant="pill" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
            {showAll ? "Свернуть" : `Показать ещё ${days.length - INITIAL_DAYS} ${plural(days.length - INITIAL_DAYS, WORDS.day)}`}
          </Button>
        </div>
      )}
    </>
  );
}

/** «Скан» link: GET /certificates/{id}/scan → short-lived presigned URL, opened in a new tab (INS-04). */
export function CertificateScanButton({ certificateId, title }: { certificateId: string; title: string }) {
  const toast = useToast();
  const scan = useMutation({
    mutationFn: () => api.get<{ url: string }>(`certificates/${encodeURIComponent(certificateId)}/scan`),
    onSuccess: ({ url }) => {
      const win = window.open(url, "_blank", "noopener,noreferrer");
      if (!win) window.location.assign(url);
    },
    onError: (err) => toast.error(err, { action: { label: "Повторить", onClick: () => scan.mutate() } }),
  });
  return (
    <Button variant="pill" size="sm" icon="external" loading={scan.isPending} onClick={() => scan.mutate()} aria-label={`Открыть скан: ${title}`}>
      Скан документа
    </Button>
  );
}

export function InstructorReviews({
  id,
  handle,
  name,
  initial,
  ratingAvg,
  ratingCount,
}: {
  id: string;
  handle: string;
  name: string;
  initial: Paginated<PublicReview> | null;
  ratingAvg: string | number | null;
  ratingCount: number;
}) {
  const self = useIsSelf(handle);
  return (
    <ReviewsSection
      targetType="instructor"
      targetId={id}
      initial={initial}
      ratingAvg={ratingAvg}
      ratingCount={ratingCount}
      title="Отзывы учеников"
      emptyText="Отзывы появятся после завершения подтверждённых занятий и проверки модератором."
      form={
        <ReviewForm
          targetType="instructor"
          targetId={id}
          targetName={name}
          hidden={self}
          eligibilityNote="Отзыв можно оставить после завершённого занятия с этим инструктором."
        />
      }
    />
  );
}

export function ScheduleEmpty({ handle, name, contact }: { handle: string; name: string; contact: ContactTarget }) {
  const self = useIsSelf(handle);
  return (
    <div className="gv-empty gv-empty-compact lesson-info-card">
      <p>
        <Icon name="calendar" size={16} /> Свободных окон пока нет.{" "}
        {self ? "Добавьте слоты в кабинете инструктора." : "Напишите инструктору — он предложит удобное время."}
      </p>
      {self ? (
        <ButtonLink href={routes.account.instructor} variant="pill">
          Открыть расписание
        </ButtonLink>
      ) : contact.accountId || contact.offerId ? (
        <InquiryButton
          kind="lesson"
          variant="pill"
          providerName={name}
          {...(contact.accountId
            ? { providerAccountId: contact.accountId }
            : { targetType: "instructor_offer" as const, targetId: contact.offerId ?? undefined })}
        >
          Написать инструктору
        </InquiryButton>
      ) : null}
    </div>
  );
}
