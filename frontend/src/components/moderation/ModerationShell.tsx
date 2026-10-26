"use client";
/**
 * /moderation/* frame: staff-only (BR-04, TRUST-06) → 2FA gate (11, DATA-09) → hero + section tabs + page.
 * Same visual language as the personal account (.gv-account / .gv-ac-hero / .gv-tabs).
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, type ReactNode } from "react";
import type { Me } from "@/lib/api/auth";
import { cx } from "@/lib/cx";
import { STAFF_ROLE_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { ButtonLink } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { LoadingState } from "@/components/ui/States";
import { modRoutes } from "./routes";
import { TwoFactorGate } from "./TwoFactorGate";

function ModerationTabs({ me }: { me: Me }) {
  const pathname = usePathname() || modRoutes.queue;
  const section = pathname.startsWith(`${modRoutes.queue}/audit`)
    ? "audit"
    : pathname.startsWith(modRoutes.staff)
      ? "staff"
      : pathname.startsWith(`${modRoutes.queue}/accounts`)
        ? "accounts"
        : "queue";
  const items = [
    { id: "queue", href: modRoutes.queue, label: "Очередь" },
    { id: "audit", href: modRoutes.audit(), label: "Журнал действий" },
    ...(me.isAdmin ? [{ id: "staff", href: modRoutes.staff, label: "Служебные роли" }] : []),
  ];
  return (
    <nav aria-label="Разделы модерации" className="gv-tabs gv-mod-tabs">
      {items.map((t) => {
        const active = t.id === section;
        return (
          <Link key={t.id} href={t.href} className={cx("gv-tab-btn", active && "active")} aria-current={active ? "page" : undefined}>
            <span>{t.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function Frame({ me, children }: { me: Me; children: ReactNode }) {
  const roles = me.staffRoles.map((r) => STAFF_ROLE_LABELS[r] ?? r).join(", ");
  return (
    <>
      <section className="gv-ac-hero gv-mod-hero" aria-label="Служебный раздел">
        <span className="gv-mod-hero-icon" aria-hidden="true">
          <Icon name="shield" size={30} />
        </span>
        <div className="gv-ac-hero-meta">
          <div className="gv-ac-kicker">Служебный раздел ГДеволна</div>
          <h1>Модерация</h1>
          <p>
            {me.displayName}
            {roles ? ` · ${roles}` : ""}
            {me.twoFactor.verified ? " · сессия подтверждена 2FA" : ""}
          </p>
        </div>
        <div className="gv-ac-hero-act">
          <ButtonLink href={routes.account.root} variant="soft">
            В кабинет
          </ButtonLink>
        </div>
      </section>
      <TwoFactorGate me={me}>
        <ModerationTabs me={me} />
        <div className="gv-mod-body">{children}</div>
      </TwoFactorGate>
    </>
  );
}

export function ModerationShell({ children }: { children: ReactNode }) {
  return (
    <div className="gv-account gv-mod">
      <Suspense fallback={<LoadingState label="Открываем модерацию…" />}>
        <RequireAuth staff="moderator" fallback={<LoadingState label="Проверяем права…" />}>
          {(me) => <Frame me={me}>{children}</Frame>}
        </RequireAuth>
      </Suspense>
    </div>
  );
}
