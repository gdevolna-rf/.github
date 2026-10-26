"use client";
/**
 * Multi-select of preset values (toggle chips, aria-pressed) + optional custom values typed by the user
 * (interests, board types). Also used as a plain list editor (fun facts) with `presets=[]` and `variant="list"`.
 */
import { useId, useState, type KeyboardEvent } from "react";
import { cx } from "@/lib/cx";
import { Icon } from "@/components/ui/Icon";

export interface TagOption {
  value: string;
  label: string;
}

export function TagPicker({
  label,
  hint,
  presets,
  value,
  onChange,
  max,
  maxLength = 60,
  allowCustom = true,
  customLabel = "Добавить своё",
  customPlaceholder,
  variant = "chips",
  error,
}: {
  label: string;
  hint?: string;
  presets: TagOption[];
  value: string[];
  onChange: (next: string[]) => void;
  max?: number;
  maxLength?: number;
  allowCustom?: boolean;
  customLabel?: string;
  customPlaceholder?: string;
  /** chips: toggle chips; list: removable rows (long texts) */
  variant?: "chips" | "list";
  error?: string | null;
}) {
  const id = `tags-${useId().replace(/:/g, "")}`;
  const [draft, setDraft] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const presetValues = new Set(presets.map((p) => p.value));
  const custom = value.filter((v) => !presetValues.has(v));
  const full = Boolean(max && value.length >= max);

  const toggle = (v: string) => {
    if (value.includes(v)) onChange(value.filter((x) => x !== v));
    else if (!full) onChange([...value, v]);
  };

  const add = () => {
    const text = draft.trim().replace(/\s+/g, " ");
    if (!text) return;
    if (text.length > maxLength) {
      setLocalError(`Не длиннее ${maxLength} символов.`);
      return;
    }
    if (value.some((v) => v.toLowerCase() === text.toLowerCase())) {
      setLocalError("Такое значение уже есть.");
      return;
    }
    if (full) {
      setLocalError(`Можно выбрать не больше ${max}.`);
      return;
    }
    onChange([...value, text]);
    setDraft("");
    setLocalError(null);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      add();
    }
  };

  const shownError = localError ?? error ?? null;

  return (
    <div className={cx("gv-chip-group acc-tags", shownError && "has-error")}>
      <div id={`${id}-label`} className="gv-field-label">
        {label}
        {max ? <span className="acc-tags-count"> · {value.length} из {max}</span> : null}
      </div>
      {hint && (
        <p id={`${id}-hint`} className="gv-field-hint">
          {hint}
        </p>
      )}
      {variant === "chips" ? (
        <div role="group" aria-labelledby={`${id}-label`} aria-describedby={hint ? `${id}-hint` : undefined} className="gv-chip-list">
          {presets.map((o) => {
            const on = value.includes(o.value);
            return (
              <button
                key={o.value}
                type="button"
                aria-pressed={on}
                disabled={!on && full}
                className={cx("gv-chip-toggle", on && "on")}
                onClick={() => toggle(o.value)}
              >
                <span>{o.label}</span>
              </button>
            );
          })}
          {custom.map((v) => (
            <button
              key={`custom-${v}`}
              type="button"
              aria-pressed
              className="gv-chip-toggle on acc-tag-custom"
              onClick={() => toggle(v)}
              aria-label={`Убрать «${v}»`}
            >
              <span>{v}</span>
              <Icon name="close" size={12} />
            </button>
          ))}
        </div>
      ) : (
        <ul className="acc-list-editor" aria-labelledby={`${id}-label`}>
          {value.map((v, i) => (
            <li key={`${i}-${v}`}>
              <span>{v}</span>
              <button type="button" className="acc-icon-btn" aria-label={`Удалить: ${v}`} onClick={() => onChange(value.filter((_, j) => j !== i))}>
                <Icon name="close" size={14} />
              </button>
            </li>
          ))}
          {value.length === 0 && <li className="acc-list-empty">Пока ничего не добавлено.</li>}
        </ul>
      )}
      {allowCustom && (
        <div className="acc-tag-add">
          <label htmlFor={`${id}-input`} className="sr-only">
            {customLabel}
          </label>
          <input
            id={`${id}-input`}
            className="gv-input"
            value={draft}
            maxLength={maxLength}
            placeholder={customPlaceholder ?? customLabel}
            disabled={full}
            onChange={(e) => {
              setDraft(e.target.value);
              setLocalError(null);
            }}
            onKeyDown={onKeyDown}
            aria-describedby={shownError ? `${id}-error` : undefined}
          />
          <button type="button" className="gv-ac-btn" onClick={add} disabled={full || !draft.trim()}>
            <Icon name="plus" size={14} /> {customLabel}
          </button>
        </div>
      )}
      {shownError && (
        <p id={`${id}-error`} className="gv-field-error" role="alert">
          {shownError}
        </p>
      )}
    </div>
  );
}
