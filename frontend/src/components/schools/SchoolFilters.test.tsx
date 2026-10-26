import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { navigation } from "@/test/navigation";
import { SchoolFilters } from "./SchoolFilters";
import { schoolsHref } from "./href";

const regions = [
  { value: "kamchatskiy-kray", label: "Камчатский край" },
  { value: "krym", label: "Крым" },
];
const spots = [
  { value: "khalaktyrskiy-plyazh", label: "Халактырский пляж", region: "kamchatskiy-kray" },
  { value: "olenevka", label: "Оленевка", region: "krym" },
];

describe("SchoolFilters", () => {
  it("builds catalogue URLs without empty params and page 1", () => {
    expect(schoolsHref({ region: "", spot: "", q: " ", page: 1 })).toBe("/schools");
    expect(schoolsHref({ region: "krym", q: "Surf", page: 2 })).toBe("/schools?region=krym&q=Surf&page=2");
  });

  it("applies the region at once and drops a spot from another region", async () => {
    render(<SchoolFilters values={{ region: "", spot: "olenevka", q: "" }} regions={regions} spots={spots} />);
    await userEvent.selectOptions(screen.getByLabelText("Регион"), "kamchatskiy-kray");
    expect(navigation.router.replace).toHaveBeenCalledWith("/schools?region=kamchatskiy-kray", { scroll: false });
  });

  it("shows only spots of the chosen region and submits the text search", async () => {
    render(<SchoolFilters values={{ region: "krym", spot: "", q: "" }} regions={regions} spots={spots} />);
    const spot = screen.getByLabelText("Спот");
    expect(spot.querySelectorAll("option")).toHaveLength(2); // «Любые споты» + Оленевка
    await userEvent.type(screen.getByLabelText("Название или город"), "волна{Enter}");
    expect(navigation.router.replace).toHaveBeenLastCalledWith("/schools?region=krym&q=%D0%B2%D0%BE%D0%BB%D0%BD%D0%B0", { scroll: false });
    await userEvent.click(screen.getByRole("button", { name: "Сбросить" }));
    expect(navigation.router.replace).toHaveBeenLastCalledWith("/schools", { scroll: false });
  });
});
