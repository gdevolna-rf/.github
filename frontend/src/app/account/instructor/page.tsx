import type { Metadata } from "next";
import { InstructorOverview } from "@/components/instructor-cabinet/InstructorOverview";

export const metadata: Metadata = { title: "Инструктор" };

export default function Page() {
  return <InstructorOverview />;
}
