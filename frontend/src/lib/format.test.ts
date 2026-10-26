import { describe, expect, it } from "vitest";
import {
  formatBoardDimensions,
  formatClock,
  formatDate,
  formatDateRange,
  formatDateTime,
  formatFeetInches,
  formatInches,
  formatMoney,
  formatPriceFrom,
  formatRating,
  formatRelative,
  formatTime,
  formatUtcOffset,
  initials,
  isoDateInZone,
  plural,
  pluralize,
  WORDS,
} from "./format";

const nbsp = (s: string) => s.replace(/[  ]/g, " ");

describe("plural / pluralize", () => {
  it.each([
    [1, "отзыв"],
    [2, "отзыва"],
    [4, "отзыва"],
    [5, "отзывов"],
    [11, "отзывов"],
    [12, "отзывов"],
    [14, "отзывов"],
    [21, "отзыв"],
    [22, "отзыва"],
    [25, "отзывов"],
    [101, "отзыв"],
    [111, "отзывов"],
    [0, "отзывов"],
  ])("%i → %s", (n, form) => {
    expect(plural(n, WORDS.review)).toBe(form);
  });
  it("prints the number with the right form (fixes «{n} окна» for every n)", () => {
    expect(pluralize(1, WORDS.slot)).toBe("1 окно");
    expect(pluralize(3, WORDS.slot)).toBe("3 окна");
    expect(pluralize(5, WORDS.slot)).toBe("5 окон");
    expect(nbsp(pluralize(1000, WORDS.model))).toBe("1 000 моделей");
  });
});

describe("dates in an explicit IANA time zone", () => {
  const iso = "2026-10-21T21:30:00Z"; // 00:30 next day in Moscow, 09:30 next day on Kamchatka
  it("formats the calendar date of the zone, not of the browser", () => {
    expect(formatDate(iso, { timeZone: "Europe/Moscow" })).toBe("22 октября 2026 г.");
    expect(formatDate(iso, { timeZone: "UTC" })).toBe("21 октября 2026 г.");
    expect(formatDate(iso, { timeZone: "Asia/Kamchatka", style: "dayMonth" })).toBe("22 октября");
    expect(formatDate(iso, { timeZone: "Europe/Moscow", style: "numeric" })).toBe("22.10.2026");
    expect(isoDateInZone(iso, "Asia/Kamchatka")).toBe("2026-10-22");
  });
  it("formats times and ranges", () => {
    expect(formatTime(iso, "Asia/Kamchatka")).toBe("09:30");
    expect(formatTime(iso, "Europe/Moscow")).toBe("00:30");
    const now = new Date("2026-10-01T00:00:00Z");
    expect(formatDateTime(iso, { timeZone: "Asia/Kamchatka", now })).toBe("22 октября, 09:30");
    expect(formatDateTime(iso, { timeZone: "Asia/Kamchatka", now: new Date("2025-01-01T00:00:00Z") })).toBe("22 октября 2026 г., 09:30");
    expect(formatDateRange("2026-10-22T06:00:00Z", "2026-10-22T07:30:00Z", { timeZone: "Europe/Moscow", now })).toBe("22 октября, 09:00–10:30");
    expect(formatUtcOffset("Asia/Kamchatka", iso)).toBe("UTC+12");
  });
  it("formats relative time", () => {
    const now = new Date("2026-10-21T12:00:00Z");
    expect(formatRelative("2026-10-21T11:59:40Z", { now })).toBe("только что");
    expect(formatRelative("2026-10-21T11:55:00Z", { now })).toBe("5 минут назад");
    expect(formatRelative("2026-10-21T14:00:00Z", { now })).toBe("через 2 часа");
    expect(formatRelative("2026-10-20T08:00:00Z", { now, timeZone: "Europe/Moscow" })).toBe("вчера");
    expect(formatRelative("2026-09-01T08:00:00Z", { now, timeZone: "Europe/Moscow" })).toBe("1 сентября");
  });
});

describe("money and numbers", () => {
  it("formats decimal strings with the currency", () => {
    expect(nbsp(formatMoney("65000.00", "RUB"))).toBe("65 000 ₽");
    expect(nbsp(formatMoney("1499.50"))).toBe("1 499,50 ₽");
    expect(nbsp(formatMoney(120, "USD"))).toBe("120 $");
    expect(formatMoney(null)).toBe("");
    expect(formatMoney("abc")).toBe("");
    expect(nbsp(formatPriceFrom("3800.00"))).toBe("от 3 800 ₽");
    expect(formatPriceFrom(null)).toBe("Цена по договорённости");
    expect(formatRating("4.86")).toBe("4,9");
  });
});

describe("board dimensions", () => {
  it("converts inches to feet/inches with fractions", () => {
    expect(formatFeetInches(76)).toBe("6′4″");
    expect(formatFeetInches(108)).toBe("9′0″");
    expect(formatFeetInches("110.00")).toBe("9′2″");
    expect(formatFeetInches(70.5)).toBe("5′10 ½″");
    expect(formatInches(20.5)).toBe("20 ½″");
    expect(formatInches(2.625)).toBe("2 ⅝″");
    expect(formatInches(19)).toBe("19″");
    expect(formatInches(null)).toBe("");
    expect(formatBoardDimensions({ length_in: 76, width_in: 20.5, thickness_in: 2.625, volume_l: "35.2" })).toBe("6′4″ × 20 ½″ × 2 ⅝″ · 35,2 л");
    expect(formatBoardDimensions({ length_in: 110, width_in: 22.75 })).toBe("9′2″ × 22 ¾″");
  });
});

describe("misc", () => {
  it("clock and initials", () => {
    expect(formatClock(65)).toBe("1:05");
    expect(formatClock(3725)).toBe("1:02:05");
    expect(initials("Алексей Морозов")).toBe("АМ");
    expect(initials("surfer_123")).toBe("S");
    expect(initials("")).toBe("?");
  });
});
