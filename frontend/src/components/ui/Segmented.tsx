"use client";
import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import { Icon, type IconName } from "./Icon";

export interface SegmentOption<T extends string> {
  value: T;
  label: ReactNode;
  icon?: IconName;
  disabled?: boolean;
}

/**
 * Single choice between 2–5 options (map/list, period, format). role="radiogroup", roving tabindex,
 * arrows/Home/End. All segments share one height, padding and radius and never wrap internally (UX-05).
 */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  block,
  size = "md",
  className,
}: {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
  block?: boolean;
  size?: "sm" | "md";
  className?: string;
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const enabled = options.filter((o) => !o.disabled);

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    const idx = enabled.findIndex((o) => o.value === value);
    let next = -1;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (idx + 1) % enabled.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (idx - 1 + enabled.length) % enabled.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = enabled.length - 1;
    if (next < 0) return;
    e.preventDefault();
    const target = enabled[next];
    onChange(target.value);
    refs.current[options.indexOf(target)]?.focus();
  };

  return (
    <div role="radiogroup" aria-label={ariaLabel} className={cx("gv-segmented", block && "is-block", size === "sm" && "is-sm", className)}>
      {options.map((o, i) => {
        const selected = o.value === value;
        const noneSelected = !options.some((x) => x.value === value);
        const focusable = selected || (noneSelected && o === enabled[0]);
        return (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={focusable ? 0 : -1}
            disabled={o.disabled}
            className={cx("gv-segment", selected && "active")}
            onClick={() => onChange(o.value)}
            onKeyDown={onKeyDown}
          >
            {o.icon && <Icon name={o.icon} size={16} />}
            <span>{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
