import { expect, test } from "@playwright/test";
import { expectNoHorizontalScroll } from "../support/app";

// BR-01, NAV-02, ATX-02: каталоги открыты гостю, без предложения «стать шейпером».
test("гость просматривает каталоги досок, спотов и аренды без регистрации", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Гдеволна");

  await page.goto("/shapers?tab=boards");
  await expect(page.getByText(/зарегистрир\w* как шейпер/i)).toHaveCount(0);
  const firstBoard = page.locator('a[href^="/boards/"]').first();
  await expect(firstBoard).toBeVisible();
  await firstBoard.click();
  await page.waitForURL(/\/boards\//, { waitUntil: "commit" });
  await expect(page.getByRole("button", { name: /Заказать/ }).first()).toBeVisible();

  await page.goto("/rentals");
  await expect(page.locator(".rent-card").first()).toBeVisible();

  await page.goto("/instructors");
  await expect(page.locator('a[href^="/instructors/"]').first()).toBeVisible();
});

// SPT-04: розы ветра и свелла — «типичные условия», отдельно от прогноза.
test("карточка спота показывает типичные условия отдельно от прогноза", async ({ page }) => {
  await page.goto("/spots");
  const spotLink = page.locator('a[href^="/spots/"]').first();
  const href = await spotLink.getAttribute("href");
  await page.goto(href!);
  await expect(page.getByRole("heading", { name: "Типичные условия" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Прогноз" })).toBeVisible();
  await expect(page.locator(".gv-rose-pair .gv-rose-svg")).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Отзывы о споте" })).toBeVisible();
});

// ATX-19: нет внешней горизонтальной прокрутки на 320–430 px.
for (const width of [320, 360, 375, 390, 414, 430]) {
  test(`нет горизонтальной прокрутки на ширине ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    for (const path of ["/", "/spots", "/shapers?tab=boards", "/rentals", "/instructors", "/login"]) {
      await page.goto(path);
      await page.waitForLoadState("load");
      await expectNoHorizontalScroll(page);
    }
  });
}

// NAV-03 / UX-03: на телефоне основная навигация — нижняя панель; «Каталог» открывает все разделы.
test("@mobile нижняя панель навигации и каталог разделов", async ({ page }) => {
  test.skip((page.viewportSize()?.width ?? 1440) > 810, "только мобильная ширина");
  await page.goto("/");
  const tabbar = page.getByRole("navigation", { name: /Нижняя|Основная мобильная|Мобильная/i }).last();
  for (const label of ["Главная", "Каталог", "Избранное", "Сообщения"]) {
    await expect(page.getByRole("link", { name: label }).or(page.getByRole("button", { name: label })).last()).toBeVisible();
  }
  await page.getByRole("button", { name: "Каталог" }).last().click();
  await expect(page.getByRole("dialog").getByRole("link", { name: /Аренда/ }).first()).toBeVisible();
  await expectNoHorizontalScroll(page);
  void tabbar;
});
