"use client";
/**
 * Labelled filter controls bound to one URL query param each (UX-14: visible labels; UX-06: Select keeps room
 * for the chevron). Text/number inputs are debounced so typing does not fire a request per key.
 * Must be rendered inside <CatalogNavProvider>.
 */
import { useEffect, useRef, useState } from "react";
import { Checkbox, Select, TextInput, type SelectOption } from "@/components/ui";
import { useCatalogNav } from "./CatalogNav";

const DEBOUNCE_MS = 450;

function useDebouncedParam(name: string) {
  const nav = useCatalogNav();
  const urlValue = nav.params.get(name) ?? "";
  const [value, setValue] = useState(urlValue);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSent = useRef(urlValue);

  // the URL changed from outside (reset, back button) → show it
  useEffect(() => {
    if (urlValue !== lastSent.current) {
      lastSent.current = urlValue;
      setValue(urlValue);
    }
  }, [urlValue]);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const commit = (next: string) => {
    if (timer.current) clearTimeout(timer.current);
    const trimmed = next.trim();
    if (trimmed === lastSent.current) return;
    lastSent.current = trimmed;
    nav.setParams({ [name]: trimmed });
  };

  const change = (next: string) => {
    setValue(next);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => commit(next), DEBOUNCE_MS);
  };

  return { value, change, commit };
}

export function SearchParamInput({
  name = "q",
  label,
  placeholder,
  type = "search",
  inputMode,
  className,
  min,
  max,
}: {
  name?: string;
  label: string;
  placeholder?: string;
  type?: "search" | "number" | "text";
  inputMode?: "numeric" | "decimal" | "search";
  className?: string;
  min?: number;
  max?: number;
}) {
  const { value, change, commit } = useDebouncedParam(name);
  return (
    <TextInput
      label={label}
      type={type}
      name={name}
      value={value}
      placeholder={placeholder}
      inputMode={inputMode}
      min={min}
      max={max}
      autoComplete="off"
      className={className}
      onChange={(e) => change(e.target.value)}
      onBlur={(e) => commit(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          commit((e.target as HTMLInputElement).value);
        }
      }}
    />
  );
}

export function ParamSelect({
  name,
  label,
  options,
  placeholder,
  className,
}: {
  name: string;
  label: string;
  options: SelectOption[];
  /** Label of the empty «all» option. */
  placeholder?: string;
  className?: string;
}) {
  const nav = useCatalogNav();
  const value = nav.params.get(name) ?? "";
  // keep an unknown value from a shared link visible instead of silently showing «Все»
  const list = value && !options.some((o) => o.value === value) ? [...options, { value, label: value }] : options;
  return (
    <Select
      label={label}
      name={name}
      value={value}
      placeholder={placeholder}
      options={list}
      className={className}
      onChange={(e) => nav.setParams({ [name]: e.target.value })}
    />
  );
}

export function ParamCheckbox({ name, label, description, className }: { name: string; label: string; description?: string; className?: string }) {
  const nav = useCatalogNav();
  const checked = nav.params.get(name) === "true";
  return (
    <Checkbox
      label={label}
      description={description}
      name={name}
      checked={checked}
      className={className}
      onChange={(e) => nav.setParams({ [name]: e.target.checked ? "true" : null })}
    />
  );
}

/** Number of active params among `keys` (badge on «Ещё фильтры», «Сбросить» visibility). */
export function useActiveFilterCount(keys: readonly string[]): number {
  const nav = useCatalogNav();
  return keys.filter((k) => (nav.params.get(k) ?? "") !== "").length;
}
