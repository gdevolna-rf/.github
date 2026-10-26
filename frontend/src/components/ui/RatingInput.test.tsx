import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Rating } from "./Rating";
import { RatingInput } from "./RatingInput";

function Controlled({ onChange }: { onChange?: (v: number) => void }) {
  const [v, setV] = useState<number | null>(null);
  return (
    <RatingInput
      label="Оценка споту"
      required
      value={v}
      onChange={(n) => {
        setV(n);
        onChange?.(n);
      }}
    />
  );
}

describe("RatingInput", () => {
  it("is a labelled radio group of five stars", () => {
    render(<Controlled />);
    expect(screen.getByRole("group", { name: /Оценка споту/ })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(5);
    expect(screen.getByRole("radio", { name: "4 из 5 — хорошо" })).not.toBeChecked();
  });

  it("selects by click and changes with arrow keys", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);
    await user.click(screen.getByRole("radio", { name: "4 из 5 — хорошо" }));
    expect(onChange).toHaveBeenLastCalledWith(4);
    expect(screen.getByRole("radio", { name: "4 из 5 — хорошо" })).toBeChecked();
    await user.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenLastCalledWith(5);
    expect(screen.getByRole("radio", { name: "5 из 5 — отлично" })).toHaveFocus();
    await user.keyboard("{ArrowRight}"); // stays at 5
    expect(onChange).toHaveBeenLastCalledWith(5);
    await user.keyboard("{Home}");
    expect(onChange).toHaveBeenLastCalledWith(1);
    expect(screen.getByRole("radio", { name: "1 из 5 — не понравилось" })).toBeChecked();
  });

  it("shows an error message linked to the group", () => {
    render(<RatingInput value={null} onChange={() => {}} error="Поставьте оценку" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Поставьте оценку");
    expect(screen.getByRole("group")).toHaveAccessibleDescription("Поставьте оценку");
  });
});

describe("Rating display", () => {
  it("announces the average and count, and handles 0 reviews", () => {
    const { rerender } = render(<Rating value="4.86" count={24} />);
    expect(screen.getByRole("img", { name: "Рейтинг 4,9 из 5, 24 отзыва" })).toBeInTheDocument();
    rerender(<Rating value="0.00" count={0} />);
    expect(screen.getByText("Пока без отзывов")).toBeInTheDocument();
  });
});
