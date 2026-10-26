import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SearchGroup } from "@/lib/api/search";
import { internalHref, SearchResults } from "./SearchResults";

const LONG = "Очень длинное название спота, которое не помещается в одну строку и должно переноситься аккуратно";

const groups: SearchGroup[] = [
  {
    type: "spots",
    label: "Споты",
    total: 7,
    more_url: "/spots?q=%D0%BA%D0%B0%D0%BC",
    results: [
      { type: "spots", id: "1", title: "Залив Англичанка", subtitle: "Камчатский край · Для новичков", image: null, url: "/spots/zaliv-anglichanka" },
      { type: "spots", id: "2", title: LONG, subtitle: "", image: null, url: "/spots/long" },
    ],
  },
  {
    type: "instructors",
    label: "Инструкторы",
    total: 1,
    more_url: "/instructors?q=x",
    results: [{ type: "instructors", id: "3", title: "Алексей Морозов", subtitle: "Сёрф-инструктор", image: null, url: "https://evil.example/x" }],
  },
];

describe("SearchResults", () => {
  it("renders groups with headings, counts and links to the objects", () => {
    render(<SearchResults groups={groups} />);
    const spots = screen.getByRole("region", { name: "Споты" });
    expect(within(spots).getByText("7 результатов")).toBeInTheDocument();
    expect(within(spots).getByRole("link", { name: /Залив Англичанка/ })).toHaveAttribute("href", "/spots/zaliv-anglichanka");
    expect(within(spots).getByText(LONG)).toHaveAttribute("title", LONG);
  });

  it("offers «Показать ещё (N)» to the section catalogue only when results are hidden", () => {
    render(<SearchResults groups={groups} />);
    const more = screen.getByRole("link", { name: "Показать ещё 5: Споты" });
    expect(more).toHaveAttribute("href", "/spots?q=%D0%BA%D0%B0%D0%BC");
    expect(within(screen.getByRole("region", { name: "Инструкторы" })).queryByText(/Показать ещё/)).toBeNull();
  });

  it("never links outside the site", () => {
    render(<SearchResults groups={groups} />);
    expect(screen.getByRole("link", { name: /Алексей Морозов/ })).toHaveAttribute("href", "/");
    expect(internalHref("//evil.example")).toBe("/");
    expect(internalHref("/gg?q=x")).toBe("/gg?q=x");
  });
});
