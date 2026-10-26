"use client";
/**
 * Personal account layout (prototype `.gv-account`, CABINET_SCREENS §4): hero (avatar, name, handle·region,
 * specialty tags) + sidebar navigation (horizontal scrolling strip on phones, active tab kept in view) +
 * workspace. Every pane is a real URL (CABINET_NOTES A10). Wrapped in RequireAuth.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useRef, type ReactNode } from "react";
import { authApi, type Me } from "@/lib/api/auth";
import { buildAccountNav, isNavItemActive } from "@/lib/account-nav";
import { useCounters } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { SPECIALTY_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { Avatar } from "@/components/ui/Avatar";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Icon, type IconName } from "@/components/ui/Icon";
import { LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";

const SPECIALTY_ICON: Record<string, IconName> = { surfer: "waves", instructor: "clover", shaper: "ruler", rental: "board" };

function AccountNav({ me }: { me: Me }) {
  const pathname = usePathname() || routes.account.root;
  const counters = useCounters();
  const groups = buildAccountNav(me, counters);
  const navRef = useRef<HTMLElement>(null);

  // Phones: keep the active tab visible in the horizontal strip (CABINET_NOTES F5)
  useEffect(() => {
    const active = navRef.current?.querySelector<HTMLElement>("a.active");
    if (active && navRef.current && navRef.current.scrollWidth > navRef.current.clientWidth) {
      active.scrollIntoView?.({ block: "nearest", inline: "center" });
    }
  }, [pathname]);

  return (
    <nav ref={navRef} className="gv-ac-nav" aria-label="Навигация личного кабинета">
      {groups.map((g) => (
        <div key={g.id} role="group" aria-label={g.label} style={{ display: "contents" }}>
          <div className="gv-ac-nav-label" aria-hidden="true">
            {g.label}
          </div>
          {g.items.map((item) => {
            const active = isNavItemActive(item, pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cx(active && "active", item.sub && "gv-ac-nav-sub")}
                aria-current={active ? "page" : undefined}
                aria-label={item.badge ? `${item.label}: ${item.badge}` : undefined}
              >
                <span className="gv-ac-nav-icon" aria-hidden="true">
                  <Icon name={item.icon} size={17} />
                </span>
                <span>{item.label}</span>
                {item.badge ? (
                  <span className={cx("gv-ac-nav-count", item.alert && "is-alert")} aria-hidden="true">
                    {item.badge > 99 ? "99+" : item.badge}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function VerifyEmailBanner({ me }: { me: Me }) {
  const toast = useToast();
  if (me.emailVerified) return null;
  return (
    <div className="gv-verify-banner" role="status">
      <Icon name="mail" size={20} />
      <div className="gv-state-body">
        <p>
          <b>Подтвердите электронную почту.</b> Мы отправили ссылку на {me.email || "ваш адрес"} — без подтверждения
          часть действий (заявки, отзывы) будет недоступна.
        </p>
      </div>
      <Button
        variant="soft"
        onClick={() =>
          authApi
            .resendVerification()
            .then(() => toast.success("Письмо отправлено ещё раз"))
            .catch((err) => toast.error(err))
        }
      >
        Отправить ещё раз
      </Button>
    </div>
  );
}

function Shell({ me, children }: { me: Me; children: ReactNode }) {
  const place = [me.handle ? `@${me.handle}` : null, me.region?.name ?? "Регион не указан"].filter(Boolean).join(" · ");
  return (
    <div className="gv-account">
      <section className="gv-ac-hero" aria-label="Ваш аккаунт">
        {/* ACC-07 / UX-10: the photo is not editable here — only in «Профиль» */}
        <Avatar media={me.avatar} name={me.displayName} size={66} />
        <div className="gv-ac-hero-meta">
          <div className="gv-ac-kicker">Личный кабинет ГДеволна</div>
          <h1>{me.displayName}</h1>
          <p>{place}</p>
          {me.specialties.length > 0 && (
            <div className="gv-ac-tags" aria-label="Подключённые направления">
              {me.specialties.map((s) => (
                <span key={s} className="gv-ac-tag">
                  <Icon name={SPECIALTY_ICON[s] ?? "sparkle"} size={13} />
                  {SPECIALTY_LABELS[s] ?? s}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="gv-ac-hero-act">
          <ButtonLink href={routes.account.specialties} variant="soft" icon="plus">
            Направление
          </ButtonLink>
          <ButtonLink href={routes.account.profile} variant="soft">
            Мой профиль
          </ButtonLink>
        </div>
      </section>
      <div className="gv-ac-grid">
        <AccountNav me={me} />
        <div className="gv-ac-workspace">
          <VerifyEmailBanner me={me} />
          {children}
        </div>
      </div>
    </div>
  );
}

export function AccountShell({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<LoadingState label="Открываем кабинет…" />}>
      <RequireAuth fallback={<div className="gv-account"><LoadingState label="Открываем кабинет…" /></div>}>
        {(me) => <Shell me={me}>{children}</Shell>}
      </RequireAuth>
    </Suspense>
  );
}

/** Placeholder pane for sections that page engineers will implement. */
export function AccountPlaceholder({ title, description, items }: { title: string; description: string; items?: string[] }) {
  return (
    <section className="gv-ac-panel gv-account-placeholder" aria-labelledby="pane-title">
      <h2 id="pane-title">{title}</h2>
      <p className="gv-ac-desc">{description}</p>
      {items && items.length > 0 && (
        <ul className="gv-ac-list">
          {items.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
      )}
      <div className="gv-ac-empty">Раздел скоро появится — мы уже подключаем его к серверу.</div>
    </section>
  );
}
