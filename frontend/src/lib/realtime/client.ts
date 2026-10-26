/**
 * Personal WebSocket channel `ws(s)://<host>/ws/events/` (ARCHITECTURE §2 «WebSocket»).
 * WS is only an accelerator: REST (`GET /me/counters`, lists) stays the source of truth, so after every
 * (re)connect the bridge refetches counters. Framework-free so it can be unit-tested.
 */
import type { Counters } from "@/lib/api/types";

export type RealtimeEvent =
  | { type: "message.new"; conversation_id: string; message: Record<string, unknown> }
  | { type: "conversation.read"; conversation_id: string; account_id: string; last_read_at: string }
  | { type: "notification.new"; notification: { id: string; kind: string; title: string; body?: string; link?: string } }
  | { type: "counters"; counters: Counters }
  | { type: "inquiry.updated"; inquiry_id: string; status: string }
  | { type: "booking.updated"; booking_id: string; status: string }
  | { type: "pong" }
  | { type: string; [key: string]: unknown };

export type RealtimeStatus = "idle" | "connecting" | "open" | "closed";

export interface RealtimeOptions {
  url?: string;
  /** ms between client pings (keeps proxies from closing idle sockets). */
  pingIntervalMs?: number;
  /** backoff: base * 2^attempt, capped, with ±20% jitter. */
  backoffBaseMs?: number;
  backoffMaxMs?: number;
  onEvent: (event: RealtimeEvent) => void;
  onStatus?: (status: RealtimeStatus) => void;
  /** Called after (re)connection — refetch REST state here. */
  onOpen?: (reconnect: boolean) => void;
  /** Server closed with 4401 (session gone) — stop and let the app re-check `/me`. */
  onUnauthorized?: () => void;
  WebSocketImpl?: typeof WebSocket;
}

export function defaultRealtimeUrl(): string {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/events/`;
}

export class RealtimeClient {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private everOpened = false;
  private stopped = true;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private readonly opts: Required<Omit<RealtimeOptions, "onStatus" | "onOpen" | "onUnauthorized" | "WebSocketImpl">> &
    RealtimeOptions;

  constructor(options: RealtimeOptions) {
    // Сначала опции, затем значения по умолчанию: явный `url: undefined` не должен затирать адрес сокета.
    this.opts = {
      ...options,
      url: options.url ?? defaultRealtimeUrl(),
      pingIntervalMs: options.pingIntervalMs ?? 25_000,
      backoffBaseMs: options.backoffBaseMs ?? 1000,
      backoffMaxMs: options.backoffMaxMs ?? 30_000,
    } as RealtimeClient["opts"];
  }

  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    this.clearTimers();
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close(1000, "client stop");
      this.ws = null;
    }
    this.opts.onStatus?.("closed");
  }

  /** Reconnect now (tab became visible / browser back online). */
  nudge(): void {
    if (this.stopped) return;
    if (this.ws && (this.ws.readyState === 0 || this.ws.readyState === 1)) return;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.attempt = 0;
    this.connect();
  }

  get readyState(): number {
    return this.ws?.readyState ?? 3;
  }

  private clearTimers() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.reconnectTimer = null;
    this.pingTimer = null;
  }

  private connect() {
    const Impl = this.opts.WebSocketImpl ?? (typeof WebSocket !== "undefined" ? WebSocket : undefined);
    if (!Impl || !this.opts.url) return;
    this.opts.onStatus?.("connecting");
    let ws: WebSocket;
    try {
      ws = new Impl(this.opts.url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;
    ws.onopen = () => {
      const reconnect = this.everOpened;
      this.everOpened = true;
      this.attempt = 0;
      this.opts.onStatus?.("open");
      this.pingTimer = setInterval(() => this.send({ type: "ping" }), this.opts.pingIntervalMs);
      this.opts.onOpen?.(reconnect);
    };
    ws.onmessage = (msg: MessageEvent) => {
      let data: unknown;
      try {
        data = JSON.parse(typeof msg.data === "string" ? msg.data : "");
      } catch {
        return;
      }
      if (data && typeof data === "object" && "type" in data) this.opts.onEvent(data as RealtimeEvent);
    };
    ws.onclose = (ev: CloseEvent) => {
      if (this.pingTimer) clearInterval(this.pingTimer);
      this.pingTimer = null;
      this.ws = null;
      this.opts.onStatus?.("closed");
      if (this.stopped) return;
      if (ev.code === 4401 || ev.code === 4403) {
        this.stopped = true;
        this.opts.onUnauthorized?.();
        return;
      }
      this.scheduleReconnect();
    };
    ws.onerror = () => {
      /* onclose follows and schedules the reconnect */
    };
  }

  private scheduleReconnect() {
    if (this.stopped) return;
    const base = Math.min(this.opts.backoffMaxMs, this.opts.backoffBaseMs * 2 ** this.attempt);
    const jitter = base * 0.2 * (Math.random() * 2 - 1);
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, Math.max(250, Math.round(base + jitter)));
  }

  send(data: Record<string, unknown>): boolean {
    if (this.ws && this.ws.readyState === 1) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }
}

/* ---- tiny event bus so pages can react to events (chat appends message.new, etc.) ---- */
type Listener = (event: RealtimeEvent) => void;
const listeners = new Map<string, Set<Listener>>();

export function emitRealtime(event: RealtimeEvent): void {
  listeners.get(event.type)?.forEach((l) => l(event));
  listeners.get("*")?.forEach((l) => l(event));
}

/** Subscribe to one event type (or "*"); returns an unsubscribe function. */
export function onRealtime(type: string, listener: Listener): () => void {
  let set = listeners.get(type);
  if (!set) {
    set = new Set();
    listeners.set(type, set);
  }
  set.add(listener);
  return () => set!.delete(listener);
}
