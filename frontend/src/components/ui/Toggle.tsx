"use client";
import { useId, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import { Icon, type IconName } from "./Icon";

export interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Accessible name when the toggle has no visible label (otherwise use aria-labelledby via ToggleRow). */
  label?: string;
  disabled?: boolean;
  id?: string;
  "aria-labelledby"?: string;
  "aria-describedby"?: string;
  className?: string;
}

/** Switch (UX-07): 58×30 track, 22px knob, role="switch" + aria-checked, 44px touch target. */
export function Toggle({ checked, onChange, label, disabled, id, className, ...aria }: ToggleProps) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={aria["aria-labelledby"] ? undefined : label}
      aria-labelledby={aria["aria-labelledby"]}
      aria-describedby={aria["aria-describedby"]}
      disabled={disabled}
      className={cx("toggle", checked && "on", className)}
      onClick={() => onChange(!checked)}
    />
  );
}

/** Prototype `.toggle-row`: title + description on the left, switch on the right. */
export function ToggleRow({
  title,
  description,
  icon,
  checked,
  onChange,
  disabled,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  icon?: IconName;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={cx("toggle-row", className)}>
      <div>
        <b id={`${id}-t`} className="gv-toggle-title">
          {icon && <Icon name={icon} size={17} />}
          {title}
        </b>
        {description && <p id={`${id}-d`}>{description}</p>}
      </div>
      <Toggle
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        aria-labelledby={`${id}-t`}
        aria-describedby={description ? `${id}-d` : undefined}
      />
    </div>
  );
}
