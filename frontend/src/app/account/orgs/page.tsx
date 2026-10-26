import type { Metadata } from "next";
import { OrgsPage } from "@/components/school-cabinet/OrgShell";

export const metadata: Metadata = { title: "Школы и организации" };

export default function Page() {
  return <OrgsPage />;
}
