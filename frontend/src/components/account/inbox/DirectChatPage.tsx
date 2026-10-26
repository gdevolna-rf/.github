"use client";
/**
 * Личная переписка GG Surfer (`/account/inquiries?conversation={id}` — так ведут уведомления о сообщениях).
 * Шапка с собеседником, ссылка на его анкету и блокировка (COM-07); сам чат — общий ChatView.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { accountApi, accountKeys } from "@/lib/api/account";
import { inboxApi, inboxKeys } from "@/lib/api/account-inbox";
import { routes } from "@/lib/routes";
import { useMe } from "@/lib/auth/hooks";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { ReasonDialog } from "../shared/ReasonDialog";
import { ChatView } from "./ChatView";

export function DirectChatPage({ conversationId, backHref }: { conversationId: string; backHref: string }) {
  const { me } = useMe();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [blockOpen, setBlockOpen] = useState(false);
  const conversation = useQuery({ queryKey: inboxKeys.conversation(conversationId), queryFn: () => inboxApi.conversation(conversationId) });
  const other = conversation.data?.participants.find((p) => p.account.id !== me?.id)?.account ?? null;
  const name = conversation.data?.counterpart?.name ?? other?.display_name ?? "Собеседник";
  const blocked = conversation.data?.send_blocked_reason === "blocked";

  return (
    <section className="gv-ac-panel acc-thread" aria-labelledby="thread-title">
      <Link href={backHref} className="acc-back">
        <Icon name="arrow-left" size={15} /> Все сообщения
      </Link>
      <header className="acc-thread-head">
        <Avatar media={conversation.data?.counterpart?.avatar ?? other?.avatar ?? null} name={name} size={48} />
        <div className="acc-thread-title">
          <span className="gv-ac-kicker">GG Surfer · личная переписка</span>
          <h2 id="thread-title" className="gv-clamp-2">
            {name}
          </h2>
          {other?.handle && !other.is_deleted && (
            <Link href={routes.surfer(other.handle)} className="acc-thread-link">
              Анкета участника <Icon name="arrow" size={13} />
            </Link>
          )}
        </div>
        {other && !other.is_deleted && !blocked && (
          <button type="button" className="gv-ac-btn danger" onClick={() => setBlockOpen(true)}>
            <Icon name="lock" size={14} /> Заблокировать
          </button>
        )}
      </header>
      <ChatView conversationId={conversationId} kind="direct" />
      {other && (
        <ReasonDialog
          open={blockOpen}
          onClose={() => setBlockOpen(false)}
          title={`Заблокировать ${name}?`}
          description="Вы больше не будете получать сообщения от этого участника. Снять блокировку можно в «Настройки → Блокировки»."
          withReason={false}
          confirmLabel="Заблокировать"
          onConfirm={async () => {
            await accountApi.block(other.id);
            void queryClient.invalidateQueries({ queryKey: inboxKeys.conversation(conversationId) });
            void queryClient.invalidateQueries({ queryKey: accountKeys.blocks });
            toast.success(`${name} заблокирован(а)`);
          }}
        />
      )}
    </section>
  );
}
