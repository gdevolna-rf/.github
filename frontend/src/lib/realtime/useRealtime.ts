"use client";
/**
 * useRealtime(): one WebSocket per logged-in tab, mounted once in <Providers>.
 * - "counters" → setQueryData(counters) (instant badges, ATX-10);
 * - message.new / conversation.read → conversations + inquiries + counters;
 * - notification.new → notifications + counters (+ optional toast);
 * - inquiry.updated → inquiries; booking.updated → bookings;
 * - after every (re)connect counters are refetched from REST (source of truth).
 * Pages subscribe to raw events with useRealtimeEvent("message.new", handler).
 */
import { useEffect, useRef } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { qk } from "@/lib/api/keys";
import type { Counters } from "@/lib/api/types";
import { RealtimeClient, emitRealtime, onRealtime, type RealtimeEvent } from "./client";

export function applyRealtimeEvent(queryClient: QueryClient, event: RealtimeEvent): void {
  switch (event.type) {
    case "counters": {
      const counters = (event as { counters?: Counters }).counters;
      if (counters) queryClient.setQueryData<Counters>(qk.counters, (old) => ({ ...(old ?? counters), ...counters }));
      break;
    }
    case "message.new":
    case "conversation.read":
      queryClient.invalidateQueries({ queryKey: qk.conversations });
      queryClient.invalidateQueries({ queryKey: qk.inquiries });
      queryClient.invalidateQueries({ queryKey: qk.counters });
      break;
    case "notification.new":
      queryClient.invalidateQueries({ queryKey: qk.notifications });
      queryClient.invalidateQueries({ queryKey: qk.counters });
      break;
    case "inquiry.updated":
      queryClient.invalidateQueries({ queryKey: qk.inquiries });
      queryClient.invalidateQueries({ queryKey: qk.counters });
      break;
    case "booking.updated":
      queryClient.invalidateQueries({ queryKey: qk.bookings });
      queryClient.invalidateQueries({ queryKey: qk.counters });
      break;
    default:
      break;
  }
}

export function useRealtime(options: {
  enabled: boolean;
  onNotification?: (n: { title: string; body?: string; link?: string }) => void;
  onUnauthorized?: () => void;
  url?: string;
}) {
  const queryClient = useQueryClient();
  const handlers = useRef(options);
  handlers.current = options;

  useEffect(() => {
    if (!options.enabled || typeof window === "undefined") return;
    const client = new RealtimeClient({
      url: options.url,
      onEvent: (event) => {
        applyRealtimeEvent(queryClient, event);
        if (event.type === "notification.new") {
          const n = (event as { notification?: { title: string; body?: string; link?: string } }).notification;
          if (n) handlers.current.onNotification?.(n);
        }
        emitRealtime(event);
      },
      onOpen: () => {
        queryClient.invalidateQueries({ queryKey: qk.counters });
      },
      onUnauthorized: () => {
        queryClient.invalidateQueries({ queryKey: qk.me });
        handlers.current.onUnauthorized?.();
      },
    });
    client.start();
    const nudge = () => {
      if (document.visibilityState === "visible") client.nudge();
    };
    window.addEventListener("online", nudge);
    document.addEventListener("visibilitychange", nudge);
    return () => {
      window.removeEventListener("online", nudge);
      document.removeEventListener("visibilitychange", nudge);
      client.stop();
    };
  }, [options.enabled, options.url, queryClient]);
}

/** Subscribe a component to one realtime event type while mounted. */
export function useRealtimeEvent(type: RealtimeEvent["type"] | "*", handler: (event: RealtimeEvent) => void) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => onRealtime(type, (e) => ref.current(e)), [type]);
}
