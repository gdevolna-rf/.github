"use client";
/**
 * Frame of every shaper cabinet page (/account/shaper/*): the prototype module styles (`.gv-shapers`), a compact
 * header with the round workshop photo left of the name (SHP-02), the promo line on its own line (SHO-09),
 * «Посмотреть на сайте» (SHP-12), the workshop switcher (several workshops) and the section navigation.
 * «Обращения» and «Бронирования» link to the unified inbox / bookings (MSG-01) instead of duplicating them.
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useMe } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { routes } from "@/lib/routes";
import type { Workshop } from "@/lib/api/shaper";
import { Avatar } from "@/components/ui/Avatar";
import { StatusBadge } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { Icon, type IconName } from "@/components/ui/Icon";
import { ErrorState, LoadingState, NoAccess } from "@/components/ui/States";
import { isApiError } from "@/lib/api/errors";
import { shaperRoutes } from "./routes";
import { useWorkshop } from "./useWorkshop";

interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  /** path used for the active state (without query) */
  path?: string;
  external?: boolean;
}

export function ShaperNav({ organization }: { organization?: string | null }) {
  const pathname = usePathname() || routes.account.shaper;
  const items: NavItem[] = [
    { href: shaperRoutes.panel(organization), path: routes.account.shaper, label: "Панель", icon: "home" },
    { href: shaperRoutes.boards(organization), path: `${routes.account.shaper}/boards`, label: "Мои доски", icon: "board" },
    { href: shaperRoutes.workshop(organization), path: `${routes.account.shaper}/workshop`, label: "Мастерская", icon: "user" },
    { href: shaperRoutes.stats(organization), path: `${routes.account.shaper}/stats`, label: "Статистика", icon: "graph" },
    { href: shaperRoutes.inquiries, label: "Обращения", icon: "mail", external: true },
    { href: shaperRoutes.bookings(organization), label: "Бронирования", icon: "calendar", external: true },
  ];
  return (
    <nav className="gv-tabs gv-sc-nav" aria-label="Разделы кабинета шейпера">
      {items.map((item) => {
        const active = !item.external && item.path === pathname;
        return (
          <Link key={item.href} href={item.href} className={cx("gv-tab-btn", active && "active")} aria-current={active ? "page" : undefined}>
            <Icon name={item.icon} size={16} />
            <span>{item.label}</span>
            {item.external && <Icon name="arrow" size={13} className="gv-sc-nav-out" />}
          </Link>
        );
      })}
    </nav>
  );
}

function WorkshopSwitcher({ organization }: { organization?: string | null }) {
  const { me } = useMe();
  const router = useRouter();
  const pathname = usePathname() || routes.account.shaper;
  const workshops = (me?.organizations ?? []).filter((o) => o.kind === "workshop" && o.id);
  if (workshops.length < 2) return null;
  return (
    <Select
      className="gv-sc-switch"
      label="Мастерская"
      value={organization ?? workshops[0].id}
      options={workshops.map((w) => ({ value: w.id, label: w.name }))}
      onChange={(e) => router.replace(`${pathname}?organization=${encodeURIComponent(e.target.value)}`)}
    />
  );
}

