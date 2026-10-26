import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { LessonSession } from "@/lib/api/learning";
import { CSRF_OK, GUEST_403, json, mockApi, RAW_ME, renderWithProviders } from "@/test/utils";
import { SessionBookingPanel } from "./SessionBookingPanel";

const ID = "11111111-2222-3333-4444-555555555555";
const FUTURE = "2099-10-22T10:00:00+10:00";

function session(extra: Partial<LessonSession> = {}): LessonSession {
  return {
    id: ID,
    kind: "school",
    title: "Первое знакомство с волной",
    status: "scheduled",
    starts_at: FUTURE,
    ends_at: "2099-10-22T11:30:00+10:00",
    timezone: "Asia/Kamchatka",
    capacity: 4,
    seats_taken: 4,
    free_seats: 0,
    is_full: true,
    price: "4500.00",
    currency: "RUB",
    program: null,
    offer: null,
    organization: { id: "school-1", slug: "kamchatka-surf-school", name: "Kamchatka Surf School", kind: "school" },
    instructor: null,
    spot: null,
    reschedule_reason: "",
    cancel_reason: "",
    my_waitlist: null,
    waitlist_count: 2,
    ...extra,
  };
}

const SESSION_URL = `GET /api/v1/sessions/${ID}`;
const WAITLIST_URL = `/api/v1/sessions/${ID}/waitlist`;

describe("SessionBookingPanel (SCH-08)", () => {
  it("asks a guest to log in before joining the waitlist", async () => {
    mockApi({ "GET /api/v1/me": GUEST_403, [SESSION_URL]: () => json(session()) });
    renderWithProviders(<SessionBookingPanel initial={session()} />);
    expect(screen.getByText("Свободных мест нет")).toBeInTheDocument();
    const join = await screen.findByRole("button", { name: /Встать в лист ожидания/ });
    await waitFor(() => expect(join).toBeEnabled());
    await userEvent.click(join);
    expect(await screen.findByRole("dialog", { name: "Нужен вход в аккаунт" })).toBeInTheDocument();
  });

  it("joins the waitlist and shows the position from the refreshed session", async () => {
    let joined = false;
    const api = mockApi({
      "GET /api/v1/me": () => json(RAW_ME),
      "GET /api/v1/auth/csrf": CSRF_OK,
      [SESSION_URL]: () =>
        json(session(joined ? { my_waitlist: { id: "w1", status: "waiting", position: 3, created_at: FUTURE } } : {})),
      [`POST ${WAITLIST_URL}`]: () => {
        joined = true;
        return json({ id: "w1", session_id: ID, status: "waiting", position: 3, created_at: FUTURE }, 201);
      },
    });
    renderWithProviders(<SessionBookingPanel initial={session()} />);
    await waitFor(() => expect(api.calls(SESSION_URL).length).toBeGreaterThan(0));
    await userEvent.click(await screen.findByRole("button", { name: /Встать в лист ожидания/ }));
    expect(await screen.findByText("Вы в листе ожидания")).toBeInTheDocument();
    expect(screen.getByText(/Ваше место в очереди: 3/)).toBeInTheDocument();
    expect(api.calls(`POST ${WAITLIST_URL}`)).toHaveLength(1);
  });

  it("leaves the waitlist", async () => {
    let inList = true;
    const api = mockApi({
      "GET /api/v1/me": () => json(RAW_ME),
      "GET /api/v1/auth/csrf": CSRF_OK,
      [SESSION_URL]: () =>
        json(session(inList ? { my_waitlist: { id: "w1", status: "waiting", position: 1, created_at: FUTURE } } : {})),
      [`DELETE ${WAITLIST_URL}`]: () => {
        inList = false;
        return new Response(null, { status: 204 });
      },
    });
    renderWithProviders(<SessionBookingPanel initial={session()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Покинуть лист ожидания" }));
    expect(await screen.findByRole("button", { name: /Встать в лист ожидания/ })).toBeInTheDocument();
    expect(api.calls(`DELETE ${WAITLIST_URL}`)).toHaveLength(1);
  });

  it("offers booking while seats are free", async () => {
    mockApi({ "GET /api/v1/me": () => json(RAW_ME), [SESSION_URL]: () => json(session({ free_seats: 2, seats_taken: 2, is_full: false })) });
    renderWithProviders(<SessionBookingPanel initial={session({ free_seats: 2, seats_taken: 2, is_full: false })} />);
    expect(await screen.findByRole("button", { name: /Записаться на занятие/ })).toBeInTheDocument();
    expect(screen.getByText(/Свободно 2 места из 4/)).toBeInTheDocument();
  });

  it("shows a notice instead of booking for cancelled sessions", async () => {
    const cancelled = session({ status: "cancelled", cancel_reason: "шторм", free_seats: 4, is_full: false });
    mockApi({ "GET /api/v1/me": GUEST_403, [SESSION_URL]: () => json(cancelled) });
    renderWithProviders(<SessionBookingPanel initial={cancelled} />);
    expect(screen.getByText(/Занятие отменено: шторм/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Записаться/ })).not.toBeInTheDocument();
  });

  it("hides customer actions from members of the school", async () => {
    const own = session({ organization: { id: "org-1", slug: "kb", name: "Kamchatka Boards", kind: "school" }, free_seats: 3, is_full: false });
    mockApi({ "GET /api/v1/me": () => json(RAW_ME), [SESSION_URL]: () => json(own) });
    renderWithProviders(<SessionBookingPanel initial={own} />);
    expect(await screen.findByText(/Это занятие вашей школы/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Записаться/ })).not.toBeInTheDocument();
  });
});
