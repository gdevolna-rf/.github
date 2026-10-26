"use client";
/**
 * Chat state for one conversation (MSG-03/06/07/10, ATX-09/10):
 * - REST is the source of truth: the latest page (`qk.messages(id)`) + older pages loaded on demand;
 * - realtime `message.new` appends instantly, `conversation.read` updates read receipts; the global bridge also
 *   invalidates the queries, so a missed WS event is repaired by the refetch;
 * - sending is optimistic with a `client_id` (a retry never duplicates a message), failures stay in the log
 *   with «Повторить»;
 * - the conversation is marked read on open and whenever a new incoming message is visible.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { inboxApi, inboxKeys, type ChatMessage, type ConversationDetail } from "@/lib/api/account-inbox";
import { newIdempotencyKey } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { qk } from "@/lib/api/keys";
import type { Counters, Media } from "@/lib/api/types";
import { useRealtimeEvent } from "@/lib/realtime/useRealtime";

export interface PendingMessage {
  clientId: string;
  body: string;
  attachments: Media[];
  /** local object URLs for the previews (revoked when the bubble goes away) */
  previews: string[];
  status: "sending" | "failed";
  error?: string;
  createdAt: string;
}

const time = (v: string | null | undefined) => (v ? Date.parse(v) : 0);

/** Union by id, oldest first (ties by id) — the same message may come from REST, WS and the send response. */
export function mergeMessages(...lists: Array<ReadonlyArray<ChatMessage> | undefined>): ChatMessage[] {
  const byId = new Map<string, ChatMessage>();
  for (const list of lists) for (const m of list ?? []) byId.set(m.id, { ...byId.get(m.id), ...m });
  return Array.from(byId.values()).sort((a, b) => time(a.created_at) - time(b.created_at) || a.id.localeCompare(b.id));
}

/** Latest moment any *other* participant has read up to (read receipts for my messages). */
export function othersReadAt(conversation: ConversationDetail | undefined, meId: string | undefined): number {
  if (!conversation) return 0;
  return conversation.participants
    .filter((p) => p.account.id !== meId)
    .reduce((acc, p) => Math.max(acc, time(p.last_read_at)), 0);
}

