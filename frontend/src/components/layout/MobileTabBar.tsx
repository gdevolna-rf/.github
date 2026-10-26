"use client";
/**
 * Bottom tab bar for phones ≤810px (NAV-03, UX-03): Главная · Каталог · Избранное · Сообщения · Кабинет.
 * «Каталог» opens a sheet with every section. Badges come from server counters (MSG-06/07) and favourite ids.
 * Fixed to the bottom with the iOS safe area; the page reserves the same space (ATX-22, see app.css).
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { loginHref } from "@/lib/api/auth";
import { useCounters, useMe } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { useFavoritesCount } from "@/lib/favorites/hooks";
import { CATALOG_PREFIXES, isActivePath, routes } from "@/lib/routes";
import { Avatar } from "@/components/ui/Avatar";
import { CountBadge } from "@/components/ui/Badge";
import { Icon, type IconName } from "@/components/ui/Icon";
import { CatalogSheet } from "./CatalogSheet";

function TabContent({ icon, label, badge, visual }: { icon: IconName; label: string; badge?: number; visual?: ReactNode }) {
  return (
    <>
      <span className="gv-tab-icon">
        {visual ?? <Icon name={icon} size={22} />}
        <CountBadge value={badge} />
      </span>
      <span className="gv-tab-label">{label}</span>
    </>
  );
}

const named = (label: string, badge?: number) => (badge ? `${label}: ${badge}` : label);

export function MobileTabBar() {
  const pathname = usePathname() || "/";
  const { me } = useMe();
  const counters = useCounters();
  const favorites = useFavoritesCount();
  const [catalogOpen, setCatalogOpen] = useState(false);

  const inFavorites = pathname.startsWith(routes.account.favorites);
  const inMessages = pathname.startsWith(routes.account.inquiries);
  const inAccount = pathname.startsWith("/account") && !inFavorites && !inMessages;
  const inCatalog = isActivePath(pathname, CATALOG_PREFIXES);
  const messagesBadge = me ? counters.unread_messages : 0;
  const accountBadge = me ? counters.unread_notifications : 0;

  return (
    <>
      <nav className="gv-tabbar" aria-label="Основная навигация">
        <Link href="/" className={cx("gv-tab", pathname === "/" && "active")} aria-current={pathname === "/" ? "page" : undefined}>
          <TabContent icon="home" label="Главная" />
        </Link>
        <button
          type="button"
          className={cx("gv-tab", (inCatalog || catalogOpen) && "active")}
          aria-haspopup="dialog"
          aria-expanded={catalogOpen}
          onClick={() => setCatalogOpen(true)}
        >
          <TabContent icon="grid" label="Каталог" />
        </button>
        <Link
          href={me ? routes.account.favorites : loginHref(routes.account.favorites)}
          className={cx("gv-tab", inFavorites && "active")}
          aria-current={inFavorites ? "page" : undefined}
          aria-label={named("Избранное", favorites)}
        >
          <TabContent icon="heart" label="Избранное" badge={favorites} />
        </Link>
        <Link
          href={me ? routes.account.inquiries : loginHref(routes.account.inquiries)}
          className={cx("gv-tab", inMessages && "active")}
          aria-current={inMessages ? "page" : undefined}
          aria-label={named("Сообщения", messagesBadge)}
        >
          <TabContent icon="chat" label="Сообщения" badge={messagesBadge} />
        </Link>
        <Link
          href={me ? routes.account.root : loginHref(routes.account.root)}
          className={cx("gv-tab", inAccount && "active")}
          aria-current={inAccount ? "page" : undefined}
          aria-label={named("Кабинет", accountBadge)}
        >
          <TabContent
            icon="user"
            label="Кабинет"
            badge={accountBadge}
            visual={me ? <Avatar media={me.avatar} name={me.displayName} size={24} /> : undefined}
          />
        </Link>
      </nav>
      <CatalogSheet open={catalogOpen} onClose={() => setCatalogOpen(false)} />
    </>
  );
}
