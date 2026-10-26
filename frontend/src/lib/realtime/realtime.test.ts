import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { qk } from "@/lib/api/keys";
import { RealtimeClient, onRealtime, emitRealtime } from "./client";
import { applyRealtimeEvent } from "./useRealtime";

class FakeWS {
  static instances: FakeWS[] = [];
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    FakeWS.instances.push(this);
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  message(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
  send(d: string) {
    this.sent.push(d);
  }
  close(code = 1006) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

afterEach(() => {
  vi.useRealTimers();
  FakeWS.instances = [];
});

describe("RealtimeClient", () => {
  it("delivers events, pings and reconnects with backoff; re-syncs REST on reconnect", () => {
    vi.useFakeTimers();
    const events: unknown[] = [];
    const onOpen = vi.fn();
    const client = new RealtimeClient({
      url: "ws://x/ws/events/",
      WebSocketImpl: FakeWS as unknown as typeof WebSocket,
      onEvent: (e) => events.push(e),
      onOpen,
      pingIntervalMs: 1000,
      backoffBaseMs: 1000,
    });
    client.start();
    const ws = FakeWS.instances[0];
    ws.open();
    expect(onOpen).toHaveBeenLastCalledWith(false);
    ws.message({ type: "counters", counters: { unread_messages: 2 } });
    expect(events).toEqual([{ type: "counters", counters: { unread_messages: 2 } }]);
    vi.advanceTimersByTime(1000);
    expect(ws.sent).toContain(JSON.stringify({ type: "ping" }));

    ws.close(1006);
    expect(FakeWS.instances).toHaveLength(1);
    vi.advanceTimersByTime(1300); // 1 s ± 20 % jitter
    expect(FakeWS.instances).toHaveLength(2);
    FakeWS.instances[1].open();
    expect(onOpen).toHaveBeenLastCalledWith(true);
    client.stop();
  });

  it("stops on 4401 (session gone) and reports it", () => {
    vi.useFakeTimers();
    const onUnauthorized = vi.fn();
    const client = new RealtimeClient({ url: "ws://x", WebSocketImpl: FakeWS as unknown as typeof WebSocket, onEvent: () => {}, onUnauthorized });
    client.start();
    FakeWS.instances[0].close(4401);
    vi.advanceTimersByTime(60_000);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(FakeWS.instances).toHaveLength(1);
  });

  it("event bus delivers to type and wildcard subscribers", () => {
    const a = vi.fn();
    const b = vi.fn();
    const offA = onRealtime("message.new", a);
    const offB = onRealtime("*", b);
    emitRealtime({ type: "message.new", conversation_id: "c1", message: {} });
    emitRealtime({ type: "booking.updated", booking_id: "b1", status: "confirmed" });
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(2);
    offA();
    offB();
  });
});

describe("applyRealtimeEvent", () => {
  it("writes counters and invalidates the affected queries", () => {
    const qc = new QueryClient();
    qc.setQueryData(qk.counters, { unread_messages: 0, unread_notifications: 0, new_inquiries: 0, pending_bookings: 0 });
    applyRealtimeEvent(qc, { type: "counters", counters: { unread_messages: 4, unread_notifications: 1, new_inquiries: 0, pending_bookings: 2 } });
    expect(qc.getQueryData(qk.counters)).toEqual({ unread_messages: 4, unread_notifications: 1, new_inquiries: 0, pending_bookings: 2 });

    const spy = vi.spyOn(qc, "invalidateQueries");
    applyRealtimeEvent(qc, { type: "message.new", conversation_id: "c1", message: {} });
    expect(spy).toHaveBeenCalledWith({ queryKey: qk.conversations });
    expect(spy).toHaveBeenCalledWith({ queryKey: qk.counters });
    applyRealtimeEvent(qc, { type: "booking.updated", booking_id: "b", status: "confirmed" });
    expect(spy).toHaveBeenCalledWith({ queryKey: qk.bookings });
    applyRealtimeEvent(qc, { type: "inquiry.updated", inquiry_id: "i", status: "in_progress" });
    expect(spy).toHaveBeenCalledWith({ queryKey: qk.inquiries });
  });
});

describe("RealtimeClient url", () => {
  it("uses the default /ws/events/ URL when url is passed as undefined", () => {
    const created: string[] = [];
    class FakeWS {
      readyState = 0;
      onopen: (() => void) | null = null;
      onmessage: ((m: MessageEvent) => void) | null = null;
      onclose: ((e: CloseEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(url: string) {
        created.push(url);
      }
      send() {}
      close() {}
    }
    const client = new RealtimeClient({ url: undefined, onEvent: () => {}, WebSocketImpl: FakeWS as unknown as typeof WebSocket });
    client.start();
    expect(created).toEqual([`ws://${window.location.host}/ws/events/`]);
    client.stop();
  });
});
