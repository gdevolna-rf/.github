import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "./Modal";

function Harness({ onClose, nested }: { onClose?: () => void; nested?: boolean }) {
  const [open, setOpen] = useState(false);
  const [inner, setInner] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Открыть</button>
      <p>Фон страницы</p>
      <Modal
        open={open}
        onClose={() => {
          onClose?.();
          setOpen(false);
        }}
        title="Профиль шейпера"
        description="Описание"
      >
        <input aria-label="Имя" />
        <a href="/x">Ссылка</a>
        {nested && <button onClick={() => setInner(true)}>Вложенное</button>}
        <button>Последняя</button>
      </Modal>
      {nested && (
        <Modal open={inner} onClose={() => setInner(false)} title="Вложенное окно">
          <button>Ок</button>
        </Modal>
      )}
    </>
  );
}

describe("Modal (UX-12, ATX-31)", () => {
  it("is an aria-modal dialog labelled by its title and moves focus inside", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "Открыть" }));
    const dialog = await screen.findByRole("dialog", { name: "Профиль шейпера" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleDescription("Описание");
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("closes on Escape and returns focus to the opener", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const opener = screen.getByRole("button", { name: "Открыть" });
    await user.click(opener);
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(opener).toHaveFocus();
  });

  it("traps Tab and Shift+Tab inside the dialog", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "Открыть" }));
    await screen.findByRole("dialog");
    const close = screen.getByRole("button", { name: "Закрыть" });
    const last = screen.getByRole("button", { name: "Последняя" });
    await user.tab(); // from the dialog container to the first focusable
    expect(close).toHaveFocus();
    await user.tab({ shift: true }); // wraps to the last one
    expect(last).toHaveFocus();
    await user.tab(); // and back to the first
    expect(close).toHaveFocus();
    for (let i = 0; i < 6; i++) await user.tab();
    expect(screen.getByRole("dialog").contains(document.activeElement)).toBe(true);
  });

  it("closes on a backdrop press but not on a click inside", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "Открыть" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(screen.getByLabelText("Имя"));
    expect(onClose).not.toHaveBeenCalled();
    await user.click(dialog.parentElement!); // the backdrop
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("locks page scroll and makes the background inert while open", async () => {
    const user = userEvent.setup();
    const { container } = render(<Harness />);
    await user.click(screen.getByRole("button", { name: "Открыть" }));
    await screen.findByRole("dialog");
    expect(document.body.style.overflow).toBe("hidden");
    expect(container).toHaveAttribute("inert");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(document.body.style.overflow).toBe(""));
    expect(container).not.toHaveAttribute("inert");
  });

  it("Escape closes only the top-most modal", async () => {
    const user = userEvent.setup();
    render(<Harness nested />);
    await user.click(screen.getByRole("button", { name: "Открыть" }));
    await user.click(await screen.findByRole("button", { name: "Вложенное" }));
    expect(await screen.findByRole("dialog", { name: "Вложенное окно" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Вложенное окно" })).not.toBeInTheDocument());
    expect(screen.getByRole("dialog", { name: "Профиль шейпера" })).toBeInTheDocument();
  });
});
