import { describe, expect, it } from "vitest";
import type { SearchResponse } from "@/lib/api/search";
import { hiddenCount, normalizeQuery, parseType, queryState, searchHref, totalResults, typeChips, visibleGroups } from "./searchModel";

const group = (type: string, total: number, n = total) => ({
  type,
  label: type,
  total,
  results: Array.from({ length: n }, (_, i) => ({ type, id: `${type}-${i}`, title: `${type} ${i}`, subtitle: "", image: null, url: `/${type}/${i}` })),
  more_url: `/${type}?q=x`,
});

const ALL = {
  query: "кам",
  groups: [group("surfers", 1), group("spots", 7, 5), group("schools", 0), group("instructors", 2)],
} as unknown as SearchResponse;

describe("search model", () => {
  it("normalises the query like the server", () => {
    expect(normalizeQuery("  Кам   чатка ")).toBe("Кам чатка");
    expect(normalizeQuery(["волна", "x"])).toBe("волна");
    expect(normalizeQuery(undefined)).toBe("");
    expect(normalizeQuery("a".repeat(150))).toHaveLength(100);
    expect(queryState("")).toBe("empty");
    expect(queryState("к")).toBe("short");
    expect(queryState("ка")).toBe("ok");
  });

  it("accepts only known types", () => {
    expect(parseType("spots")).toBe("spots");
    expect(parseType("Instructors,spots")).toBe("instructors");
    expect(parseType("hackers")).toBeNull();
    expect(parseType(undefined)).toBeNull();
    expect(searchHref("кам", "spots")).toBe(`/search?q=${encodeURIComponent("кам")}&types=spots`);
  });

  it("shows non-empty groups in the canonical order", () => {
    expect(visibleGroups(ALL, null, null).map((g) => g.type)).toEqual(["spots", "instructors", "surfers"]);
    expect(totalResults(ALL)).toBe(10);
    expect(hiddenCount(ALL.groups[1])).toBe(2);
  });

  it("with a type filter shows only that group, preferring the detailed response", () => {
    const one = { query: "кам", groups: [group("spots", 7)] } as unknown as SearchResponse;
    const groups = visibleGroups(ALL, one, "spots");
    expect(groups).toHaveLength(1);
    expect(groups[0].results).toHaveLength(7);
    expect(visibleGroups(ALL, null, "schools")).toEqual([]);
  });

  it("builds type chips with totals and the active one", () => {
    const chips = typeChips(ALL, "кам", "spots");
    expect(chips[0]).toMatchObject({ type: null, label: "Все", total: 10, active: false });
    const spots = chips.find((c) => c.type === "spots");
    expect(spots).toMatchObject({ total: 7, active: true });
    expect(chips.find((c) => c.type === "boards")?.total).toBe(0);
    expect(chips).toHaveLength(8);
  });
});
