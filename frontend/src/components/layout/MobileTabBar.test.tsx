import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { GUEST_403, json, mockApi, RAW_ME, renderWithProviders } from "@/test/utils";
import { navigation } from "@/test/navigation";
import { MobileTabBar } from "./MobileTabBar";

describe("MobileTabBar (NAV-03)", () => {
  it("shows the five tabs with server counter badges for a logged-in user", async () => {
    navigation.set({ pathname: "/account/inquiries" });
    mockApi({
      "GET /api/v1/me": () => json(RAW_ME),
      "GET /api/v1/me/counters": () => json({ unread_messages: 3, unread_notifications: 2, new_inquiries: 1, pending_bookings: 0 }),
      "GET /api/v1/me/favorites/ids": () => json({ spot: ["a", "b"], instructor: ["c"] }),
    });
    renderWithProviders(<MobileTabBar />);
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    const messages = await within(nav).findByRole("link", { name: "Сообщения: 3" });
    expect(messages).toHaveAttribute("href", "/account/inquiries");
    expect(messages).toHaveAttribute("aria-current", "page");
    expect(within(messages).getByText("3")).toHaveClass("count");
    expect(await within(nav).findByRole("link", { name: "Избранное: 3" })).toHaveAttribute("href", "/account/favorites");
    expect(within(nav).getByRole("link", { name: "Кабинет: 2" })).toHaveAttribute("href", "/account");
    expect(within(nav).getByRole("link", { name: "Главная" })).toHaveAttribute("href", "/");
    expect(within(nav).getByRole("button", { name: "Каталог" })).toBeInTheDocument();
  });

  it("has no badges for guests and sends private tabs through login", async () => {
    mockApi({ "GET /api/v1/me": GUEST_403 });
    renderWithProviders(<MobileTabBar />);
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    const cabinet = await within(nav).findByRole("link", { name: "Кабинет" });
    expect(cabinet.getAttribute("href")).toMatch(/^\/login\?next=%2Faccount/);
    expect(within(nav).getByRole("link", { name: "Сообщения" })).toHaveAttribute("href", "/login?next=%2Faccount%2Finquiries");
    expect(nav.querySelectorAll(".count")).toHaveLength(0);
  });

  it("«Каталог» opens a sheet with every section", async () => {
    const user = userEvent.setup();
    mockApi({ "GET /api/v1/me": GUEST_403 });
    renderWithProviders(<MobileTabBar />);
    await user.click(screen.getByRole("button", { name: "Каталог" }));
    const sheet = await screen.findByRole("dialog", { name: "Каталог" });
    for (const name of ["Каталог сёрф-инструкторов", "Карта сёрф-спотов", "GG Surfer", "Аренда", "Шейперы", "О нас и клуб", "Сёрф-школы"]) {
      expect(within(sheet).getByRole("link", { name: new RegExp(name) })).toBeInTheDocument();
    }
  });
});
