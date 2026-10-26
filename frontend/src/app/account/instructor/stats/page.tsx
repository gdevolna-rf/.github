import type { Metadata } from "next";
import { InstructorStats } from "@/components/instructor-cabinet/InstructorSections";

export const metadata: Metadata = { title: "Статистика" };

export default function Page() {
  return <InstructorStats />;
}
