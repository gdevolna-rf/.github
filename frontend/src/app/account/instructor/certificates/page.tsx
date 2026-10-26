import type { Metadata } from "next";
import { InstructorCertificates } from "@/components/instructor-cabinet/InstructorSections";

export const metadata: Metadata = { title: "Сертификаты" };

export default function Page() {
  return <InstructorCertificates />;
}
