/**
 * School team helpers (ATX-35): one real person = one entry, even if the API (or a future change) lists a person
 * twice (owner who also teaches, membership in several roles). The highest role wins; a published instructor
 * profile found on any of the duplicates is kept so the card links to /instructors/{handle}.
 */
import type { SchoolTeamMember } from "@/lib/api/learning";
import { MEMBERSHIP_ROLE_LABELS } from "@/lib/labels";
import type { MembershipRole } from "@/lib/api/types";

const ROLE_ORDER: Record<string, number> = { owner: 0, manager: 1, instructor: 2, staff: 3 };

export interface TeamEntry {
  accountId: string;
  name: string;
  member: SchoolTeamMember;
  roles: string[];
  instructorHandle: string | null;
}

export function dedupeTeam(team: SchoolTeamMember[] | null | undefined): TeamEntry[] {
  const byId = new Map<string, TeamEntry>();
  for (const m of team ?? []) {
    const id = m?.account?.id;
    if (!id || m.account.is_deleted) continue;
    const existing = byId.get(id);
    if (!existing) {
      byId.set(id, {
        accountId: id,
        name: m.account.display_name || "Участник команды",
        member: m,
        roles: [m.role],
        instructorHandle: m.instructor_profile?.handle ?? null,
      });
      continue;
    }
    if (!existing.roles.includes(m.role)) existing.roles.push(m.role);
    if (!existing.instructorHandle && m.instructor_profile?.handle) existing.instructorHandle = m.instructor_profile.handle;
    if ((ROLE_ORDER[m.role] ?? 9) < (ROLE_ORDER[existing.member.role] ?? 9)) existing.member = m;
  }
  const out = Array.from(byId.values());
  out.forEach((e) => e.roles.sort((a, b) => (ROLE_ORDER[a] ?? 9) - (ROLE_ORDER[b] ?? 9)));
  return out.sort((a, b) => (ROLE_ORDER[a.roles[0]] ?? 9) - (ROLE_ORDER[b.roles[0]] ?? 9));
}

/** «Владелец · инструктор» — custom title from the school first, else role labels. */
export function teamRoleLabel(entry: TeamEntry): string {
  const labels = entry.roles.map((r) => MEMBERSHIP_ROLE_LABELS[r as MembershipRole] ?? "Сотрудник");
  const title = entry.member.title?.trim();
  if (title && !labels.includes(title)) return title;
  return labels.map((l, i) => (i === 0 ? l : l.toLowerCase())).join(" · ");
}
