"use client";
/**
 * Gate for private screens (/account/*, /moderation, /invites/*): guests are redirected to
 * `/login?next=<current url>`; while `/me` loads a LoadingState is shown; network errors offer a retry.
 * Optional checks render <NoAccess> (the server still enforces every permission — this is UX only).
 *
 *   <RequireAuth>…</RequireAuth>
 *   <RequireAuth staff="moderator">…</RequireAuth>
 *   <RequireAuth specialty="instructor">…</RequireAuth>
 */
import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { loginHref, type Me } from "@/lib/api/auth";
import type { SpecialtyCode, StaffRole } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { SPECIALTY_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { ErrorState, LoadingState, NoAccess } from "@/components/ui/States";

export interface RequireAuthProps {
  children: ReactNode | ((me: Me) => ReactNode);
  /** Server role required (moderator also accepts admin). */
  staff?: StaffRole;
  /** Active specialty required. */
  specialty?: SpecialtyCode;
  fallback?: ReactNode;
}

export function RequireAuth({ children, staff, specialty, fallback }: RequireAuthProps) {
  const { me, isGuest, isLoading, isError, error, refetch } = useMe();
  const router = useRouter();
  const pathname = usePathname() || "/";
  const search = useSearchParams();

  useEffect(() => {
    if (isGuest) {
      const qs = search?.toString();
      router.replace(loginHref(qs ? `${pathname}?${qs}` : pathname));
    }
  }, [isGuest, pathname, search, router]);

  if (isLoading || isGuest) return <>{fallback ?? <LoadingState label={isGuest ? "Переходим ко входу…" : "Проверяем вход…"} />}</>;
  if (isError || !me) return <ErrorState error={error} title="Не удалось проверить вход" onRetry={() => void refetch()} />;

  if (staff) {
    const ok = staff === "moderator" ? me.isModerator : me.staffRoles.includes(staff);
    if (!ok) return <NoAccess text="Раздел доступен только сотрудникам с назначенной серверной ролью." action={{ label: "В кабинет", href: routes.account.root }} />;
  }
  if (specialty && !me.specialties.includes(specialty)) {
    return (
      <NoAccess
        title={`Направление «${SPECIALTY_LABELS[specialty]}» не подключено`}
        text="Подключите направление в разделе «Мои направления» — история и данные аккаунта сохранятся."
        action={{ label: "Мои направления", href: routes.account.specialties }}
      />
    );
  }
  return <>{typeof children === "function" ? children(me) : children}</>;
}
