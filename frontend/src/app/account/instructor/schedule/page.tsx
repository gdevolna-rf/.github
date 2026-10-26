import type { Metadata } from "next";
import { InstructorSchedule } from "@/components/instructor-cabinet/InstructorSections";

export const metadata: Metadata = { title: "Расписание" };

export default function Page() {
  return <InstructorSchedule />;
}
