import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { resetCsrfForTests } from "@/lib/api/client";
import { navigation } from "@/test/navigation";
import { clearCookies, CSRF_OK, json, mockApi, RAW_ME, renderWithProviders } from "@/test/utils";
import { RentalCabinet } from "./RentalCabinet";
import { ITEM, ORG } from "./test-fixtures";

const rentalMe = {
  ...RAW_ME,
  specialties: [
    { code: "surfer", status: "active", is_primary: false },
    { code: "rental", status: "active", is_primary: true },
  ],
  organizations: [{ id: ORG, slug: "volna", name: "Прокат «Волна рядом»", kind: "rental", status: "published", role: "owner", membership_id: "m1" }],
};

const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

const AVAILABILITY = {
  from: "2026-10-21T00:00:00+03:00",
  to: "2026-10-22T00:00:00+03:00",
  summary: { total: 8, free_now: 3, booked_now: 1, maintenance: 1, free_in_range: 2, booked_in_range: 2 },
  items: [
    {
      id: "i1",
      title: "Лонгборд 9′2″",
      kind: "board",
      status: "available",
      size: "9′2″",
      is_published: true,
      is_booked_now: true,
      is_free_in_range: false,
      booked: [{ booking_id: "b1", starts_at: "2026-10-21T06:00:00+03:00", ends_at: "2026-10-21T12:00:00+03:00", status: "confirmed" }],
    },
  ],
};

function routes(overrides: Record<string, () => Response> = {}) {
  return mockApi({
    "GET /api/v1/auth/csrf": CSRF_OK,
    "GET /api/v1/me": () => json(rentalMe),
    "GET /api/v1/me/inventory": () => json(page([ITEM])),
    "GET /api/v1/me/inventory/availability": () => json(AVAILABILITY),
    "GET /api/v1/regions": () => json([{ id: 1, slug: "kamchatskiy-kray", name: "Камчатский край", timezone: "Asia/Kamchatka" }]),
    ...overrides,
  });
}

