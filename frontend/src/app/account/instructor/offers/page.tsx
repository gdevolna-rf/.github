import type { Metadata } from "next";
import { InstructorOffers } from "@/components/instructor-cabinet/InstructorOffers";

export const metadata: Metadata = { title: "Предложения" };

export default function Page() {
  return <InstructorOffers />;
}
