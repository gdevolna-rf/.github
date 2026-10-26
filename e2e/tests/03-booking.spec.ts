import { expect, test } from "@playwright/test";
import { apiCall, apiLogin, apiRegister, demo, uiLogin, uniqueEmail } from "../support/app";

/**
 * F03 / ATX-14: клиент записывается на свободный слот инструктора через профиль; инструктор видит запрос
 * в «Бронированиях клиентов» и подтверждает — у клиента статус «Подтверждено». Свободных мест становится меньше.
 */
test("клиент записывается на занятие, инструктор подтверждает запись", async ({ page, browser }) => {
  const email = uniqueEmail("student");
  await apiRegister(page.request, email);

  const instructorCtx = await browser.newContext();
  await apiLogin(instructorCtx.request, demo.instructor);
  const me = await (await instructorCtx.request.get("/api/v1/me")).json();
  const handle = me.profile.handle as string;

  await page.goto(`/instructors/${handle}`);
  await page.getByRole("button", { name: "Записаться" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Пара слов инструктору").fill("Первый раз на доске, нужен гидрокостюм.");
  await dialog.getByRole("button", { name: "Отправить заявку" }).click();
  await page.waitForURL(/\/account\/bookings\//, { waitUntil: "commit" });
  await expect(page.getByText("Запрошено").first()).toBeVisible();
  const bookingId = page.url().split("/account/bookings/")[1].split(/[?#]/)[0];

  // Инструктор подтверждает в кабинете (7.3: requested → confirmed).
  const ip = await instructorCtx.newPage();
  await ip.goto(`/account/bookings/${bookingId}`);
  await ip.getByRole("button", { name: "Подтвердить" }).click();
  await ip.getByRole("dialog").getByRole("button", { name: "Подтвердить" }).click();
  await expect(ip.getByText("Подтверждено").first()).toBeVisible();

  await page.reload();
  await expect(page.getByText("Подтверждено").first()).toBeVisible();
  await instructorCtx.close();
});

/**
 * AT-06 / F11 / ATX-15: инструктор не может открыть частный слот на время, когда у него урок школы —
 * сервер отвечает 409 instructor_busy.
 */
test("пересекающийся слот инструктора блокируется сервером", async ({ browser }) => {
  const ctx = await browser.newContext();
  await apiLogin(ctx.request, demo.instructor);
  const today = new Date();
  const to = new Date(today.getTime() + 14 * 86400_000);
  const schedule = await (
    await ctx.request.get(`/api/v1/me/schedule?from=${today.toISOString().slice(0, 10)}&to=${to.toISOString().slice(0, 10)}`)
  ).json();
  const busy = schedule.results.find((s: { status: string }) => s.status === "scheduled");
  expect(busy, "в расписании инструктора есть занятие").toBeTruthy();
  const offers = await (await ctx.request.get("/api/v1/me/instructor/offers")).json();
  const offer = (Array.isArray(offers) ? offers : offers.results)[0];
  const res = await apiCall(ctx.request, "post", "me/instructor/sessions", { offer_id: offer.id, starts_at: busy.starts_at });
  expect(res.status()).toBe(409);
  expect((await res.json()).error.code).toBe("instructor_busy");
  await ctx.close();
});
