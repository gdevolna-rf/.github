import { describe, expect, it } from "vitest";
import { boardFromParams, mergeQuery, parseWeight, recommendFromParams, validateBoard, validateRecommend } from "./assistantModel";

const TODAY = new Date(2026, 9, 21);

describe("assistant model", () => {
  it("parses weight with a comma and rejects garbage", () => {
    expect(parseWeight("72,5")).toBe(72.5);
    expect(parseWeight(" 80 ")).toBe(80);
    expect(parseWeight("80kg")).toBeNaN();
    expect(parseWeight("")).toBeNaN();
  });

  it("validates the board form like the server serializer", () => {
    expect(validateBoard({ weight: "", level: "", wave: "" }).errors).toEqual({
      weight_kg: "Укажите вес.",
      level: "Выберите уровень катания.",
      wave: "Выберите волну.",
    });
    expect(validateBoard({ weight: "201", level: "pro", wave: "big" }).errors.weight_kg).toBe("Вес от 25 до 200 кг.");
    expect(validateBoard({ weight: "72,55", level: "beginner", wave: "small" }).data).toEqual({ weight_kg: 72.6, level: "beginner", wave: "small" });
  });

  it("validates the recommendation form; date is optional and within a year", () => {
    expect(validateRecommend({ region: "", level: "", date: "" }, TODAY).errors).toEqual({
      region: "Выберите регион.",
      level: "Выберите уровень катания.",
    });
    expect(validateRecommend({ region: "krym", level: "beginner", date: "2026-10-01" }, TODAY).errors.date).toMatch(/ближайшего года/);
    expect(validateRecommend({ region: "krym", level: "beginner", date: "" }, TODAY).data).toEqual({ region: "krym", level: "beginner" });
    expect(validateRecommend({ region: "krym", level: "beginner", date: "2026-11-02" }, TODAY).data).toEqual({
      region: "krym",
      level: "beginner",
      date: "2026-11-02",
    });
  });

  it("reads shareable URL parameters defensively", () => {
    expect(boardFromParams({ weight: "75", board_level: "beginner", wave: "huge" })).toEqual({ weight: "75", level: "beginner", wave: "" });
    expect(recommendFromParams({ region: "krym", level: ["advanced"], date: "zz" })).toEqual({ region: "krym", level: "advanced", date: "" });
    expect(mergeQuery("?region=krym&level=pro", { level: null, weight: "80" })).toBe("?region=krym&weight=80");
    expect(mergeQuery("", { a: "" })).toBe("");
  });
});
