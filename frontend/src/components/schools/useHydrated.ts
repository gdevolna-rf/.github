"use client";
import { useEffect, useState } from "react";

/**
 * false during SSR and the hydration render, true after mount. Viewer-dependent branches (member? logged in?)
 * must render the server markup first: TanStack Query may already hold `/me` when a streamed boundary hydrates.
 */
export function useHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);
  return hydrated;
}
