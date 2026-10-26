import type { Metadata } from "next";
import { AccountOverview } from "@/components/account/AccountOverview";

export const metadata: Metadata = { title: "Обзор" };

export default function AccountPage() {
  return <AccountOverview />;
}
