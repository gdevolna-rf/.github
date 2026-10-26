"use client";
/**
 * Guest gating for actions (favourite, book, message, review, rental request): instead of silently failing,
 * show «Нужен вход» with links that bring the user back (`?next=` current URL).
 *
 *   const requireAuth = useRequireAuth();
 *   onClick={() => requireAuth(() => book(), "Чтобы записаться на занятие, войдите в аккаунт.")}
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { loginHref, safeNext } from "@/lib/api/auth";
import { useMe } from "@/lib/auth/hooks";
import { ButtonLink } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";

interface PromptState {
  reason: string;
  next?: string;
}

interface LoginPromptApi {
  prompt: (reason?: string, next?: string) => void;
}

const Ctx = createContext<LoginPromptApi | null>(null);

const DEFAULT_REASON = "Войдите или создайте аккаунт — это бесплатно и займёт минуту.";

export function LoginPromptProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PromptState | null>(null);
  const pathname = usePathname();
  const prompt = useCallback((reason?: string, next?: string) => setState({ reason: reason ?? DEFAULT_REASON, next }), []);
  const api = useMemo(() => ({ prompt }), [prompt]);
  const currentUrl = () =>
    typeof window !== "undefined" ? `${window.location.pathname}${window.location.search}` : pathname;
  const next = state ? safeNext(state.next ?? currentUrl(), "/") : "/";
  return (
    <Ctx.Provider value={api}>
      {children}
      <Modal
        open={Boolean(state)}
        onClose={() => setState(null)}
        title="Нужен вход в аккаунт"
        description={state?.reason}
        footer={
          <>
            <ButtonLink href={`/register?next=${encodeURIComponent(next)}`} variant="pill" onClick={() => setState(null)}>
              Создать аккаунт
            </ButtonLink>
            <ButtonLink href={loginHref(next)} variant="primary" iconRight="arrow" onClick={() => setState(null)} data-autofocus="">
              Войти
            </ButtonLink>
          </>
        }
      />
    </Ctx.Provider>
  );
}

export function useLoginPrompt(): LoginPromptApi {
  return useContext(Ctx) ?? { prompt: () => {} };
}

/** Run `action` for logged-in users; show the login prompt to guests. */
export function useRequireAuth() {
  const { me, isLoading } = useMe();
  const { prompt } = useLoginPrompt();
  return useCallback(
    (action: () => void, reason?: string) => {
      if (me) action();
      else if (!isLoading) prompt(reason);
    },
    [me, isLoading, prompt],
  );
}
