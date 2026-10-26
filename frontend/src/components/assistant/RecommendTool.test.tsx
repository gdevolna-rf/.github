import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { CSRF_OK, json, mockApi, renderWithProviders } from "@/test/utils";
import { RecommendTool } from "./RecommendTool";

const REGIONS = [
  { slug: "krym", name: "Крым", timezone: "Europe/Moscow" },
  { slug: "kamchatskiy-kray", name: "Камчатский край", timezone: "Asia/Kamchatka" },
];

const RESULT = {
  region: { id: 1, slug: "kamchatskiy-kray", name: "Камчатский край" },
  level: "beginner",
  level_label: "Новичок",
  date: "2026-10-21",
  spots: [
    {
      type: "spot",
      id: "s1",
      slug: "zaliv-anglichanka",
      title: "Залив Англичанка",
      subtitle: "Камчатский край · Для новичков",
      image: null,
      url: "/spots/zaliv-anglichanka",
      difficulty: "beginner",
      difficulty_label: "Для новичков",
      typical_conditions: "Ветер: северо-запад.",
      season: "Весна — лето",
      season_match: false,
      hazards: ["rocks", "cold_water"],
      hazard_notes: "Камни. Обстановка может меняться.",
      seasonal_warning: "",
      rating_avg: "0.00",
      rating_count: 0,
      forecast: null,
      source: "Каталог ГДеволна, данные обновлены 21.10.2026",
    },
  ],
  instructors: [
    {
      type: "instructor",
      id: "i1",
      handle: "aleksey-morozov",
      title: "Алексей Морозов",
      subtitle: "Сёрф-инструктор",
      image: null,
      url: "/instructors/aleksey-morozov",
      rating_avg: "4.80",
      rating_count: 3,
      price_from: "3800.00",
      currency: "RUB",
      certificate_verified: true,
      source: "Каталог ГДеволна, данные обновлены 21.10.2026",
    },
  ],
  rentals: [],
  notes: ["Прогноз для выбранной даты недоступен."],
  disclaimer: "Подборка сформирована автоматически по правилам.",
  rule_version: 1,
  generated_at: "2026-10-21T10:00:00Z",
};

const HAZARDS = { rocks: "Камни", cold_water: "Холодная вода" };

describe("RecommendTool", () => {
  beforeEach(() => window.history.replaceState(null, "", "/assistant"));

  it("requires region and level", async () => {
    const api = mockApi({});
    renderWithProviders(<RecommendTool regions={REGIONS} />);
    fireEvent.click(screen.getByRole("button", { name: "Подобрать" }));
    expect(await screen.findByText("Выберите регион.")).toBeInTheDocument();
    expect(screen.getByText("Выберите уровень катания.")).toBeInTheDocument();
    expect(api.fetch).not.toHaveBeenCalled();
  });

  it("posts region/level/date and renders grouped results with links, sources and the disclaimer", async () => {
    const api = mockApi({ "GET /api/v1/auth/csrf": CSRF_OK, "POST /api/v1/assistant/recommend": () => json(RESULT) });
    const user = userEvent.setup();
    renderWithProviders(<RecommendTool regions={REGIONS} hazardLabels={HAZARDS} />);
    // regions are sorted alphabetically
    const options = within(screen.getByLabelText(/Регион/)).getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(["Выберите регион", "Камчатский край", "Крым"]);
    await user.selectOptions(screen.getByLabelText(/Регион/), "kamchatskiy-kray");
    await user.selectOptions(screen.getByLabelText(/Уровень катания/), "beginner");
    fireEvent.change(screen.getByLabelText(/Когда собираетесь/), { target: { value: "2099-01-01" } });
    await user.click(screen.getByRole("button", { name: "Подобрать" }));
    expect(await screen.findByText(/ближайшего года/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Когда собираетесь/), { target: { value: "" } });
    await user.click(screen.getByRole("button", { name: "Подобрать" }));

    expect(await screen.findByRole("heading", { name: /Подборка: Камчатский край · Новичок/ })).toBeInTheDocument();
    expect(api.calls("POST /api/v1/assistant/recommend")[0].body).toEqual({ region: "kamchatskiy-kray", level: "beginner" });
    expect(screen.getByRole("link", { name: "Залив Англичанка" })).toHaveAttribute("href", "/spots/zaliv-anglichanka");
    expect(screen.getByRole("link", { name: "Алексей Морозов" })).toHaveAttribute("href", "/instructors/aleksey-morozov");
    expect(screen.getByText("Сертификат проверен")).toBeInTheDocument();
    expect(screen.getByText("Не лучший сезон")).toBeInTheDocument();
    // «Камни» is already in the notes → only «Холодная вода» is added
    expect(screen.getByText(/Холодная вода\. Камни\. Обстановка может меняться\./)).toBeInTheDocument();
    expect(screen.getAllByText(/Источник: Каталог ГДеволна/)).toHaveLength(2);
    expect(screen.getByText(/Типичные условия \(не прогноз\)/)).toBeInTheDocument();
    expect(screen.getByText("Подборка сформирована автоматически по правилам.", { exact: false })).toBeInTheDocument();
    // empty rentals → catalogue link for the region
    expect(screen.getByRole("link", { name: /Вся аренда региона/ })).toHaveAttribute("href", "/rentals?region=kamchatskiy-kray");
    expect(window.location.search).toBe("?region=kamchatskiy-kray&level=beginner");
  });

  it("shows the server error in the region field", async () => {
    mockApi({
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/assistant/recommend": () =>
        json({ error: { code: "region_not_found", message: "Регион не найден.", fields: { region: ["Выберите регион из списка."] } } }, 400),
    });
    renderWithProviders(<RecommendTool regions={REGIONS} initial={{ region: "nope", level: "beginner", date: "" }} />);
    expect(await screen.findByText("Выберите регион из списка.")).toBeInTheDocument();
  });

  it("shows «Нет соединения» with retry on network errors and loads regions in the browser if SSR had none", async () => {
    mockApi({
      "GET /api/v1/regions": () => json(REGIONS),
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/assistant/recommend": () => Promise.reject(new TypeError("Failed to fetch")),
    });
    const user = userEvent.setup();
    renderWithProviders(<RecommendTool regions={[]} />);
    await screen.findByRole("option", { name: "Крым" });
    await user.selectOptions(screen.getByLabelText(/Регион/), "krym");
    await user.selectOptions(screen.getByLabelText(/Уровень катания/), "advanced");
    await user.click(screen.getByRole("button", { name: "Подобрать" }));
    expect((await screen.findAllByText(/Нет соединения/, {}, { timeout: 4000 })).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Повторить" })).toBeInTheDocument();
  });
});
