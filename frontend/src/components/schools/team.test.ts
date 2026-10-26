import { describe, expect, it } from "vitest";
import type { SchoolTeamMember } from "@/lib/api/learning";
import { dedupeTeam, teamRoleLabel } from "./team";

const acc = (id: string, name: string, extra: Partial<SchoolTeamMember["account"]> = {}) => ({
  id,
  handle: name.toLowerCase(),
  display_name: name,
  avatar: null,
  is_deleted: false,
  ...extra,
});

describe("dedupeTeam (ATX-35)", () => {
  it("keeps one entry per account and merges roles, the highest role first", () => {
    const team: SchoolTeamMember[] = [
      { account: acc("a1", "Алексей"), role: "instructor", title: "", instructor_profile: { id: "p1", handle: "aleksey" } },
      { account: acc("o1", "Ольга"), role: "owner", title: "", instructor_profile: null },
      { account: acc("a1", "Алексей"), role: "manager", title: "", instructor_profile: null },
    ];
    const out = dedupeTeam(team);
    expect(out).toHaveLength(2);
    expect(out[0].accountId).toBe("o1");
    const aleksey = out.find((e) => e.accountId === "a1")!;
    expect(aleksey.roles).toEqual(["manager", "instructor"]);
    expect(aleksey.instructorHandle).toBe("aleksey");
    expect(teamRoleLabel(aleksey)).toBe("Менеджер · инструктор");
  });

  it("drops deleted accounts and tolerates empty input", () => {
    expect(dedupeTeam(undefined)).toEqual([]);
    const out = dedupeTeam([{ account: acc("d1", "X", { is_deleted: true }), role: "staff", title: "", instructor_profile: null }]);
    expect(out).toEqual([]);
  });

  it("prefers the school's own title", () => {
    const [entry] = dedupeTeam([{ account: acc("m1", "Павел"), role: "manager", title: "Менеджер школы", instructor_profile: null }]);
    expect(teamRoleLabel(entry)).toBe("Менеджер школы");
  });
});
