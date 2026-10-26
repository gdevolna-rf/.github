/**
 * Account navigation (ACC-02, ACC-09): general screens for everyone + professional sections for each active
 * specialty / organization membership + moderation for staff. Pure function → unit-testable.
 */
import type { Me } from "@/lib/api/auth";
import type { Counters } from "@/lib/api/types";
import type { IconName } from "@/components/ui/icons/registry";
import { ORGANIZATION_KIND_LABELS } from "./labels";
import { routes } from "./routes";

export interface AccountNavItem {
  href: string;
  label: string;
  icon: IconName;
  badge?: number;
  /** red badge (needs attention) instead of the blue count */
  alert?: boolean;
  /** match only the exact path (Обзор) */
  exact?: boolean;
  sub?: boolean;
}

export interface AccountNavGroup {
  id: string;
  label: string;
  items: AccountNavItem[];
}

export function buildAccountNav(me: Me, counters: Counters): AccountNavGroup[] {
  const a = routes.account;
  const general: AccountNavItem[] = [
    { href: a.root, label: "Обзор", icon: "home", exact: true },
    // ACC-09: Профиль и Настройки рядом
    { href: a.profile, label: "Профиль", icon: "user" },
    { href: a.settings, label: "Настройки", icon: "settings" },
    {
      href: a.inquiries,
      label: "Обращения",
      icon: "chat",
      badge: counters.unread_messages + counters.new_inquiries,
      alert: counters.unread_messages > 0,
    },
    { href: a.bookings, label: "Мои бронирования", icon: "calendar", badge: counters.pending_bookings },
    { href: a.favorites, label: "Избранное", icon: "heart" },
    { href: a.notifications, label: "Уведомления", icon: "bell", badge: counters.unread_notifications, alert: counters.unread_notifications > 0 },
    { href: a.specialties, label: "Мои направления", icon: "plus" },
  ];

  const pro: AccountNavItem[] = [];
  if (me.specialties.includes("surfer")) pro.push({ href: a.diary, label: "Сёрфер · дневник", icon: "waves" });
  if (me.specialties.includes("instructor")) pro.push({ href: a.instructor, label: "Инструктор", icon: "clover" });
  if (me.specialties.includes("shaper")) pro.push({ href: a.shaper, label: "Шейпер · мастерская", icon: "ruler" });
  if (me.specialties.includes("rental")) pro.push({ href: a.rental, label: "Прокат", icon: "board" });
  const orgs = me.organizations.filter((o) => !o.status || o.status === "active" || o.status === "published" || o.status === "draft" || o.status === "pending_review");
  if (orgs.length) {
    pro.push({ href: a.orgs, label: orgs.length === 1 ? ORGANIZATION_KIND_LABELS[orgs[0].kind] ?? "Организация" : "Школы и организации", icon: "school", exact: orgs.length > 1 });
    if (orgs.length > 1 || orgs[0].id) {
      for (const org of orgs.slice(0, 6)) {
        if (org.id) pro.push({ href: a.org(org.id), label: org.name, icon: org.kind === "workshop" ? "ruler" : org.kind === "rental" ? "board" : "school", sub: true });
      }
    }
  }

  const groups: AccountNavGroup[] = [{ id: "general", label: "Общее", items: general }];
  if (pro.length) groups.push({ id: "pro", label: "Мои специальности", items: pro });
  if (me.isModerator) groups.push({ id: "staff", label: "Служебное", items: [{ href: routes.moderation, label: "Модерация", icon: "shield" }] });
  return groups;
}

export function isNavItemActive(item: AccountNavItem, pathname: string): boolean {
  if (item.exact) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}
