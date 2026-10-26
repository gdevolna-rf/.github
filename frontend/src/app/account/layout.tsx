import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AccountShell } from "@/components/layout/AccountShell";

/** /account/* — private, client-rendered panes inside one shell (RequireAuth + navigation). */
export const metadata: Metadata = {
  title: { default: "Личный кабинет", template: "%s · Личный кабинет · Гдеволна.рф" },
  robots: { index: false, follow: false },
};

export default function AccountLayout({ children }: { children: ReactNode }) {
  return <AccountShell>{children}</AccountShell>;
}
