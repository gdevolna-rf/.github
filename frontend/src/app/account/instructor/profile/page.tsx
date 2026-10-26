import type { Metadata } from "next";
import { InstructorProfileEditor } from "@/components/instructor-cabinet/InstructorProfileEditor";

export const metadata: Metadata = { title: "Карточка инструктора" };

export default function Page() {
  return <InstructorProfileEditor />;
}
