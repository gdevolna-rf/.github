import { expect, test } from "@playwright/test";
import { apiCall, apiRegister, moderatorSession, uniqueEmail, verifyEmailViaMailpit } from "../support/app";

/**
 * AT-07 / F08 / ATX-13: пользователь предлагает изменить направление ветра спота — публичная карточка прежняя
 * до решения; модератор (вход с TOTP) видит правку в очереди и одобряет её в интерфейсе — карточка обновлена,
 * в журнале аудита есть запись.
 */
test("правка направления ветра проходит модерацию и обновляет карточку", async ({ page, browser }) => {
  const email = uniqueEmail("proposer");
  await apiRegister(page.request, email);

  const spots = await (await page.request.get("/api/v1/spots?page_size=1")).json();
  const slug = spots.results[0].slug as string;
  const spot = await (await page.request.get(`/api/v1/spots/${slug}`)).json();
  const current: string[] = spot.best_wind_directions.map((d: { code: string }) => d.code);
  const proposed = current.includes("SSW") ? ["NNE"] : ["SSW"];

  const created = await apiCall(page.request, "post", `spots/${spot.id}/proposals`, {
    changes: { best_wind_directions: proposed },
    comment: "Местные катаются при этом ветре",
    source: "Наблюдения e2e",
  });
  expect(created.status(), await created.text()).toBe(201);
  const proposal = await created.json();

  // До решения публичная карточка не меняется.
  const before = await (await page.request.get(`/api/v1/spots/${slug}`)).json();
  expect(before.best_wind_directions.map((d: { code: string }) => d.code)).toEqual(current);

  const modCtx = await moderatorSession(browser);
  const cases = await (await modCtx.request.get("/api/v1/moderation/cases?kind=spot_change&status=open")).json();
  const theCase = (cases.results ?? cases).find((c: { target?: { id?: string }; spot_change_request?: string }) =>
    JSON.stringify(c).includes(proposal.id),
  );
  expect(theCase, "кейс правки в очереди модератора").toBeTruthy();

  const mp = await modCtx.newPage();
  await mp.goto(`/moderation/cases/${theCase.id}`);
  await expect(mp.getByText(/Было|было/).first()).toBeVisible();
  await mp.getByRole("button", { name: /Одобрить|Принять/ }).first().click();
  const dialog = mp.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("textbox").first().fill("Подтверждено местными");
  await dialog.getByRole("button", { name: "Одобрить и опубликовать" }).click();
  await expect(dialog).toBeHidden();

  await expect
    .poll(async () => (await (await page.request.get(`/api/v1/spots/${slug}`)).json()).best_wind_directions.map((d: { code: string }) => d.code))
    .toEqual(proposed);

  const audit = await (await modCtx.request.get(`/api/v1/moderation/audit?object_id=${spot.id}`)).json();
  expect((audit.results ?? audit).length).toBeGreaterThan(0);
  await modCtx.close();
});

// BR-04 / ACC-10: обычный пользователь не попадает в модерацию.
test("обычный пользователь не имеет доступа к модерации", async ({ page }) => {
  const email = uniqueEmail("nomod");
  await apiRegister(page.request, email);
  const res = await page.request.get("/api/v1/moderation/cases");
  expect(res.status()).toBe(403);
  await page.goto("/moderation");
  await expect(page.getByText(/нет доступа|недостаточно прав|только модератор/i).first()).toBeVisible();
});

// 5.3: подтверждение email по ссылке из письма (Mailpit).
test("подтверждение email по ссылке из письма", async ({ page }) => {
  const email = uniqueEmail("verify");
  await apiRegister(page.request, email);
  await verifyEmailViaMailpit(page, email);
  const me = await (await page.request.get("/api/v1/me")).json();
  expect(me.email_verified).toBe(true);
});
