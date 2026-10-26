import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { UiKitShowcase } from "@/components/dev/UiKitShowcase";

export const metadata: Metadata = { title: "UI kit", robots: { index: false, follow: false } };

/** Development-only living style guide. Set SHOW_UI_KIT=1 to expose it in a production build (staging). */
export default function UiKitPage() {
  if (process.env.NODE_ENV === "production" && process.env.SHOW_UI_KIT !== "1") notFound();
  return <UiKitShowcase />;
}
