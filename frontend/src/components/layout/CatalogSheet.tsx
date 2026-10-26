"use client";
/** «Каталог» sheet of the mobile tab bar: every section of the site (NAV-01/03). */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { cx } from "@/lib/cx";
import { isActivePath, MAIN_NAV, routes } from "@/lib/routes";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";

export function CatalogSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname() || "/";
  const first = useRef(pathname);
  // Close when navigation happens (link click inside the sheet)
  useEffect(() => {
    if (pathname !== first.current) {
      first.current = pathname;
      onClose();
    }
  }, [pathname, onClose]);

  return (
    <Modal open={open} onClose={onClose} title="Каталог" description="Все разделы «Гдеволны»" size="sheet">
      <ul className="gv-catalog-list">
        {MAIN_NAV.map((item) => {
          const active = isActivePath(pathname, item.match);
          return (
            <li key={item.href}>
              <Link href={item.href} className={cx("gv-catalog-item", active && "active")} aria-current={active ? "page" : undefined} onClick={onClose}>
                <span className="gv-catalog-icon" aria-hidden="true">
                  <Icon name={item.icon} size={20} />
                </span>
                <span className="gv-catalog-text">
                  <b>{item.label}</b>
                  <small>{item.description}</small>
                </span>
                <Icon name="chevron-right" size={16} className="gv-catalog-arrow" />
              </Link>
            </li>
          );
        })}
        <li>
          <Link href={routes.search()} className="gv-catalog-item" onClick={onClose}>
            <span className="gv-catalog-icon" aria-hidden="true">
              <Icon name="search" size={20} />
            </span>
            <span className="gv-catalog-text">
              <b>Поиск по сайту</b>
              <small>Споты, инструкторы, школы, доски и снаряжение</small>
            </span>
            <Icon name="chevron-right" size={16} className="gv-catalog-arrow" />
          </Link>
        </li>
      </ul>
    </Modal>
  );
}
