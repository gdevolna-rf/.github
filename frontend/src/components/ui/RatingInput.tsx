"use client";
import { useId, useRef, useState, type KeyboardEvent } from "react";
import { cx } from "@/lib/cx";
import { STAR_PATH } from "./Rating";

export const RATING_CAPTIONS = ["не понравилось", "сложно", "нормально", "хорошо", "отлично"] as const;

export interface RatingInputProps {
  value: number | null;
  onChange: (value: number) => void;
  label?: string;
  name?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
}

/**
 * Star input = native radio group (keyboard: arrows/Home/End; screen readers announce «4 из 5 — хорошо»).
 * Hover previews the value; the caption under the stars repeats it in words.
 */
export function RatingInput({ value, onChange, label = "Оценка", name, required, disabled, error }: RatingInputProps) {
  const autoId = useId();
  const groupName = name ?? `rating-${autoId}`;
  const [hover, setHover] = useState<number | null>(null);
  const refs = useRef<Array<HTMLInputElement | null>>([]);
  const shown = hover ?? value ?? 0;
  const errorId = `${autoId}-error`;

  const move = (e: KeyboardEvent<HTMLInputElement>, current: number) => {
    let next: number | null = null;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") next = Math.min(5, current + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = Math.max(1, current - 1);
    else if (e.key === "Home") next = 1;
    else if (e.key === "End") next = 5;
    if (next !== null) {
      e.preventDefault();
      onChange(next);
      refs.current[next - 1]?.focus();
    }
  };

  return (
    <fieldset
      className={cx("gv-rating-input", disabled && "is-disabled", error && "has-error")}
      aria-describedby={error ? errorId : undefined}
      aria-required={required || undefined}
      disabled={disabled}
    >
      <legend className="gv-field-label">
        {label}
        {required && <span className="gv-req" aria-hidden="true"> *</span>}
      </legend>
      <div className="gv-rating-stars" onMouseLeave={() => setHover(null)}>
        {[1, 2, 3, 4, 5].map((n) => (
          <label key={n} className={cx("gv-rating-star-btn", n <= shown && "is-on")} onMouseEnter={() => !disabled && setHover(n)}>
            <input
              ref={(el) => {
                refs.current[n - 1] = el;
              }}
              type="radio"
              name={groupName}
              value={n}
              checked={value === n}
              tabIndex={value ? (value === n ? 0 : -1) : n === 1 ? 0 : -1}
              onChange={() => onChange(n)}
              onKeyDown={(e) => move(e, value ?? 0)}
              className="sr-only"
              aria-label={`${n} из 5 — ${RATING_CAPTIONS[n - 1]}`}
            />
            <svg viewBox="0 0 24 24" width={28} height={28} aria-hidden="true">
              <path d={STAR_PATH} />
            </svg>
          </label>
        ))}
        <span className="gv-rating-caption" aria-hidden="true">
          {shown ? RATING_CAPTIONS[shown - 1] : "Выберите оценку"}
        </span>
      </div>
      {error && (
        <p id={errorId} className="gv-field-error" role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}
