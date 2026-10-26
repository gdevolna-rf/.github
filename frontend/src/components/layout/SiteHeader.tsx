"use client";
/**
 * Sticky top bar (prototype `.topbar`, DESIGN_SYSTEM §3.1): logo · main nav (NAV-01) · tools.
 * Desktop tools: search, favourites (count), messages (unread = server counters, MSG-06/07), account.
 * Phones (≤810px, UX-03): a light bar — logo + search only; the rest lives in the bottom tab bar.
 * Account: «Войти» for guests; avatar + «Кабинет» for users — a link to /account, never an upload (ACC-07/UX-10).
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { loginHref } from "@/lib/api/auth";
import { useCounters, useMe } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { useFavoritesCount } from "@/lib/favorites/hooks";
import { isActivePath, MAIN_NAV, routes } from "@/lib/routes";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";
import { IconButton, IconLink } from "@/components/ui/IconButton";
import { SearchDialog } from "./SearchDialog";

const AUTH_PATHS = ["/login", "/register", "/reset-password", "/verify-email"];

export function AccountButton({ className }: { className?: string }) {
  const { me, isLoading } = useMe();
  const pathname = usePathname();
  if (isLoading) {
    return (
      <span className={cx("line-btn account-btn is-loading", className)} aria-hidden="true">
        <Icon name="user" size={18} />
        <span>Войти</span>
      </span>
    );
  }
  if (!me) {
    const next = AUTH_PATHS.some((p) => pathname.startsWith(p)) ? undefined : pathname;
    return (
      <Link href={loginHref(next)} className={cx("line-btn account-btn", className)}>
        <Icon name="user" size={18} />
        <span>Войти</span>
      </Link>
    );
  }
  return (
    <Link
      href={routes.account.root}
      className={cx("line-btn account-btn has-avatar", pathname.startsWith("/account") && "active", className)}
      aria-label={`Личный кабинет: ${me.displayName}`}
      title="Личный кабинет"
    >
      <Avatar media={me.avatar} name={me.displayName} size={26} />
      <span>Кабинет</span>
    </Link>
  );
}

export function SiteHeader() {
  const pathname = usePathname() || "/";
  const { me } = useMe();
  const counters = useCounters();
  const favorites = useFavoritesCount();
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <header className="topbar">
      <div className="wrap header">
        <Link href="/" className="logo" title="На главную" aria-label="Гдеволна.рф — на главную">
          <img src="/brand/logo.png" alt="Гдеволна.рф" width={108} height={61} />
        </Link>
        <nav className="mainnav" id="nav" aria-label="Разделы сайта">
          {MAIN_NAV.map((item) => {
            const active = isActivePath(pathname, item.match);
            return (
              <Link key={item.href} href={item.href} className={cx("navlink", active && "active")} aria-current={active ? "page" : undefined}>
                <span className="nav-long">{item.label}</span>
                <span className="nav-short" aria-hidden="true">
                  {item.short}
                </span>
              </Link>
            );
          })}
        </nav>
        <div className="navtools">
          <IconButton icon="search" label="Поиск" onClick={() => setSearchOpen(true)} aria-haspopup="dialog" />
          <IconLink
            href={me ? routes.account.favorites : loginHref(routes.account.favorites)}
            icon="heart"
            label="Избранное"
            badge={favorites}
            className="hide-on-phone"
          />
          <IconLink
            href={me ? routes.account.inquiries : loginHref(routes.account.inquiries)}
            icon="chat"
            label="Сообщения"
            badge={counters.unread_messages}
            className="hide-on-phone"
          />
          <AccountButton className="hide-on-phone" />
        </div>
      </div>
      <SearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />
    </header>
  );
}
