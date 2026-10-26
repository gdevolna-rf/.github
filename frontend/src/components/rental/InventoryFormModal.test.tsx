import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { resetCsrfForTests } from "@/lib/api/client";
import type { InventoryItem } from "@/lib/api/inventory";
import { clearCookies, CSRF_OK, json, mockApi, renderWithProviders } from "@/test/utils";
import { InventoryFormModal } from "./InventoryFormModal";
import { ITEM } from "./test-fixtures";

const REGIONS = [
  { id: 1, slug: "kamchatskiy-kray", name: "Камчатский край", timezone: "Asia/Kamchatka" },
  { id: 5, slug: "primorskiy-kray", name: "Приморский край", timezone: "Asia/Vladivostok" },
];
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
const VARIANT = {
  id: "v1",
  sku: "GV-KBA01-LNG-9P2-W2200-001",
  length_display: "9'2\"",
  dimensions_display: "9'2\" × 22\" × 2 7/8\"",
  volume_display: "65 л",
  model: { id: "m1", name: "Kamchatka Classic", status: "published", board_type: { id: 5, code: "longboard", name: "Лонгборд", silhouette: "longboard" } },
};

function routes(overrides: Record<string, (req: { body: unknown }) => Response> = {}) {
  return mockApi({
    "GET /api/v1/auth/csrf": CSRF_OK,
    "GET /api/v1/regions": () => json(REGIONS),
    "GET /api/v1/spots": () => json(page([{ id: "s1", slug: "poberezhye", name: "Побережье Приморья" }])),
    "GET /api/v1/me/workshop": () => json({ error: { code: "no_workshop", message: "Мастерская ещё не создана.", fields: {} } }, 404),
    ...overrides,
  });
}

describe("InventoryFormModal", () => {
  beforeEach(() => {
    clearCookies();
    resetCsrfForTests();
  });

  it("validates on the client before sending", async () => {
    const api = routes();
    renderWithProviders(<InventoryFormModal open item={null} organizationId={null} onClose={() => {}} />);
    const dialog = await screen.findByRole("dialog", { name: "Добавить снаряжение" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Сохранить" }));
    expect(await within(dialog).findByText("Укажите название.")).toBeInTheDocument();
    expect(within(dialog).getByText(/за день или за час/)).toBeInTheDocument();
    expect(api.calls("POST /api/v1/me/inventory")).toHaveLength(0);
  });

  it("creates an organization item with region, spot (by region slug) and a variant link", async () => {
    const onClose = vi.fn();
    const api = routes({
      "GET /api/v1/me/workshop": () => json({ id: "w1" }),
      "GET /api/v1/workshops/w1/variants": () => json([VARIANT]),
      "POST /api/v1/me/inventory": () => json({ ...ITEM, id: "new", title: "Kamchatka Classic 9'2\"" }, 201),
    });
    renderWithProviders(<InventoryFormModal open item={null} organizationId="org-1" onClose={onClose} />);
    const dialog = await screen.findByRole("dialog", { name: "Добавить снаряжение" });
    await userEvent.selectOptions(await within(dialog).findByLabelText("Модель моей мастерской"), "v1");
    expect(within(dialog).getByLabelText(/Название/)).toHaveValue("Kamchatka Classic 9'2\"");
    await waitFor(() => expect(within(dialog).getByRole("option", { name: "Приморский край" })).toBeInTheDocument());
    await userEvent.selectOptions(within(dialog).getByLabelText("Регион"), "5");
    await waitFor(() => expect(api.calls("GET /api/v1/spots").some((c) => c.url.includes("region=primorskiy-kray"))).toBe(true));
    await userEvent.selectOptions(await within(dialog).findByLabelText("Спот рядом"), "s1");
    await userEvent.type(within(dialog).getByLabelText("Цена за сутки, ₽"), "1500");
    await userEvent.click(within(dialog).getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(api.calls("POST /api/v1/me/inventory")[0].body).toMatchObject({
      organization_id: "org-1",
      variant_id: "v1",
      region_id: 5,
      spot_id: "s1",
      rental_price_per_day: "1500",
      size: "9'2\" × 22\" × 2 7/8\"",
      is_published: true,
    });
  });

  it("shows server field errors under the fields and keeps the dialog open", async () => {
    routes({
      "POST /api/v1/me/inventory": () =>
        json({ error: { code: "validation_error", message: "Проверьте данные экземпляра.", fields: { spot_id: ["Спот находится в другом регионе."] } } }, 400),
    });
    renderWithProviders(<InventoryFormModal open item={null} organizationId={null} onClose={() => {}} />);
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Название/), "Гидрокостюм 4/3");
    await userEvent.type(within(dialog).getByLabelText("Цена за час, ₽"), "300");
    await userEvent.click(within(dialog).getByRole("button", { name: "Сохранить" }));
    expect(await within(dialog).findByText("Спот находится в другом регионе.")).toBeInTheDocument();
  });

  it("network failure keeps the form and offers «Повторить»", async () => {
    routes({ "POST /api/v1/me/inventory": () => Promise.reject(new TypeError("Failed to fetch")) as never });
    renderWithProviders(<InventoryFormModal open item={null} organizationId={null} onClose={() => {}} />);
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Название/), "Доска");
    await userEvent.type(within(dialog).getByLabelText("Цена за сутки, ₽"), "1000");
    await userEvent.click(within(dialog).getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByRole("button", { name: "Повторить" })).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/Название/)).toHaveValue("Доска");
  });

  it("edit: PATCH then photo sync (delete removed)", async () => {
    const two = {
      ...ITEM,
      photos: [ITEM.photos[0], { id: 2, position: 1, media: { ...ITEM.photos[0].media, id: "m2", url: "/m/2.png" } }],
    } as unknown as InventoryItem;
    const onClose = vi.fn();
    const api = routes({
      "PATCH /api/v1/me/inventory/i1": () => json(two),
      "DELETE /api/v1/me/inventory/i1/photos/1": () => json({ photos: [{ ...two.photos[1], position: 0 }] }),
    });
    renderWithProviders(<InventoryFormModal open item={two} organizationId="org-1" onClose={onClose} />);
    const dialog = await screen.findByRole("dialog", { name: "Редактировать снаряжение" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Удалить фото 1" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const patch = api.calls("PATCH /api/v1/me/inventory/i1")[0].body as Record<string, unknown>;
    expect(patch).not.toHaveProperty("organization_id");
    expect(patch.title).toBe(ITEM.title);
    expect(api.calls("DELETE /api/v1/me/inventory/i1/photos/1")).toHaveLength(1);
    expect(api.calls("POST /api/v1/me/inventory/i1/photos")).toHaveLength(0);
    expect(api.calls("PUT /api/v1/me/inventory/i1/photos/order")).toHaveLength(0);
  });
});
