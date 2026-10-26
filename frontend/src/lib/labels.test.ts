import { describe, expect, it } from "vitest";
import { choiceCode, choiceLabel, compassCodes, getStatus, INQUIRY_ACTIONS, RENTAL_BOOKING_ACTIONS, STATUS, statusLabel, statusTone } from "./labels";

describe("status vocabulary (SHO-05, ATX-28)", () => {
  it("maps every server code of the main state machines to a Russian label and a tone", () => {
    expect(getStatus("inquiry", "in_progress")).toEqual({ label: "В работе", tone: "info" });
    expect(statusLabel("inquiry", "declined")).toBe("Отказано");
    expect(statusLabel("booking", "requested")).toBe("Ожидает подтверждения");
    expect(statusLabel("rentalBooking", "in_progress")).toBe("Выдано");
    expect(statusLabel("rentalBooking", "completed")).toBe("Возвращено");
    expect(statusLabel("session", "completed")).toBe("Проведено");
    expect(statusLabel("review", "pending")).toBe("На модерации");
    expect(statusLabel("proposal", "needs_info")).toBe("Нужны уточнения");
    expect(statusTone("availability", "out_of_stock")).toBe("danger"); // not amber like «Под заказ»
    expect(statusTone("certificate", "verified")).toBe("verified");
    expect(statusTone("certificate", "uploaded")).not.toBe(statusTone("certificate", "verified"));
  });

  it("never shows a raw code", () => {
    expect(statusLabel("inquiry", "pending")).toBe("Статус уточняется");
    expect(statusLabel("booking", null)).toBe("Статус уточняется");
    for (const domain of Object.values(STATUS)) {
      for (const def of Object.values(domain)) expect(def.label).not.toMatch(/^[a-z_]+$/);
    }
  });

  it("accepts choice objects {code, label} from the API", () => {
    expect(getStatus("publication", { code: "published", label: "Опубликован" })).toEqual({ label: "Опубликовано", tone: "ok" });
    expect(getStatus("inquiry", { code: "something_new", label: "Новый статус" })).toEqual({ label: "Новый статус", tone: "muted" });
  });

  it("has one set of action verbs", () => {
    expect(INQUIRY_ACTIONS.accept).toBe("Взять в работу");
    expect(RENTAL_BOOKING_ACTIONS.start).toBe("Выдать");
  });
});

describe("choice helpers", () => {
  it("reads codes and labels from strings or objects", () => {
    expect(choiceCode("beginner")).toBe("beginner");
    expect(choiceCode({ code: "beach", label: "Бич-брейк" })).toBe("beach");
    expect(choiceCode(null)).toBeNull();
    expect(choiceLabel({ code: "beach", label: "Бич-брейк" })).toBe("Бич-брейк");
    expect(choiceLabel("reef", { reef: "Риф-брейк" })).toBe("Риф-брейк");
    expect(choiceLabel("unknown_code", { reef: "Риф" })).toBe("");
  });
  it("normalises compass directions", () => {
    expect(compassCodes(["NW", { code: "N", label: "Север", short: "С", degrees: 0 }, "XX", "NW", null])).toEqual(["NW", "N"]);
  });
});
