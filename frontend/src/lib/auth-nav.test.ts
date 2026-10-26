import { describe, expect, it } from "vitest";
import { buildAccountNav, isNavItemActive } from "./account-nav";
import { normalizeMe, routeForNextStep, safeNext, loginHref } from "./api/auth";
import { normalizeFavoriteIds } from "./api/favorites";
import { RAW_ME } from "@/test/utils";

const counters = { unread_messages: 2, unread_notifications: 1, new_inquiries: 1, pending_bookings: 0 };

describe("normalizeMe", () => {
  it("maps the backend /me payload", () => {
    const me = normalizeMe(RAW_ME);
    expect(me).toMatchObject({
      id: RAW_ME.id,
      email: RAW_ME.email,
      emailVerified: true,
      handle: "ivan-petrov",
      displayName: "Иван Петров",
      specialties: ["surfer", "instructor", "shaper"], // disabled rental excluded
      primarySpecialty: "instructor",
      isModerator: false,
      deletion: null,
      instructorProfile: { id: "ip-1", status: "published" },
    });
    expect(me.organizations[0]).toMatchObject({ id: "org-1", kind: "workshop", role: "owner", membershipId: "m-1", status: "published" });
    expect(me.region?.name).toBe("Камчатский край");
  });
});

describe("account navigation (ACC-02, ACC-09)", () => {
  it("has the general screens with Профиль next to Настройки and pro sections per specialty/org", () => {
    const groups = buildAccountNav(normalizeMe(RAW_ME), counters);
    const general = groups[0].items.map((i) => i.label);
    expect(general).toEqual(["Обзор", "Профиль", "Настройки", "Обращения", "Мои бронирования", "Избранное", "Уведомления", "Мои направления"]);
    expect(groups[0].items.find((i) => i.label === "Обращения")?.badge).toBe(3);
    const pro = groups[1].items.map((i) => i.label);
    expect(pro).toEqual(expect.arrayContaining(["Сёрфер · дневник", "Инструктор", "Шейпер · мастерская", "Kamchatka Boards"]));
    expect(pro).not.toContain("Прокат");
    expect(groups.find((g) => g.id === "staff")).toBeUndefined();
  });
  it("adds Модерация for staff only", () => {
    const groups = buildAccountNav(normalizeMe({ ...RAW_ME, staff_roles: ["moderator"] }), counters);
    expect(groups.at(-1)?.items[0]).toMatchObject({ label: "Модерация", href: "/moderation" });
  });
  it("matches active items", () => {
    expect(isNavItemActive({ href: "/account", label: "", icon: "home", exact: true }, "/account/profile")).toBe(false);
    expect(isNavItemActive({ href: "/account/inquiries", label: "", icon: "chat" }, "/account/inquiries/42")).toBe(true);
  });
});

describe("auth helpers", () => {
  it("accepts only same-site next targets", () => {
    expect(safeNext("/account/bookings?box=provider")).toBe("/account/bookings?box=provider");
    expect(safeNext("https://evil.example")).toBe("/account");
    expect(safeNext("//evil.example")).toBe("/account");
    expect(safeNext("/login?next=/x")).toBe("/account");
    expect(loginHref("/account/favorites")).toBe("/login?next=%2Faccount%2Ffavorites");
    expect(routeForNextStep("create_school", "/account")).toBe("/account/orgs?create=school");
    expect(routeForNextStep(undefined, "/spots")).toBe("/spots");
  });
  it("normalises favourite ids in every supported shape", () => {
    expect([...normalizeFavoriteIds({ spot: ["a"], instructor: [1] })]).toEqual(["spot:a", "instructor:1"]);
    expect([...normalizeFavoriteIds([{ target_type: "spot", target_id: "b" }])]).toEqual(["spot:b"]);
    expect([...normalizeFavoriteIds(["organization:c"])]).toEqual(["organization:c"]);
  });
});
