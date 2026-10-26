import type { Metadata } from "next";
import { InstructorStudents } from "@/components/instructor-cabinet/InstructorSections";

export const metadata: Metadata = { title: "Ученики" };

export default function Page() {
  return <InstructorStudents />;
}
