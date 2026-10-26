"use client";
import { use } from "react";
import { usePathname } from "next/navigation";
import { OrgShell } from "@/components/school-cabinet/OrgShell";
import {
  AnalyticsTab,
  EquipmentTab,
  InquiriesTab,
  OrgOverview,
  OrgProfileTab,
  ProgramsTab,
  ReviewsTab,
  ScheduleTab,
  StudentsTab,
  TeamTab,
} from "@/components/school-cabinet/OrgTabs";
import { NoAccess } from "@/components/ui";

/** /account/orgs/{id}/{tab} — кабинет школы (SCH-03). Менеджерские вкладки без прав → NoAccess (сервер проверяет сам). */
export default function Page({ params }: { params: Promise<{ id: string; tab?: string[] }> }) {
  const { id, tab } = use(params);
  const pathname = usePathname() ?? "";
  const section = tab?.[0] ?? "";
  return (
    <OrgShell id={id} pathname={pathname}>
      {(org, role) => {
        if (section === "") return <OrgOverview id={id} org={org} role={role} />;
        if (section === "team") return <TeamTab id={id} org={org} role={role} />;
        if (section === "reviews") return <ReviewsTab id={id} />;
        if (!org) return <NoAccess text="Раздел доступен владельцу и менеджерам организации." />;
        switch (section) {
          case "profile":
            return <OrgProfileTab id={id} org={org} />;
          case "programs":
            return <ProgramsTab id={id} />;
          case "schedule":
            return <ScheduleTab id={id} org={org} />;
          case "students":
            return <StudentsTab id={id} />;
          case "equipment":
            return <EquipmentTab id={id} />;
          case "inquiries":
            return <InquiriesTab id={id} />;
          case "analytics":
            return <AnalyticsTab id={id} org={org} />;
          default:
            return <NoAccess title="Раздел не найден" />;
        }
      }}
    </OrgShell>
  );
}
