import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { CSRF_OK, json, mockApi, renderWithProviders } from "@/test/utils";
import { BoardSizeTool } from "./BoardSizeTool";

const RESULT = {
  input: { weight_kg: "90.0", level: "intermediate", wave: "medium" },
  volume_l: { min: "49.5", max: "63.0" },
  formula: { guild_factor: { min: "0.55", max: "0.70" }, wave_factor: "1.00", rule_version: 1 },
  board_types: [
    { code: "fish", name: "Fish / Фиш" },
    { code: "funboard", name: "Фанборд" },
  ],
  explanation: "Объём рассчитан по формуле гильд-фактора.",
  warnings: ["Большая волна не рекомендуется новичкам."],
  matching_boards: [
    {
      variant_id: "v1",
      model_id: "m1",
      sku: "GV-1",
      title: "Ocean Soul",
      subtitle: "Volna Craft · Лонгборд",
      board_type: { code: "longboard", name: "Лонгборд" },
      length_in: "108.00",
      length_label: "9′0″",
      width_in: "22.75",
      thickness_in: null,
      volume_l: "62.00",
      price: "79000.00",
      currency: "RUB",
      availability: "in_stock",
      availability_label: "В наличии",
      type_match: false,
      image: null,
      url: "/boards/m1",
      source: "Каталог ГДеволна, данные обновлены 21.10.2026",
    },
  ],
  disclaimer: "Это ориентир по формуле, а не гарантия.",
};

async function fill(weight: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/Ваш вес/), weight);
  await user.selectOptions(screen.getByLabelText(/Уровень катания/), "intermediate");
  await user.selectOptions(screen.getByLabelText(/Волна/), "medium");
  await user.click(screen.getByRole("button", { name: "Рассчитать объём" }));
}

describe("BoardSizeTool", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/assistant");
  });

  it("validates on the client without calling the API", async () => {
    const api = mockApi({});
    renderWithProviders(<BoardSizeTool />);
    fireEvent.click(screen.getByRole("button", { name: "Рассчитать объём" }));
    expect(await screen.findByText("Укажите вес.")).toBeInTheDocument();
    expect(screen.getByText("Выберите уровень катания.")).toBeInTheDocument();
    expect(screen.getByText("Выберите волну.")).toBeInTheDocument();
    expect(api.fetch).not.toHaveBeenCalled();
  });

  it("posts the parameters, shows the result and mirrors them into the URL", async () => {
    const api = mockApi({ "GET /api/v1/auth/csrf": CSRF_OK, "POST /api/v1/assistant/board-size": () => json(RESULT) });
    renderWithProviders(<BoardSizeTool />);
    await fill("90");
    const heading = await screen.findByRole("heading", { name: "Рекомендованный объём" });
    expect(api.calls("POST /api/v1/assistant/board-size")[0].body).toEqual({ weight_kg: 90, level: "intermediate", wave: "medium" });
    expect(screen.getByText("49,5–63")).toBeInTheDocument();
    expect(screen.getByText("Fish / Фиш")).toBeInTheDocument();
    expect(screen.getByText("Большая волна не рекомендуется новичкам.", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Это ориентир по формуле, а не гарантия.", { exact: false })).toBeInTheDocument();
    const board = screen.getByRole("link", { name: /Ocean Soul/ });
    expect(board).toHaveAttribute("href", "/boards/m1");
    expect(within(board).getByText("В наличии")).toBeInTheDocument();
    await waitFor(() => expect(heading).toHaveFocus());
    expect(window.location.search).toBe("?weight=90&board_level=intermediate&wave=medium");
    expect(screen.getByText("Рекомендованный объём от 49,5 до 63 литров.", { selector: "[role=status]" })).toBeInTheDocument();
  });

  it("puts server field errors into the fields", async () => {
    mockApi({
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/assistant/board-size": () =>
        json({ error: { code: "validation_error", message: "Проверьте введённые данные.", fields: { weight_kg: ["Слишком много."] } } }, 400),
    });
    renderWithProviders(<BoardSizeTool />);
    await fill("90");
    expect(await screen.findByText("Слишком много.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Ваш вес/)).toHaveAttribute("aria-invalid", "true");
  });

  it("shows an error with retry when the service fails", async () => {
    let calls = 0;
    mockApi({
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/assistant/board-size": () => (++calls === 1 ? json({ error: { code: "server_error", message: "Ошибка сервера." } }, 500) : json(RESULT)),
    });
    renderWithProviders(<BoardSizeTool />);
    await fill("90");
    expect(await screen.findByText("Не удалось рассчитать")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByRole("heading", { name: "Рекомендованный объём" })).toBeInTheDocument();
  });

  it("recalculates a shared link on open", async () => {
    const api = mockApi({ "GET /api/v1/auth/csrf": CSRF_OK, "POST /api/v1/assistant/board-size": () => json({ ...RESULT, matching_boards: [] }) });
    renderWithProviders(<BoardSizeTool initial={{ weight: "90", level: "intermediate", wave: "medium" }} />);
    expect(await screen.findByText(/В каталоге пока нет досок такого объёма/)).toBeInTheDocument();
    expect(api.calls("POST /api/v1/assistant/board-size")).toHaveLength(1);
    expect(screen.getByRole("link", { name: /Все доски/ })).toHaveAttribute("href", "/shapers?tab=boards");
  });
});