describe("RentalCabinet", () => {
  beforeEach(() => {
    clearCookies();
    resetCsrfForTests();
    navigation.set({ pathname: "/account/rental", search: "" });
  });

  it("opens the rental organization by default and shows the RENT-04 row and items", async () => {
    const api = routes();
    renderWithProviders(<RentalCabinet />);
    expect(await screen.findByRole("heading", { name: "Прокат · снаряжение" })).toBeInTheDocument();
    const strip = await screen.findByLabelText("Доступность снаряжения");
    await waitFor(() => expect(within(strip).getByText("Свободных бордов").nextSibling).toHaveTextContent("3"));
    expect(within(strip).getByText("Забронировано").nextSibling).toHaveTextContent("1");
    const heading = await screen.findByRole("heading", { name: ITEM.title });
    expect(heading).toHaveAttribute("title", ITEM.title);
    const card = heading.closest("article")!;
    expect(within(card).getByText("Доступен")).toBeInTheDocument();
    expect(within(card).getByText(/3 фото/)).toBeInTheDocument();
    expect(within(card).getByText(/1\s700\s₽/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Бронирования аренды/ })).toHaveAttribute(
      "href",
      `/account/bookings?box=provider&kind=rental&organization=${ORG}`,
    );
    const call = api.calls("GET /api/v1/me/inventory").find((c) => c.url.includes("organization="));
    expect(call?.url).toContain(`organization=${ORG}`);
    expect(api.calls("GET /api/v1/me/inventory/availability")[0].url).toContain("kind=board");
  });

  it("switches the owner through the URL", async () => {
    routes();
    renderWithProviders(<RentalCabinet />);
    const select = await screen.findByLabelText("Чей инвентарь");
    await userEvent.selectOptions(select, "personal");
    expect(navigation.router.replace).toHaveBeenCalledWith("/account/rental?owner=personal", { scroll: false });
  });

  it("shows the empty state with a create action for an empty personal inventory", async () => {
    navigation.set({ search: "owner=personal" });
    routes({ "GET /api/v1/me/inventory": () => json(page([])) });
    renderWithProviders(<RentalCabinet />);
    expect(await screen.findByText("Снаряжения пока нет")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Добавить снаряжение/ }).length).toBeGreaterThan(0);
  });

  it("shows an error with retry and recovers", async () => {
    let fail = true;
    routes({
      "GET /api/v1/me/inventory": () =>
        fail ? json({ error: { code: "server_error", message: "Внутренняя ошибка сервера.", fields: {} } }, 500) : json(page([ITEM])),
    });
    renderWithProviders(<RentalCabinet />);
    const retry = await screen.findByRole("button", { name: "Повторить" });
    fail = false;
    await userEvent.click(retry);
    expect(await screen.findByRole("heading", { name: ITEM.title })).toBeInTheDocument();
  });

  it("shows NoAccess for an organization the user is not a member of", async () => {
    navigation.set({ search: "organization=foreign" });
    routes({
      "GET /api/v1/me/inventory": () => json({ error: { code: "not_org_member", message: "Вы не состоите в этой организации.", fields: {} } }, 403),
      "GET /api/v1/me/inventory/availability": () => json({ error: { code: "not_org_member", message: "Нет", fields: {} } }, 403),
    });
    renderWithProviders(<RentalCabinet />);
    expect(await screen.findByText("Нет доступа")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Добавить снаряжение/ })).not.toBeInTheDocument();
  });

  it("explains the section without the rental specialty or an organization", async () => {
    routes({ "GET /api/v1/me": () => json({ ...RAW_ME, specialties: [{ code: "surfer", status: "active" }], organizations: [] }) });
    renderWithProviders(<RentalCabinet />);
    expect(await screen.findByRole("link", { name: /Мои направления/ })).toHaveAttribute("href", "/account/specialties");
  });

  it("renders the interval timeline with booking links", async () => {
    navigation.set({ search: "view=availability" });
    routes();
    renderWithProviders(<RentalCabinet />);
    const list = await screen.findByRole("list", { name: /Брони «Лонгборд 9′2″» в периоде/ });
    expect(within(list).getByText("Подтверждено")).toBeInTheDocument();
    expect(within(list).getByRole("link", { name: "Открыть бронь" })).toHaveAttribute("href", "/account/bookings/b1");
    expect(screen.getByRole("img", { name: "Занято 25% периода" })).toBeInTheDocument();
    expect(screen.getByText("Сейчас забронирован")).toBeInTheDocument();
  });

  it("changes the status and explains a conflict with active bookings", async () => {
    const api = routes({
      "POST /api/v1/me/inventory/i1/status": () =>
        json({ error: { code: "item_has_active_bookings", message: "У экземпляра есть подтверждённые брони.", fields: {} } }, 409),
    });
    renderWithProviders(<RentalCabinet />);
    await userEvent.click(await screen.findByRole("button", { name: /Сменить статус/ }));
    const dialog = await screen.findByRole("dialog", { name: "Статус экземпляра" });
    await userEvent.click(within(dialog).getByRole("radio", { name: /На обслуживании/ }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Сохранить" }));
    expect(await within(dialog).findByText(/Сначала отмените или завершите их/)).toBeInTheDocument();
    expect(api.calls("POST /api/v1/me/inventory/i1/status")[0].body).toEqual({ status: "maintenance" });
  });

  it("delete of an item with history reports «списан»", async () => {
    routes({ "DELETE /api/v1/me/inventory/i1": () => json({ result: "retired" }) });
    renderWithProviders(<RentalCabinet />);
    await userEvent.click(await screen.findByRole("button", { name: /Удалить «Лонгборд/ }));
    const dialog = await screen.findByRole("dialog", { name: "Удалить экземпляр?" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Удалить" }));
    expect(await screen.findByText(/списан и скрыт из каталога/)).toBeInTheDocument();
  });
});
