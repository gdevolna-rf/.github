import type { Metadata } from "next";
import { StaffRoles } from "@/components/moderation/StaffRoles";

export const metadata: Metadata = { title: "Служебные роли" };

/** Admins only: grant / revoke moderator and organizer roles (BR-04). */
export default function ModerationStaffPage() {
  return <StaffRoles />;
}
