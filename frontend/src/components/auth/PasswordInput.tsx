"use client";
import { useState } from "react";
import { TextInput, type TextInputProps } from "@/components/ui/Field";

/** Password field with «Показать / Скрыть». */
export function PasswordInput(props: Omit<TextInputProps, "type">) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="gv-password-wrap">
      <TextInput {...props} type={visible ? "text" : "password"} />
      <button
        type="button"
        className="gv-password-toggle"
        aria-pressed={visible}
        aria-label={visible ? "Скрыть пароль" : "Показать пароль"}
        onClick={() => setVisible((v) => !v)}
      >
        {visible ? "Скрыть" : "Показать"}
      </button>
    </div>
  );
}
