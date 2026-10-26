import { expect, test } from "@playwright/test";
import { apiCall, apiLogin, apiRegister, demo, uniqueEmail, verifyEmailViaMailpit } from "../support/app";

/**
 * AT-05 / F07 / ATX-16: два клиента запрашивают аренду одной доски на пересекающееся время; прокат подтверждает
 * обе заявки одновременно — проходит только одно подтверждение, второе получает 409.
 */
test("две конкурирующие брони одного экземпляра: подтверждается одна", async ({ browser }) => {
  const rental = await browser.newContext();
  await apiLogin(rental.request, demo.rental);
  const items = await (await rental.request.get("/api/v1/rentals?page_size=50")).json();
  const ownerOrg = (await (await rental.request.get("/api/v1/me")).json()).organizations.map((o: { slug: string }) => o.slug);
  const item = items.results.find((i: { owner: { slug: string | null } }) => i.owner.slug && ownerOrg.includes(i.owner.slug));
  expect(item, "у демо-проката есть экземпляр").toBeTruthy();

  const start = new Date(Date.now() + (40 + Math.floor(Math.random() * 300)) * 86400_000);
  start.setUTCHours(6, 0, 0, 0);
  const end = new Date(start.getTime() + Math.max(item.min_rental_hours ?? 1, 24) * 3600_000);

  const ids: string[] = [];
  for (const n of [1, 2]) {
    const ctx = await browser.newContext();
    await apiRegister(ctx.request, uniqueEmail(`renter${n}`));
    const res = await apiCall(
      ctx.request,
      "post",
      "bookings",
      { inventory_item_id: item.id, starts_at: start.toISOString(), ends_at: end.toISOString() },
      { "Idempotency-Key": crypto.randomUUID() },
    );
    expect(res.status(), await res.text()).toBe(201);
    ids.push((await res.json()).id);
    await ctx.close();
  }

  const results = await Promise.all(ids.map((id) => apiCall(rental.request, "post", `bookings/${id}/confirm`, {})));
  const statuses = results.map((r) => r.status()).sort();
  expect(statuses).toEqual([200, 409]);
  await rental.close();
});

/**
 * AT-09 / F15: владелец школы отзывает доступ менеджера — управление школой сразу закрыто, занятия и история на месте.
 */
test("отзыв доступа менеджера сразу закрывает управление школой", async ({ browser }) => {
  const owner = await browser.newContext();
  await apiLogin(owner.request, "school@demo.gdevolna.local");
  const me = await (await owner.request.get("/api/v1/me")).json();
  const school = me.organizations.find((o: { kind: string }) => o.kind === "school");

  const managerCtx = await browser.newContext();
  const managerEmail = uniqueEmail("manager");
  await apiRegister(managerCtx.request, managerEmail);
  const invite = await apiCall(owner.request, "post", `organizations/${school.id}/invites`, { email: managerEmail, role: "manager" });
  expect(invite.status(), await invite.text()).toBe(201);
  const myInvites = await (await managerCtx.request.get("/api/v1/me/invites")).json();
  const token = myInvites[0].token;

  // Приглашение принимается только с подтверждённым email (5.3) — подтверждаем через письмо.
  const page = await managerCtx.newPage();
  await verifyEmailViaMailpit(page, managerEmail);
  const accept = await apiCall(managerCtx.request, "post", `invites/${token}/accept`);
  expect(accept.ok(), await accept.text()).toBeTruthy();
  expect((await managerCtx.request.get(`/api/v1/organizations/${school.id}/manage`)).status()).toBe(200);

  const sessionsBefore = await (await owner.request.get(`/api/v1/organizations/${school.id}/sessions?from=2020-01-01&to=2100-01-01`)).json();
  const managerId = (await (await managerCtx.request.get("/api/v1/me")).json()).id;
  const members = await (await owner.request.get(`/api/v1/organizations/${school.id}/members`)).json();
  const membership = members.find((m: { account: { id: string } }) => m.account.id === managerId);
  const revoke = await apiCall(owner.request, "delete", `organizations/${school.id}/members/${membership.id}`);
  expect(revoke.ok(), await revoke.text()).toBeTruthy();

  // Доступ закрыт немедленно: 403/404 (сервер не раскрывает закрытую карточку).
  expect([403, 404]).toContain((await managerCtx.request.get(`/api/v1/organizations/${school.id}/manage`)).status());
  await page.goto(`/account/orgs/${school.id}/schedule`);
  await expect(page.getByText(/Нет доступа|доступ был отозван/i).first()).toBeVisible();
  const sessionsAfter = await (await owner.request.get(`/api/v1/organizations/${school.id}/sessions?from=2020-01-01&to=2100-01-01`)).json();
  expect((sessionsAfter.results ?? sessionsAfter).length).toBe((sessionsBefore.results ?? sessionsBefore).length);
  await owner.close();
  await managerCtx.close();
});
