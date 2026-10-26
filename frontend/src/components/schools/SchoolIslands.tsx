"use client";
/**
 * Client islands of the school page (SCH-02): actions row, per-program inquiry, per-session booking, review form.
 * Members of the school never see customer actions (the server refuses them too) — they get a cabinet link.
 */
import Link from "next/link";
import { InquiryButton } from "@/components/commerce/InquiryDialog";
import { BookingButton, type BookableSession } from "@/components/learning/BookingDialog";
import { ReportButton } from "@/components/trust/ReportButton";
import { ReviewForm } from "@/components/trust/ReviewForm";
import { ButtonLink, HeartButton } from "@/components/ui";
import { routes } from "@/lib/routes";
import { MemberGate, useIsMember } from "./MemberGate";

interface SchoolRef {
  id: string;
  name: string;
}

export function SchoolActions({ school }: { school: SchoolRef }) {
  const member = useIsMember(school.id);
  return (
    <div className="gv-school-actions">
      <HeartButton type="organization" id={school.id} name={school.name} variant="pill" />
      {member ? (
        <>
          <span className="gv-school-owner-note">Это ваша школа.</span>
          <ButtonLink href={routes.account.org(school.id)} variant="pill" icon="settings">
            Управлять в кабинете
          </ButtonLink>
        </>
      ) : (
        <>
          <InquiryButton kind="program" providerOrganizationId={school.id} providerName={school.name} title={`Написать в ${school.name}`}>
            Написать школе
          </InquiryButton>
          <ReportButton targetType="organization" targetId={school.id} label="Пожаловаться на школу" />
        </>
      )}
    </div>
  );
}

export function ProgramInquiry({ school, program }: { school: SchoolRef; program: { id: string; title: string } }) {
  return (
    <MemberGate organizationId={school.id}>
      <InquiryButton
        kind="program"
        targetType="school_program"
        targetId={program.id}
        providerName={school.name}
        contextLabel={`Программа «${program.title}»`}
        variant="pill"
        size="sm"
        defaultMessage={`Здравствуйте! Интересует программа «${program.title}». Расскажите, пожалуйста, о ближайших датах.`}
      >
        Задать вопрос
      </InquiryButton>
    </MemberGate>
  );
}

export function SessionCta({
  school,
  session,
  timeZone,
}: {
  school: SchoolRef;
  session: BookableSession;
  timeZone?: string;
}) {
  const full = session.free_seats <= 0;
  return (
    <MemberGate
      organizationId={school.id}
      fallback={
        <Link href={routes.session(session.id)} className="feature-link">
          Карточка занятия
        </Link>
      }
    >
      {full ? (
        <ButtonLink href={routes.session(session.id)} variant="pill" size="sm" iconRight="arrow">
          Мест нет — лист ожидания
        </ButtonLink>
      ) : (
        <BookingButton session={session} providerName={school.name} timeZone={timeZone} size="sm" />
      )}
    </MemberGate>
  );
}

export function SchoolReviewForm({ school }: { school: SchoolRef }) {
  return (
    <MemberGate organizationId={school.id}>
      <ReviewForm
        targetType="organization"
        targetId={school.id}
        targetName={school.name}
        eligibilityNote="Отзыв о школе можно оставить после завершённого занятия."
      />
    </MemberGate>
  );
}
