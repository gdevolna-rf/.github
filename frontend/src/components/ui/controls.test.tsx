import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Select, TextInput } from "./Field";
import { Segmented } from "./Segmented";
import { Toggle, ToggleRow } from "./Toggle";
import { Tabs, TabPanel } from "./Tabs";

describe("Select (UX-06, UX-14)", () => {
  it("is labelled, keeps the placeholder option and links hint/error", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <Select
        label="Регион"
        placeholder="Все регионы"
        options={[
          { value: "kamchatka", label: "Камчатский край" },
          { value: "crimea", label: "Крым" },
        ]}
        hint="Где вы катаетесь"
        error="Выберите регион"
        required
        value=""
        onChange={onChange}
      />,
    );
    const select = screen.getByRole("combobox", { name: "Регион" });
    expect(select).toHaveClass("gv-select");
    expect(select).toBeRequired();
    expect(select).toHaveAttribute("aria-invalid", "true");
    expect(select).toHaveAccessibleDescription("Где вы катаетесь Выберите регион");
    expect(screen.getByRole("option", { name: "Все регионы" })).toHaveValue("");
    await user.selectOptions(select, "crimea");
    expect(onChange).toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Выберите регион");
  });

  it("TextInput has a visible label and no aria-invalid without an error", () => {
    render(<TextInput label="Электронная почта" type="email" />);
    const input = screen.getByRole("textbox", { name: "Электронная почта" });
    expect(input).not.toHaveAttribute("aria-invalid");
  });
});

describe("Toggle (UX-07)", () => {
  function Controlled() {
    const [on, setOn] = useState(false);
    return <ToggleRow title="Хочу быть GG Surfer" description="Появляться в поиске сообщества" checked={on} onChange={setOn} />;
  }
  it("is a switch with aria-checked, named by its row title and toggled by click/keyboard", async () => {
    const user = userEvent.setup();
    render(<Controlled />);
    const sw = screen.getByRole("switch", { name: "Хочу быть GG Surfer" });
    expect(sw).toHaveAccessibleDescription("Появляться в поиске сообщества");
    expect(sw).toHaveAttribute("aria-checked", "false");
    expect(sw).toHaveClass("toggle");
    await user.click(sw);
    expect(sw).toHaveAttribute("aria-checked", "true");
    expect(sw).toHaveClass("on");
    sw.focus();
    await user.keyboard(" ");
    expect(sw).toHaveAttribute("aria-checked", "false");
    await user.keyboard("{Enter}");
    expect(sw).toHaveAttribute("aria-checked", "true");
  });
  it("standalone toggle uses its label as the accessible name", () => {
    render(<Toggle checked label="Показываться на карте" onChange={() => {}} />);
    expect(screen.getByRole("switch", { name: "Показываться на карте" })).toHaveAttribute("aria-checked", "true");
  });
});

describe("Segmented (UX-05)", () => {
  function Controlled() {
    const [v, setV] = useState<"map" | "list" | "grid">("map");
    return (
      <Segmented
        ariaLabel="Вид"
        value={v}
        onChange={setV}
        options={[
          { value: "map", label: "На карте" },
          { value: "list", label: "Списком" },
          { value: "grid", label: "Плиткой" },
        ]}
      />
    );
  }
  it("is a radiogroup with roving tabindex and arrow-key selection", async () => {
    const user = userEvent.setup();
    render(<Controlled />);
    expect(screen.getByRole("radiogroup", { name: "Вид" })).toBeInTheDocument();
    const map = screen.getByRole("radio", { name: "На карте" });
    const list = screen.getByRole("radio", { name: "Списком" });
    const grid = screen.getByRole("radio", { name: "Плиткой" });
    expect(map).toHaveAttribute("aria-checked", "true");
    expect(map).toHaveAttribute("tabindex", "0");
    expect(list).toHaveAttribute("tabindex", "-1");
    map.focus();
    await user.keyboard("{ArrowRight}");
    expect(list).toHaveAttribute("aria-checked", "true");
    expect(list).toHaveFocus();
    await user.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(grid).toHaveAttribute("aria-checked", "true"); // wraps around
    await user.click(map);
    expect(map).toHaveAttribute("aria-checked", "true");
  });
});

describe("Tabs", () => {
  function Controlled() {
    const [v, setV] = useState("about");
    return (
      <>
        <Tabs
          idPrefix="inst"
          ariaLabel="Разделы профиля"
          value={v}
          onChange={setV}
          items={[
            { id: "about", label: "О знакомстве" },
            { id: "calendar", label: "Календарь занятий" },
            { id: "reviews", label: "Отзывы", badge: 3 },
          ]}
        />
        <TabPanel idPrefix="inst" id="about" value={v}>
          Про занятия
        </TabPanel>
        <TabPanel idPrefix="inst" id="calendar" value={v}>
          Календарь
        </TabPanel>
      </>
    );
  }
  it("follows the WAI-ARIA tabs pattern", async () => {
    const user = userEvent.setup();
    render(<Controlled />);
    const about = screen.getByRole("tab", { name: "О знакомстве" });
    expect(about).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "О знакомстве" })).toHaveTextContent("Про занятия");
    about.focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Календарь занятий" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Календарь занятий" })).toHaveTextContent("Календарь");
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: /Отзывы/ })).toHaveFocus();
  });
});
