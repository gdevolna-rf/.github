import { expect, test } from "@playwright/test";
import { apiCall, apiLogin, counters, demo, uniqueEmail, verifyEmailViaMailpit } from "../support/app";

/**
 * AT-01 / F01 / MSG-03 / AT-04 / ATX-09 / ATX-10:
 * новый клиент регистрируется через форму, подтверждает email, заказывает доску у шейпера — чат доступен сразу;
 * пишет два сообщения до принятия; шейпер видит 2 непрочитанных, открывает диалог — счётчик обнуляется,
 * его ответ виден клиенту (второе устройство).
 */
test("регистрация → заявка на доску → чат до принятия → непрочитанные у шейпера обнуляются", async ({ page, browser }) => {
  const email = uniqueEmail("client");

  await page.goto("/register");
  await page.locator('input[name="first_name"]').fill("Ольга");
  await page.locator('input[name="last_name"]').fill("Тестова");
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill("E2e-Passw0rd!");
  await page.getByLabel(/Принимаю пользовательское соглашение/).check();
  await page.getByLabel(/Согласен на обработку персональных данных/).check();
  await page.getByRole("button", { name: "Создать аккаунт" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/register"), { waitUntil: "commit" });
  await verifyEmailViaMailpit(page, email);

  // Модель доски шейпера demo.shaper (мастерская «Volna Craft»).
  const shaperCtx = await browser.newContext();
  await apiLogin(shaperCtx.request, demo.shaper);
  const workshop = await (await shaperCtx.request.get("/api/v1/me/workshop")).json();
  const boards = await (await page.request.get(`/api/v1/boards?shaper=${workshop.slug}`)).json();
  const board = boards.results[0];
  const before = await counters(shaperCtx.request);

  await page.goto(`/boards/${board.id}`);
  await page.getByRole("button", { name: /Заказать/ }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Сообщение").fill("Здравствуйте! Интересует эта модель, есть ли в наличии?");
  await dialog.getByRole("button", { name: "Отправить" }).click();
  await page.waitForURL(/\/account\/inquiries\//, { waitUntil: "commit" });

  // Второе сообщение до принятия заявки (BR-06, MSG-03).
  await page.getByPlaceholder("Напишите сообщение или прикрепите фото…").fill("И сколько ждать изготовление?");
  await page.getByRole("button", { name: "Отправить" }).click();
  await expect(page.getByText("И сколько ждать изготовление?")).toBeVisible();

  const inquiryId = page.url().split("/account/inquiries/")[1].split(/[?#]/)[0];
  await expect.poll(async () => (await counters(shaperCtx.request)).unread_messages).toBe(before.unread_messages + 2);

  // Шейпер открывает обращение на «втором устройстве» → непрочитанные исчезают, ответ виден клиенту.
  const shaperPage = await shaperCtx.newPage();
  await shaperPage.goto(`/account/inquiries/${inquiryId}`);
  await expect(shaperPage.getByText("И сколько ждать изготовление?")).toBeVisible();
  await expect.poll(async () => (await counters(shaperCtx.request)).unread_messages).toBe(before.unread_messages);
  await shaperPage.getByPlaceholder("Напишите сообщение или прикрепите фото…").fill("Есть в наличии, приезжайте примерить!");
  await shaperPage.getByRole("button", { name: "Отправить" }).click();

  await expect(page.getByText("Есть в наличии, приезжайте примерить!")).toBeVisible({ timeout: 20_000 });
  await shaperCtx.close();
});

// AT-03 / ATX-03 / SHP-11: шейпер не может написать сам себе — ни в интерфейсе, ни прямым POST.
test("шейпер не может заказать собственную доску", async ({ browser }) => {
  const ctx = await browser.newContext();
  await apiLogin(ctx.request, demo.shaper);
  const workshop = await (await ctx.request.get("/api/v1/me/workshop")).json();
  const boards = await (await ctx.request.get(`/api/v1/boards?shaper=${workshop.slug}`)).json();
  const board = boards.results[0];

  const page = await ctx.newPage();
  await page.goto(`/boards/${board.id}`);
  await expect(page.getByRole("button", { name: "Это ваша доска" }).first()).toBeDisabled();

  const res = await apiCall(ctx.request, "post", "inquiries", { kind: "board_purchase", target_type: "board_model", target_id: board.id, message: "сам себе" });
  expect(res.status()).toBe(403);
  expect((await res.json()).error.code).toBe("self_inquiry");
  await ctx.close();
});
