import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ModerationShell } from "@/components/moderation/ModerationShell";

/** /moderation/* — staff only (BR-04, TRUST-06) + 2FA-verified session (11, DATA-09); never indexed. */
export const metadata: Metadata = {
  title: { default: "Модерация", template: "%s · Модерация · Гдеволна.рф" },
  robots: { index: false, follow: false },
};

export default function ModerationLayout({ children }: { children: ReactNode }) {
  return <ModerationShell>{children}</ModerationShell>;
}
