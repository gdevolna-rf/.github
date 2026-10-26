"use client";
/**
 * /invites/{token}: the addressee accepts or declines an organization invite (5.3, ACC-11, SCH-09).
 * The role becomes active only after acceptance; the server checks that the invite belongs to this account.
 * Placeholder UI — the organizations engineer can enrich it with invite details from GET /me/invites.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/api/keys";
import { routes } from "@/lib/routes";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { Button } from "@/components/ui/Button";
import { ErrorState, SuccessState } from "@/components/ui/States";
import { AuthCard } from "./AuthCard";

export function InviteResponse({ token }: { token: string }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<{ status: "idle" | "pending" | "accepted" | "declined" | "error"; action?: "accept" | "decline"; error?: unknown }>({
    status: "idle",
  });

  const respond = (action: "accept" | "decline") => {
    setState({ status: "pending", action });
    api
      .post(`invites/${encodeURIComponent(token)}/${action}`)
      .then(() => {
        setState({ status: action === "accept" ? "accepted" : "declined" });
        queryClient.invalidateQueries({ queryKey: qk.me });
        queryClient.invalidateQueries({ queryKey: qk.myInvites });
      })
      .catch((error) => setState({ status: "error", action, error }));
  };

  return (
    <RequireAuth>
      <AuthCard
        narrow
        title="Приглашение в организацию"
        lead="Вас пригласили в команду школы, мастерской или проката на «Гдеволне». Роль начнёт действовать только после того, как вы примете приглашение."
      >
        {state.status === "accepted" && (
          <SuccessState title="Приглашение принято" text="Организация появилась в вашем кабинете." action={{ label: "Открыть организации", href: routes.account.orgs }} />
        )}
        {state.status === "declined" && (
          <SuccessState title="Приглашение отклонено" text="Владелец организации увидит ваш ответ." action={{ label: "В кабинет", href: routes.account.root }} />
        )}
        {state.status === "error" && (
          <ErrorState error={state.error} title="Не получилось ответить на приглашение" onRetry={() => state.action && respond(state.action)} />
        )}
        {(state.status === "idle" || state.status === "pending" || state.status === "error") && (
          <div className="gv-auth-actions">
            <Button variant="pill" onClick={() => respond("decline")} loading={state.status === "pending" && state.action === "decline"} disabled={state.status === "pending"}>
              Отклонить
            </Button>
            <Button variant="primary" iconRight="check" onClick={() => respond("accept")} loading={state.status === "pending" && state.action === "accept"} disabled={state.status === "pending"}>
              Принять приглашение
            </Button>
          </div>
        )}
      </AuthCard>
    </RequireAuth>
  );
}
