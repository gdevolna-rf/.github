import { expect, type APIRequestContext, type Browser, type Page } from "@playwright/test";
import { firstLink, latestMessageTo } from "./mailpit";
import { totp } from "./totp";

export const DEMO_PASSWORD = "Demo-2026!";
export const MODERATOR_TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";
export const demo = {
  surfer: "surfer@demo.gdevolna.local",
  instructor: "aleksey.morozov@demo.gdevolna.local",
  shaper: "andrey.volkov@demo.gdevolna.local",
  rental: "rental@demo.gdevolna.local",
  moderator: "moderator@demo.gdevolna.local",
};

export const uniqueEmail = (prefix: string) => `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e4)}@e2e.test`;

async function csrf(request: APIRequestContext): Promise<string> {
  await request.get("/api/v1/auth/csrf");
  const state = await request.storageState();
  return state.cookies.find((c) => c.name === "csrftoken")?.value ?? "";
}

/** POST/PUT/PATCH/DELETE с CSRF для сессии, сохранённой в request-контексте. */
export async function apiCall(request: APIRequestContext, method: "post" | "put" | "patch" | "delete", path: string, data?: unknown, headers: Record<string, string> = {}) {
  const token = await csrf(request);
  return request[method](`/api/v1/${path}`, { data, headers: { "X-CSRFToken": token, ...headers } });
}

export async function apiLogin(request: APIRequestContext, email: string, password = DEMO_PASSWORD) {
  const res = await apiCall(request, "post", "auth/login", { email, password });
  expect(res.ok(), `login ${email}: ${res.status()} ${await res.text()}`).toBeTruthy();
}

export async function apiRegister(request: APIRequestContext, email: string, primary_type = "surfer", extra: string[] = []) {
  const res = await apiCall(request, "post", "auth/register", {
    email,
    password: "E2e-Passw0rd!",
    first_name: "Тест",
    last_name: "Сёрфер",
    primary_type,
    extra_specialties: extra,
    accept_terms: true,
    accept_privacy: true,
  });
  expect(res.status(), await res.text()).toBe(201);
  return res.json();
}

/** Подтверждение email по ссылке из письма в Mailpit (5.3). */
export async function verifyEmailViaMailpit(page: Page, email: string) {
  const mail = await latestMessageTo(email, { subjectIncludes: "одтвер" });
  const link = new URL(firstLink(mail.Text || mail.HTML, "verify-email"));
  await page.goto(link.pathname + link.search);
  await expect(page.getByText("Почта подтверждена").first()).toBeVisible();
}

export async function uiLogin(page: Page, email: string, password = DEMO_PASSWORD, next = "/account") {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Электронная почта").fill(email);
  await page.getByLabel("Пароль", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Войти" }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { waitUntil: "commit" });
}

/** Модератор: вход + TOTP-подтверждение сессии (2FA для персонала). */
export async function moderatorSession(browser: Browser) {
  const context = await browser.newContext();
  await apiLogin(context.request, demo.moderator);
  const res = await apiCall(context.request, "post", "auth/2fa/verify", { code: totp(MODERATOR_TOTP_SECRET) });
  expect(res.ok(), await res.text()).toBeTruthy();
  return context;
}

export async function counters(request: APIRequestContext) {
  const res = await request.get("/api/v1/me/counters");
  expect(res.ok()).toBeTruthy();
  return (await res.json()) as { unread_messages: number; unread_notifications: number; new_inquiries: number; pending_bookings: number };
}

/** Нет внешней горизонтальной прокрутки (ATX-19). */
export async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "горизонтальная прокрутка страницы").toBeLessThanOrEqual(1);
}
