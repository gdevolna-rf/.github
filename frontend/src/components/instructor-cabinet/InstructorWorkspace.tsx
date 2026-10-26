"use client";
/**
 * «Инструктор · рабочее место» (CABINET_SCREENS §6.2, INS-06): panel header + section tabs (each a URL) around
 * the instructor sub-pages. Tools need the «Сёрф-инструктор» specialty (BR-11); a school instructor without it
 * still sees the unified schedule of assigned lessons (SCH-06).
 */
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useMe } from "@/lib/auth/hooks";
import { routes } from "@/lib/routes";
import { ButtonLink } from "@/components/ui/Button";
import { NoAccess } from "@/components/ui/States";
import { CabinetTabs, isTabActive, type CabinetTab } from "@/components/learning-cabinet/CabinetTabs";
import { instructorLinks, instructorPaths as p } from "./paths";

export const INSTRUCTOR_TABS: CabinetTab[] = [
  { href: p.root, label: "Обзор", icon: "home", exact: true },
  { href: p.profile, label: "Карточка", icon: "user" },
  { href: p.offers, label: "Предложения", icon: "brief" },
  { href: p.schedule, label: "Расписание", icon: "calendar" },
  { href: p.students, label: "Ученики", icon: "users" },
  { href: p.certificates, label: "Сертификаты", icon: "shield" },
  { href: p.stats, label: "Статистика", icon: "graph" },
];

export function InstructorWorkspace({ children }: { children: ReactNode }) {
  const { me } = useMe();
  const pathname = usePathname() || p.root;
  if (!me) return null; // AccountShell renders loading / login redirect
  const hasSpecialty = me.specialties.includes("instructor");
  const teachesInSchool = me.organizations.some((o) => o.role === "instructor");

  if (!hasSpecialty && !teachesInSchool) {
    return (
      <section className="gv-ac-panel" aria-labelledby="ins-title">
        <h2 id="ins-title">Инструктор</h2>
        <NoAccess
          title="Направление «Сёрф-инструктор» не подключено"
          text="Подключите направление в разделе «Мои направления» — карточка, расписание, ученики и статистика появятся здесь. История аккаунта сохранится."
          action={{ label: "Мои направления", href: routes.account.specialties }}
        />
      </section>
    );
  }

  const tabs = hasSpecialty ? INSTRUCTOR_TABS : INSTRUCTOR_TABS.filter((t) => t.href === p.schedule);
  const allowed = tabs.some((t) => isTabActive(t, pathname));

  return (
    <section className="gv-ac-panel lc-workspace" aria-labelledby="ins-title">
      <div className="gv-card-head">
        <div className="gv-card-head-text">
          <div className="gv-ac-kicker">Личный кабинет · инструктор</div>
          <h2 id="ins-title">Инструктор · рабочее место</h2>
          <p className="gv-ac-desc">Карточка, предложения, расписание школ и частных занятий, ученики и статистика — в одном месте.</p>
        </div>
        <div className="gv-card-head-actions">
          <ButtonLink href={instructorLinks.inquiries} variant="soft" icon="chat">
            Обращения
          </ButtonLink>
          <ButtonLink href={instructorLinks.bookings} variant="soft" icon="calendar">
            Записи учеников
          </ButtonLink>
        </div>
      </div>
      <CabinetTabs items={tabs} current={pathname} ariaLabel="Разделы кабинета инструктора" />
      <div className="lc-workspace-body">
        {allowed ? (
          children
        ) : (
          <NoAccess
            title="Раздел доступен с направлением «Сёрф-инструктор»"
            text="Сейчас вам доступно расписание занятий школы, куда вас назначили. Подключите направление, чтобы вести свою карточку и частные занятия."
            action={{ label: "Мои направления", href: routes.account.specialties }}
          />
        )}
      </div>
    </section>
  );
}
