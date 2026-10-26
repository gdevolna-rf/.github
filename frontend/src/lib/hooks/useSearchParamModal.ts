"use client";
/**
 * Deep-linked modal state in the URL (SHP-10, UX-12): `/shapers?profile=volna-boards` opens the profile
 * modal directly; opening pushes a history entry so the Back button closes it; closing removes the param.
 *
 *   const profile = useSearchParamModal("profile");
 *   <button onClick={() => profile.open(slug)}>…</button>
 *   <Modal open={Boolean(profile.value)} onClose={profile.close} title="…">…</Modal>
 *
 * Needs a <Suspense> boundary above the component (useSearchParams) on statically rendered pages.
 */
import { useCallback, useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export function useSearchParamModal(key: string) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const pushed = useRef(false);
  const value = params.get(key);

  const build = useCallback(
    (next: string | null) => {
      const p = new URLSearchParams(params.toString());
      if (next === null) p.delete(key);
      else p.set(key, next);
      const qs = p.toString();
      return qs ? `${pathname}?${qs}` : pathname;
    },
    [params, pathname, key],
  );

  const open = useCallback(
    (next: string) => {
      pushed.current = true;
      router.push(build(next), { scroll: false });
    },
    [router, build],
  );

  const close = useCallback(() => {
    if (pushed.current && typeof window !== "undefined" && window.history.length > 1) {
      pushed.current = false;
      router.back();
    } else {
      router.replace(build(null), { scroll: false });
    }
  }, [router, build]);

  return { value, isOpen: value !== null, open, close };
}
