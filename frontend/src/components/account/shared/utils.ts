"use client";
/**
 * Small helpers shared by the account screens (fe-account). Kept inside the domain folder on purpose:
 * shared foundation files (lib/format.ts, lib/routes.ts…) are owned by the lead.
 */
import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { DEFAULT_TIME_ZONE } from "@/lib/format";
import { routes } from "@/lib/routes";
import type { Me } from "@/lib/api/auth";

/** The viewer's own zone, named explicitly (chat timestamps are «my local time»). */
export function viewerTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || DEFAULT_TIME_ZONE;
  } catch {
    return DEFAULT_TIME_ZONE;
  }
}

/**
 * URL-backed filter state: `get(name)` reads `?name=`, `set({a: "1", b: null})` replaces the URL (no history
 * entry, no scroll jump) so filters are shareable and survive reloads (NAV-05).
 */
export function useUrlState() {
  const params = useSearchParams();
  const pathname = usePathname() || "/";
  const router = useRouter();
  const search = params?.toString() ?? "";

  const get = useCallback((name: string) => new URLSearchParams(search).get(name) ?? "", [search]);

  const hrefWith = useCallback(
    (patch: Record<string, string | null | undefined>) => {
      const next = new URLSearchParams(search);
      for (const [k, v] of Object.entries(patch)) {
        if (v === null || v === undefined || v === "") next.delete(k);
        else next.set(k, v);
      }
      const qs = next.toString();
      return qs ? `${pathname}?${qs}` : pathname;
    },
    [pathname, search],
  );

  const set = useCallback(
    (patch: Record<string, string | null | undefined>, mode: "replace" | "push" = "replace") => {
      const href = hrefWith(patch);
      if (mode === "push") router.push(href, { scroll: false });
      else router.replace(href, { scroll: false });
    },
    [hrefWith, router],
  );

  return useMemo(() => ({ get, set, hrefWith, search }), [get, set, hrefWith, search]);
}

/** Does the account work as a provider somewhere (instructor / shaper / rental / organization member)? */
export function isProvider(me: Me | null | undefined): boolean {
  if (!me) return false;
  return (
    me.specialties.some((s) => s === "instructor" || s === "shaper" || s === "rental") || me.organizations.length > 0
  );
}

/** Public page of the account (ACC-08 «Посмотреть на сайте»). */
export function publicProfileHref(me: Me): { href: string | null; reason?: string } {
  if (!me.handle) return { href: null, reason: "У профиля пока нет адреса." };
  if (me.ggSurferEnabled) return { href: routes.surfer(me.handle) };
  if (me.instructorProfile?.status === "published") return { href: routes.instructor(me.handle) };
  return {
    href: null,
    reason: "Публичная анкета появится, когда вы включите GG Surfer в настройках или опубликуете карточку инструктора.",
  };
}

/** «Вы: …» prefix for own last messages, «📎 Фото» stays as sent by the server. */
export function previewText(last: { body: string; is_mine: boolean; kind: string } | null | undefined): string {
  if (!last) return "Сообщений пока нет";
  const body = last.body?.trim() || "Фото";
  if (last.kind === "system") return body;
  return last.is_mine ? `Вы: ${body}` : body;
}

/** YYYY-MM-DD for <input type="date"> in the viewer's zone. */
export function todayIso(timeZone = viewerTimeZone()): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  return parts;
}

export function age(birthDate: string | null | undefined, now = new Date()): number | null {
  if (!birthDate) return null;
  const [y, m, d] = birthDate.split("-").map(Number);
  if (!y || !m || !d) return null;
  let years = now.getFullYear() - y;
  const beforeBirthday = now.getMonth() + 1 < m || (now.getMonth() + 1 === m && now.getDate() < d);
  if (beforeBirthday) years -= 1;
  return years;
}