export function useChat(conversationId: string, meId: string | undefined) {
  const queryClient = useQueryClient();
  const conversation = useQuery({
    queryKey: inboxKeys.conversation(conversationId),
    queryFn: () => inboxApi.conversation(conversationId),
  });
  const latest = useQuery({
    queryKey: inboxKeys.messages(conversationId),
    queryFn: () => inboxApi.messages(conversationId, { limit: 30 }),
  });
  const [older, setOlder] = useState<{ items: ChatMessage[]; hasMore: boolean; loaded: boolean }>({ items: [], hasMore: false, loaded: false });
  const [olderState, setOlderState] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null });
  const [live, setLive] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState<PendingMessage[]>([]);
  const pendingRef = useRef(pending);
  pendingRef.current = pending;

  // reset when switching conversations
  useEffect(() => {
    setOlder({ items: [], hasMore: false, loaded: false });
    setLive([]);
    setPending([]);
  }, [conversationId]);

  useEffect(
    () => () => {
      pendingRef.current.forEach((p) => p.previews.forEach((u) => URL.revokeObjectURL?.(u)));
    },
    [],
  );

  const dropPending = useCallback((clientId: string) => {
    setPending((list) => {
      const item = list.find((p) => p.clientId === clientId);
      item?.previews.forEach((u) => URL.revokeObjectURL?.(u));
      return list.filter((p) => p.clientId !== clientId);
    });
  }, []);

  useRealtimeEvent("message.new", (e) => {
    if (e.type !== "message.new" || e.conversation_id !== conversationId) return;
    const message = (e as unknown as { message: ChatMessage }).message;
    if (!message?.id) return;
    setLive((l) => mergeMessages(l, [message]));
    if (message.is_mine && message.client_id) dropPending(message.client_id);
  });

  useRealtimeEvent("conversation.read", (e) => {
    if (e.type !== "conversation.read" || e.conversation_id !== conversationId) return;
    const ev = e as { account_id: string; last_read_at: string };
    queryClient.setQueryData<ConversationDetail>(inboxKeys.conversation(conversationId), (old) =>
      old
        ? {
            ...old,
            my_last_read_at: ev.account_id === meId ? ev.last_read_at : old.my_last_read_at,
            participants: old.participants.map((p) =>
              p.account.id === ev.account_id && time(ev.last_read_at) > time(p.last_read_at) ? { ...p, last_read_at: ev.last_read_at } : p,
            ),
          }
        : old,
    );
  });

  const messages = useMemo(() => mergeMessages(older.items, latest.data?.results, live), [older.items, latest.data, live]);
  const visiblePending = useMemo(() => {
    const sentClientIds = new Set(messages.filter((m) => m.is_mine && m.client_id).map((m) => m.client_id));
    return pending.filter((p) => !sentClientIds.has(p.clientId));
  }, [messages, pending]);
  const hasMore = older.loaded ? older.hasMore : Boolean(latest.data?.has_more);

  const loadOlder = useCallback(async () => {
    const first = messages[0];
    if (!first || olderState.loading) return;
    setOlderState({ loading: true, error: null });
    try {
      const page = await inboxApi.messages(conversationId, { before: first.id, limit: 30 });
      setOlder((o) => ({ items: mergeMessages(page.results, o.items), hasMore: page.has_more, loaded: true }));
      setOlderState({ loading: false, error: null });
    } catch (err) {
      setOlderState({ loading: false, error: errorMessage(err) });
    }
  }, [conversationId, messages, olderState.loading]);

  const refreshLists = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["inquiries", "list"] });
    void queryClient.invalidateQueries({ queryKey: ["inquiries", "count"] });
    void queryClient.invalidateQueries({ queryKey: ["conversations", "list"] });
    void queryClient.invalidateQueries({ queryKey: ["conversations", "count"] });
  }, [queryClient]);

  const deliver = useCallback(
    async (item: PendingMessage) => {
      try {
        const message = await inboxApi.send(conversationId, {
          body: item.body,
          attachment_ids: item.attachments.map((a) => a.id),
          client_id: item.clientId,
        });
        setLive((l) => mergeMessages(l, [message]));
        dropPending(item.clientId);
        refreshLists();
      } catch (err) {
        setPending((list) => list.map((p) => (p.clientId === item.clientId ? { ...p, status: "failed", error: errorMessage(err, "Не удалось отправить.") } : p)));
        // closed / blocked conversations: refresh can_send so the composer explains why
        void queryClient.invalidateQueries({ queryKey: inboxKeys.conversation(conversationId), exact: true });
      }
    },
    [conversationId, dropPending, queryClient, refreshLists],
  );

  const send = useCallback(
    (body: string, attachments: Media[], previews: string[] = []) => {
      const item: PendingMessage = {
        clientId: newIdempotencyKey(),
        body: body.trim(),
        attachments,
        previews,
        status: "sending",
        createdAt: new Date().toISOString(),
      };
      setPending((list) => [...list, item]);
      void deliver(item);
    },
    [deliver],
  );

  const retry = useCallback(
    (clientId: string) => {
      const item = pendingRef.current.find((p) => p.clientId === clientId);
      if (!item) return;
      const again = { ...item, status: "sending" as const, error: undefined };
      setPending((list) => list.map((p) => (p.clientId === clientId ? again : p)));
      void deliver(again);
    },
    [deliver],
  );

  /* ---- mark read (MSG-06, ATX-10) ---- */
  const lastIncoming = useMemo(() => [...messages].reverse().find((m) => !m.is_mine), [messages]);
  const readSentFor = useRef<string | null>(null);
  const markRead = useCallback(async () => {
    const conv = conversation.data;
    if (!conv || !lastIncoming) return;
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    const alreadyRead = time(conv.my_last_read_at) >= time(lastIncoming.created_at) && conv.unread_count === 0;
    if (alreadyRead || readSentFor.current === lastIncoming.id) return;
    readSentFor.current = lastIncoming.id;
    try {
      const res = await inboxApi.read(conversationId);
      queryClient.setQueryData<Counters>(qk.counters, (old) => ({ ...(old ?? res.counters), ...res.counters }));
      queryClient.setQueryData<ConversationDetail>(inboxKeys.conversation(conversationId), (old) =>
        old ? { ...old, my_last_read_at: res.last_read_at, unread_count: res.unread_count } : old,
      );
      refreshLists();
    } catch {
      readSentFor.current = null; // try again on the next message / focus
    }
  }, [conversation.data, conversationId, lastIncoming, queryClient, refreshLists]);

  useEffect(() => {
    void markRead();
  }, [markRead]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") void markRead();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [markRead]);

  return {
    conversation,
    latest,
    messages,
    pending: visiblePending,
    hasMore,
    loadOlder,
    olderLoading: olderState.loading,
    olderError: olderState.error,
    send,
    retry,
    discard: dropPending,
    othersReadAt: othersReadAt(conversation.data, meId),
  };
}
