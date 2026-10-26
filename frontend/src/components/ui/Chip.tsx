"use client";
import { useId, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import { Icon, type IconName } from "./Icon";

/** Static chip (prototype `.chip`): nature/infrastructure features, sizes, filters summary. */
export function Chip({ children, icon, title, className }: { children: ReactNode; icon?: IconName; title?: string; className?: string }) {
  return (
    <span className={cx("chip", className)} title={title}>
      {icon && <Icon name={icon} size={13} />}
      {children}
    </span>
  );
}

export interface ChipOption<T extends string> {
  value: T;
  label: ReactNode;
  icon?: IconName;
  disabled?: boolean;
}

/**
 * Toggle chips (interests, extra specialties, wind directions…). `multiple` → aria-pressed buttons in a
 * labelled group; single → radiogroup semantics. `max` limits multi-select.
 */
export function ChipGroup<T extends string>({
  options,
  value,
  onChange,
  multiple = true,
  label,
  max,
  className,
}: {
  options: ChipOption<T>[];
  value: T[];
  onChange: (value: T[]) => void;
  multiple?: boolean;
  /** Visible group label (also the accessible name). */
  label: ReactNode;
  max?: number;
  className?: string;
}) {
  const toggle = (v: T) => {
    if (!multiple) return onChange(value[0] === v ? [] : [v]);
    if (value.includes(v)) onChange(value.filter((x) => x !== v));
    else if (!max || value.length < max) onChange([...value, v]);
  };
  const labelId = `chips-${useId().replace(/:/g, "")}`;
  return (
    <div className={cx("gv-chip-group", className)}>
      <div id={labelId} className="gv-field-label">
        {label}
      </div>
      <div role={multiple ? "group" : "radiogroup"} aria-labelledby={labelId} className="gv-chip-list">
        {options.map((o) => {
          const on = value.includes(o.value);
          const limitReached = Boolean(multiple && max && !on && value.length >= max);
          return (
            <button
              key={o.value}
              type="button"
              role={multiple ? undefined : "radio"}
              aria-pressed={multiple ? on : undefined}
              aria-checked={multiple ? undefined : on}
              disabled={o.disabled || limitReached}
              className={cx("gv-chip-toggle", on && "on")}
              onClick={() => toggle(o.value)}
            >
              {o.icon && <Icon name={o.icon} size={14} />}
              <span>{o.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
