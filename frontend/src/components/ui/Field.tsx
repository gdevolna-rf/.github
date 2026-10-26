"use client";
/**
 * Labelled form controls (UX-14 / WCAG 2.2 AA): every control has a visible <label>, hint and error are
 * linked with aria-describedby, errors set aria-invalid and are announced (role="alert").
 * Styling: `.gv-field` (labels 12px/700, inputs radius 9–10, focus ring) — see app.css.
 */
import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cx } from "@/lib/cx";

export interface FieldOwnProps {
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  /** Visually hide the label (it stays for screen readers). Use only when the context labels the field visibly. */
  hideLabel?: boolean;
  className?: string;
}

export function useFieldIds(id: string | undefined, hint?: unknown, error?: unknown) {
  const auto = useId();
  const fieldId = id ?? `f${auto.replace(/:/g, "")}`;
  const hintId = hint ? `${fieldId}-hint` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return { fieldId, hintId, errorId, describedBy };
}

/** Wrapper for custom controls: pass the same `id` to your control and `aria-describedby={describedBy}`. */
export function Field({
  id,
  label,
  hint,
  error,
  required,
  hideLabel,
  className,
  children,
}: FieldOwnProps & { id: string; children: ReactNode }) {
  return (
    <div className={cx("gv-field", error && "has-error", className)}>
      <label htmlFor={id} className={cx("gv-field-label", hideLabel && "sr-only")}>
        {label}
        {required && (
          <span className="gv-req" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </label>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="gv-field-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="gv-field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export type TextInputProps = FieldOwnProps & Omit<InputHTMLAttributes<HTMLInputElement>, "className"> & { inputClassName?: string };

export function TextInput({ id, label, hint, error, required, hideLabel, className, inputClassName, ...input }: TextInputProps) {
  const { fieldId, describedBy } = useFieldIds(id, hint, error);
  return (
    <Field id={fieldId} label={label} hint={hint} error={error} required={required} hideLabel={hideLabel} className={className}>
      <input
        id={fieldId}
        className={cx("gv-input", inputClassName)}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...input}
      />
    </Field>
  );
}

export type TextareaProps = FieldOwnProps & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className"> & { showCounter?: boolean };

export function Textarea({ id, label, hint, error, required, hideLabel, className, showCounter = true, maxLength, value, ...rest }: TextareaProps) {
  const { fieldId, describedBy } = useFieldIds(id, hint, error);
  const length = typeof value === "string" ? value.length : 0;
  return (
    <Field
      id={fieldId}
      label={label}
      hint={hint}
      error={error}
      required={required}
      hideLabel={hideLabel}
      className={className}
    >
      <textarea
        id={fieldId}
        className="gv-input gv-textarea"
        required={required}
        maxLength={maxLength}
        value={value}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      />
      {showCounter && maxLength ? (
        <span className="gv-field-counter" aria-live="polite">
          {length} / {maxLength}
        </span>
      ) : null}
    </Field>
  );
}

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export type SelectProps = FieldOwnProps &
  Omit<SelectHTMLAttributes<HTMLSelectElement>, "className"> & {
    options: SelectOption[];
    /** First empty option, e.g. «Все регионы» or «Выберите регион». */
    placeholder?: string;
    /** `filter` = borderless select inside a prototype `.filter` tile. */
    appearance?: "field" | "filter";
  };

/**
 * Native select with the single thin chevron and a reserved 32px on the right, so «Все регионы» is never
 * covered by the arrow (UX-06, ATX-20). Long values end with an ellipsis instead of overlapping.
 */
export function Select({ id, label, hint, error, required, hideLabel, className, options, placeholder, appearance = "field", ...rest }: SelectProps) {
  const { fieldId, describedBy } = useFieldIds(id, hint, error);
  return (
    <Field id={fieldId} label={label} hint={hint} error={error} required={required} hideLabel={hideLabel} className={className}>
      <select
        id={fieldId}
        className={cx("gv-select", appearance === "filter" && "gv-select-filter")}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function Checkbox({
  id,
  label,
  description,
  error,
  className,
  ...input
}: { label: ReactNode; description?: ReactNode; error?: string | null; className?: string } & Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "className">) {
  const { fieldId, describedBy, errorId } = useFieldIds(id, description, error);
  return (
    <div className={cx("gv-check", error && "has-error", className)}>
      <input id={fieldId} type="checkbox" aria-invalid={error ? true : undefined} aria-describedby={describedBy} {...input} />
      <label htmlFor={fieldId}>
        <span className="gv-check-label">{label}</span>
        {description && (
          <span id={`${fieldId}-hint`} className="gv-field-hint">
            {description}
          </span>
        )}
      </label>
      {error && (
        <p id={errorId} className="gv-field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
