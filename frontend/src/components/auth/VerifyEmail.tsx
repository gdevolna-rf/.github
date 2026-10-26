"use client";
/** /verify-email?token= — confirms the address (5.3, ACC-13); without a token explains and offers a resend. */
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { authApi } from "@/lib/api/auth";
import { qk } from "@/lib/api/keys";
import { useMe } from "@/lib/auth/hooks";
import { routes } from "@/lib/routes";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingState, SuccessState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { AuthCard } from "./AuthCard";

export function VerifyEmail() {
  const params = useSearchParams();
  const token = params.get("token");
  const queryClient = useQueryClient();
  const { me } = useMe();
  const toast = useToast();
  const [state, setState] = useState<{ status: "idle" | "pending" | "done" | "error"; error?: unknown }>({
    status: token ? "pending" : "idle",
  });
  const started = useRef(false);
  const [resending, setResending] = useState(false);

  const confirm = () => {
    if (!token) return;
    setState({ status: "pending" });
    authApi
      .verifyEmail(token)
      .then(() => {
        setState({ status: "done" });
        queryClient.invalidateQueries({ queryKey: qk.me });
      })
      .catch((error) => setState({ status: "error", error }));
  };

  useEffect(() => {
    if (token && !started.current) {
      started.current = true;
      confirm();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const resend = () => {
    setResending(true);
    authApi
      .resendVerification()
      .then(() => toast.success("Письмо отправлено ещё раз — проверьте почту и папку «Спам»"))
      .catch((err) => toast.error(err))
      .finally(() => setResending(false));
  };

  return (
    <AuthCard narrow title="Подтверждение почты">
      {state.status === "pending" && <LoadingState label="Проверяем ссылку…" />}
      {state.status === "done" && (
        <SuccessState
          title="Почта подтверждена"
          text="Спасибо! Теперь доступны заявки, бронирования и отзывы."
          action={{ label: me ? "В личный кабинет" : "Войти", href: me ? routes.account.root : routes.login }}
        />
      )}
      {state.status === "error" && (
        <>
          <ErrorState error={state.error} title="Ссылка не сработала" onRetry={confirm} />
          <p className="gv-auth-lead">Ссылка могла устареть или уже использоваться. Запросите новое письмо.</p>
          {me && (
            <Button variant="pill" icon="mail" onClick={resend} loading={resending}>
              Отправить письмо ещё раз
            </Button>
          )}
        </>
      )}
      {state.status === "idle" && (
        <>
          <p className="gv-auth-lead">
            {params.get("sent")
              ? "Мы отправили письмо со ссылкой для подтверждения. Откройте его на любом устройстве — ссылка действует ограниченное время."
              : "Чтобы подтвердить адрес, откройте ссылку из письма «Гдеволны»."}
          </p>
          {me ? (
            <Button variant="pill" icon="mail" onClick={resend} loading={resending}>
              Отправить письмо ещё раз
            </Button>
          ) : null}
        </>
      )}
    </AuthCard>
  );
}
