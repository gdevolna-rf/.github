import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GUEST_403, json, mockApi, RAW_ME, renderWithProviders } from "@/test/utils";
import { navigation } from "@/test/navigation";
import { RequireAuth } from "./RequireAuth";

describe("RequireAuth", () => {
  it("redirects guests to /login?next=<current url>", async () => {
    navigation.set({ pathname: "/account/bookings", search: "box=provider" });
    mockApi({ "GET /api/v1/me": GUEST_403 });
    renderWithProviders(
      <RequireAuth>
        <p>Секретный кабинет</p>
      </RequireAuth>,
    );
    await waitFor(() => expect(navigation.router.replace).toHaveBeenCalledWith("/login?next=%2Faccount%2Fbookings%3Fbox%3Dprovider"));
    expect(screen.queryByText("Секретный кабинет")).not.toBeInTheDocument();
  });

  it("treats 401 the same as 403 (guest)", async () => {
    navigation.set({ pathname: "/account" });
    mockApi({ "GET /api/v1/me": () => json({ error: { code: "not_authenticated", message: "Требуется вход в аккаунт." } }, 401) });
    renderWithProviders(<RequireAuth>ok</RequireAuth>);
    await waitFor(() => expect(navigation.router.replace).toHaveBeenCalledWith("/login?next=%2Faccount"));
  });

  it("renders children (render-prop gets `me`) for logged-in users", async () => {
    mockApi({ "GET /api/v1/me": () => json(RAW_ME) });
    renderWithProviders(<RequireAuth>{(me) => <p>Привет, {me.firstName}</p>}</RequireAuth>);
    expect(await screen.findByText("Привет, Иван")).toBeInTheDocument();
    expect(navigation.router.replace).not.toHaveBeenCalled();
  });

  it("shows NoAccess when a server role or specialty is missing", async () => {
    mockApi({ "GET /api/v1/me": () => json(RAW_ME) });
    const { unmount } = renderWithProviders(<RequireAuth staff="moderator">модерация</RequireAuth>);
    expect(await screen.findByRole("heading", { name: "Нет доступа" })).toBeInTheDocument();
    unmount();
    renderWithProviders(<RequireAuth specialty="rental">прокат</RequireAuth>);
    expect(await screen.findByRole("heading", { name: "Направление «Прокат» не подключено" })).toBeInTheDocument();
  });

  it("offers a retry when /me cannot be loaded (network)", async () => {
    mockApi({
      "GET /api/v1/me": () => {
        throw new TypeError("Failed to fetch");
      },
    });
    renderWithProviders(<RequireAuth>ok</RequireAuth>);
    expect(await screen.findByRole("heading", { name: "Не удалось проверить вход" }, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Повторить" })).toBeInTheDocument();
    expect(navigation.router.replace).not.toHaveBeenCalled();
  });
});