export function ShaperShell({
  workshop,
  organization,
  title = "Кабинет шейпера",
  children,
}: {
  workshop?: Workshop | null;
  organization?: string | null;
  title?: string;
  children: ReactNode;
}) {
  return (
    <div className="gv-shapers gv-shaper-cab">
      <section className="gv-ac-panel gv-sc-pane" aria-labelledby="shaper-pane-title">
        <header className="gv-sc-head">
          <div className="gv-sc-identity">
            {workshop && <Avatar media={workshop.logo} name={workshop.name} size={56} className="gv-sc-logo" alt="" />}
            <div className="gv-sc-identity-text">
              <h2 id="shaper-pane-title">{title}</h2>
              {workshop ? (
                <p className="gv-sc-meta">
                  <b className="gv-clamp-1" title={workshop.name}>
                    {workshop.name}
                  </b>
                  {workshop.region?.name ? <span>{workshop.region.name}</span> : null}
                  <StatusBadge domain="organization" status={workshop.status} />
                </p>
              ) : null}
              <p className="gv-sc-promo">
                Управляйте моделями, заявками и профилем.
                <br />
                Развивайте мастерскую с Гдеволна!
              </p>
            </div>
          </div>
          <div className="gv-sc-head-actions">
            <WorkshopSwitcher organization={organization} />
            {workshop &&
              (workshop.is_public ? (
                <ButtonLink href={routes.shaper(workshop.slug)} variant="soft" iconRight="arrow">
                  Посмотреть на сайте
                </ButtonLink>
              ) : (
                <span className="gv-sc-hint" role="note">
                  <Icon name="info" size={14} /> «Посмотреть на сайте» появится после публикации мастерской
                </span>
              ))}
          </div>
        </header>
        <ShaperNav organization={organization} />
        <div className="gv-sc-body">{children}</div>
      </section>
    </div>
  );
}

/**
 * Resolves the workshop for a page and renders every non-success state inside the shell:
 * loading · no workshop (registration form via `whenMissing` / CTA / no specialty) · no access · error + retry.
 */
export function ShaperGate({
  children,
  whenMissing,
  title,
}: {
  children: (workshop: Workshop, organization: string | null) => ReactNode;
  /** rendered for a shaper without a workshop (default — a CTA to the registration form) */
  whenMissing?: (organization: string | null) => ReactNode;
  title?: string;
}) {
  const { me } = useMe();
  const { query, workshop, organization, noWorkshop } = useWorkshop();
  const isShaper = Boolean(me?.specialties.includes("shaper"));
  if (query.isPending) {
    return (
      <ShaperShell organization={organization} title={title}>
        <LoadingState label="Загружаем мастерскую…" />
      </ShaperShell>
    );
  }
  if (noWorkshop) {
    return (
      <ShaperShell organization={organization} title={title}>
        {isShaper ? (whenMissing ? whenMissing(organization) : <NeedWorkshopState organization={organization} />) : <NoShaperState />}
      </ShaperShell>
    );
  }
  if (query.isError || !workshop) {
    const forbidden = isApiError(query.error) && query.error.isForbidden;
    return (
      <ShaperShell organization={organization} title={title}>
        {forbidden ? <NoAccess /> : <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      </ShaperShell>
    );
  }
  return (
    <ShaperShell workshop={workshop} organization={organization} title={title}>
      {children(workshop, organization)}
    </ShaperShell>
  );
}

/** Shown on shaper pages when the account has no shaper specialty and no workshop membership (BR-04 wording). */
export function NoShaperState() {
  return (
    <div className="gv-ac-empty gv-sc-empty">
      <h3>Кабинет шейпера ещё не подключён</h3>
      <p>
        Мастерская, модели досок и статистика появятся после подключения направления «Шейпер». Это делается в разделе
        «Мои направления» — без новой регистрации, в том же аккаунте.
      </p>
      <ButtonLink href={routes.account.specialties} variant="primary" iconRight="arrow">
        Мои направления
      </ButtonLink>
    </div>
  );
}

/** Pages that need an existing workshop (boards, stats) point to the registration form. */
export function NeedWorkshopState({ organization }: { organization?: string | null }) {
  return (
    <div className="gv-ac-empty gv-sc-empty">
      <h3>Сначала зарегистрируйте мастерскую</h3>
      <p>Модели досок, артикулы и статистика привязаны к мастерской. Заполните её профиль — это займёт пару минут.</p>
      <ButtonLink href={shaperRoutes.workshop(organization)} variant="primary" iconRight="arrow">
        Зарегистрироваться как шейпер
      </ButtonLink>
    </div>
  );
}
