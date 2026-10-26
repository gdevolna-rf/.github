import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { resetCsrfForTests } from "@/lib/api/client";
import { clearCookies, CSRF_OK, GUEST_403, json, mockApi, RAW_ME, renderWithProviders } from "@/test/utils";
import { HeartButton } from "./HeartButton";

beforeEach(() => {
  resetCsrfForTests();
  clearCookies();
});

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

describe("HeartButton (MSG-11)", () => {
  it("turns on optimistically and keeps the state when the server agrees", async () => {
    const user = userEvent.setup();
    const gate = deferred<Response>();
    const api = mockApi({
      "GET /api/v1/me": () => json(RAW_ME),
      "GET /api/v1/me/favorites/ids": () => json({ spot: [], instructor: [] }),
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/favorites": () => gate.promise,
    });
    renderWithProviders(<HeartButton type="spot" id="s1" name="Халактырский пляж" />);
    const btn = await screen.findByRole("button", { name: "В избранное: Халактырский пляж" });
    await waitFor(() => expect(api.calls("GET /api/v1/me/favorites/ids")).toHaveLength(1));
    expect(btn).toHaveAttribute("aria-pressed", "false");

    await user.click(btn);
    // optimistic: pressed before the server answered
    expect(btn).toHaveAttribute("aria-pressed", "true");
    expect(api.calls("POST /api/v1/favorites")[0]?.body).toEqual({ target_type: "spot", target_id: "s1" });
    gate.resolve(json({ id: 1 }, 201));
    expect(await screen.findByText("Добавлено в избранное ♡")).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-pressed", "true");
  });

  it("rolls back and offers a retry when the request fails", async () => {
    const user = userEvent.setup();
    const api = mockApi({
      "GET /api/v1/me": () => json(RAW_ME),
      "GET /api/v1/me/favorites/ids": () => json({ spot: ["s1"] }),
      "GET /api/v1/auth/csrf": CSRF_OK,
      "DELETE /api/v1/favorites/spot/s1": () => {
        throw new TypeError("Failed to fetch");
      },
    });
    renderWithProviders(<HeartButton type="spot" id="s1" name="Оленевка" />);
    const btn = await screen.findByRole("button", { name: "В избранное: Оленевка" });
    await waitFor(() => expect(btn).toHaveAttribute("aria-pressed", "true"));

    await user.click(btn);
    await waitFor(() => expect(api.calls("DELETE /api/v1/favorites/spot/s1")).toHaveLength(1));
    // rolled back to the saved state + clear network message with «Повторить»
    await waitFor(() => expect(btn).toHaveAttribute("aria-pressed", "true"));
    expect(await screen.findByText(/Нет соединения с сервером/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Повторить" })).toBeInTheDocument();
  });

  it("asks guests to log in instead of calling the API", async () => {
    const user = userEvent.setup();
    const api = mockApi({ "GET /api/v1/me": GUEST_403 });
    renderWithProviders(<HeartButton type="instructor" id="i1" name="Мария Волкова" variant="pill" />);
    const btn = await screen.findByRole("button", { name: "В избранное: Мария Волкова" });
    await waitFor(() => expect(api.calls("GET /api/v1/me")).toHaveLength(1));
    await user.click(btn);
    const dialog = await screen.findByRole("dialog", { name: "Нужен вход в аккаунт" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Войти/ })).toHaveAttribute("href", expect.stringContaining("/login?next="));
    expect(api.calls("POST /api/v1/favorites")).toHaveLength(0);
    expect(btn).toHaveAttribute("aria-pressed", "false");
  });
});
