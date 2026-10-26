"use client";
/**
 * «Ваш обзор» (CABINET_SCREENS §5.1): compact server counters (MET-02) + entry cards to the general screens +
 * notes for connected professional sections. The summary dashboard with a specialty filter (MET-01) is
 * built later on GET /me/metrics.
 */
import Link from "next/link";
import { useCounters, useMe } from "@/lib/auth/hooks";
import { ORGANIZATION_KIND_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { ButtonLink } from "@/components/ui/Button";
import { Icon, type IconName } from "@/components/ui/Icon";
import { StatStrip } from "@/components/ui/StatStrip";

const CARDS: Array<{ title: string; text: string; href: string; icon: IconName }> = [
  { title: "Обращения", text: "Заявки и чаты от клиентов, инструкторов, школ и мастерских.", href: routes.account.inquiries, icon: "chat" },
  { title: "Мои бронирования", text: "Занятия, аренда и записи на ближайшие даты.", href: routes.account.bookings, icon: "calendar" },
  { title: "Мои направления", text: "Подключайте новые специальности без повторной регистрации.", href: routes.account.specialties, icon: "plus" },
  { title: "Профиль и настройки", text: "Общая информация, видимость и управление аккаунтом.", href: routes.account.profile, icon: "settings" },
];

export function AccountOverview() {
  const { me } = useMe();
  const counters = useCounters();
  if (!me) return null;
  return (
    <section className="gv-ac-panel" aria-labelledby="overview-title">
      <h2 id="overview-title">Ваш обзор</h2>
      <p className="gv-ac-desc">Общие события и инструменты всех подключённых направлений в одном месте.</p>
      <StatStrip
        ariaLabel="Что требует внимания"
        items={[
          { label: "Новых сообщений", value: counters.unread_messages },
          { label: "Новых обращений", value: counters.new_inquiries },
          { label: "Ждут подтверждения", value: counters.pending_bookings },
          { label: "Уведомлений", value: counters.unread_notifications },
        ]}
      />
      <div className="gv-ac-cards">
        {CARDS.map((c) => (
          <article key={c.href} className="gv-ac-card">
            <div className="gv-ac-card-head">
              <h3>{c.title}</h3>
              <Icon name={c.icon} size={22} className="gv-ac-card-icon" />
            </div>
            <p>{c.text}</p>
            <ButtonLink href={c.href} variant="soft" iconRight="arrow">
              Открыть
            </ButtonLink>
          </article>
        ))}
      </div>
      {me.specialties.includes("instructor") && (
        <div className="gv-ac-note">
          <Icon name="clover" size={14} /> Инструктор: расписание, заявки, ученики и отзывы — в разделе{" "}
          <Link href={routes.account.instructor}>«Инструктор»</Link>.
        </div>
      )}
      {me.specialties.includes("shaper") && (
        <div className="gv-ac-note">
          <Icon name="ruler" size={14} /> Шейпер: доски, заявки и статистика мастерской — в разделе{" "}
          <Link href={routes.account.shaper}>«Шейпер · мастерская»</Link>.
        </div>
      )}
      {me.organizations.map((o) => (
        <div key={o.id} className="gv-ac-note">
          <Icon name="school" size={14} /> {ORGANIZATION_KIND_LABELS[o.kind] ?? "Организация"}: <Link href={routes.account.org(o.id)}>{o.name}</Link>
        </div>
      ))}
    </section>
  );
}
