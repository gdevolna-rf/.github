"use client";
/** ACC-09: «Профиль» и «Настройки» — соседние вкладки (каждая — отдельный URL). */
import { usePathname } from "next/navigation";
import { routes } from "@/lib/routes";
import { NavTabs } from "@/components/ui/Tabs";

export function ProfileSettingsTabs() {
  const pathname = usePathname() || routes.account.profile;
  return (
    <NavTabs
      ariaLabel="Профиль и настройки"
      current={pathname}
      className="acc-top-tabs"
      items={[
        { href: routes.account.profile, label: "Профиль" },
        { href: routes.account.settings, label: "Настройки" },
      ]}
    />
  );
}
