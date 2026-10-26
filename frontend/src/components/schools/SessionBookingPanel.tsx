"use client";
/**
 * Booking box of /sessions/{id} (SCH-05, SCH-08, AT-05): live free seats (client refetch — SSR has no cookies and
 * may be cached), «Записаться» while seats are free, the waitlist when the session is full, a notice for
 * cancelled / finished / started sessions. Members of the school and the instructor see no customer actions.
 */
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLoginPrompt } from "@/components/auth/LoginPrompt";
import { BookingButton } from "@/components/learning/BookingDialog";
import { Button, ButtonLink, Icon, StatusBadge, useToast } from "@/components/ui";
import { learningApi, learningKeys, type LessonSession } from "@/lib/api/learning";
import { useMe } from "@/lib/auth/hooks";
import { formatMoney, plural, WORDS } from "@/lib/format";
import { routes } from "@/lib/routes";
import { useHydrated } from "./useHydrated";

export function SessionBookingPanel({ initial, now }: { initial: LessonSession; now?: number }) {
  const { me: viewer, isLoading: meLoading } = useMe();
  const hydrated = useHydrated();
  // the hydration render must match the guest SSR markup
  const me = hydrated ? viewer : null;
  const { prompt } = useLoginPrompt();
  const toast = useToast();
  const queryClient = useQueryClient();
  const key = learningKeys.session(initial.id);
  const query = useQuery({
    queryKey: [...key, viewer?.id ?? "guest"],
    queryFn: () => learningApi.session(initial.id),
    initialData: initial,
    // SSR data has no viewer → refetch right away for the viewer's waitlist entry and fresh seats
    initialDataUpdatedAt: 0,
    staleTime: 15_000,
    refetchInterval: 60_000,
    enabled: !meLoading,
  });
  const session = query.data ?? initial;

  const join = useMutation({
    mutationFn: () => learningApi.joinWaitlist(session.id),
    onSuccess: () => {
      toast.success("Вы в листе ожидания — сообщим, если место освободится");
      void queryClient.invalidateQueries({ queryKey: key });
    },
    onError: (err) => toast.error(err, { action: { label: "Повторить", onClick: () => join.mutate() } }),
  });
  const leave = useMutation({
    mutationFn: () => learningApi.leaveWaitlist(session.id),
    onSuccess: () => {
      toast.success("Вы вышли из листа ожидания");
      void queryClient.invalidateQueries({ queryKey: key });
    },
    onError: (err) => toast.error(err, { action: { label: "Повторить", onClick: () => leave.mutate() } }),
  });

  const memberOrg = Boolean(session.organization && me?.organizations?.some((o) => String(o.id) === String(session.organization?.id)));
  const isInstructor = Boolean(me && session.instructor && session.instructor.id === me.id);
  const own = memberOrg || isInstructor;
  const started = new Date(session.starts_at).getTime() <= (now ?? Date.now());
  const providerName = session.organization?.name ?? session.instructor?.display_name ?? "Инструктор";
  const full = session.is_full || session.free_seats <= 0;
  const entry = session.my_waitlist && ["waiting", "offered"].includes(session.my_waitlist.status) ? session.my_waitlist : null;

  const joinWaitlist = () => {
    if (!me) {
      if (!meLoading) prompt("Чтобы встать в лист ожидания, войдите в аккаунт.");
      return;
    }
    join.mutate();
  };

  let body: ReactNode;
  if (session.status === "cancelled") {
    body = (
      <p className="notice" role="status">
        Занятие отменено{session.cancel_reason ? `: ${session.cancel_reason}` : "."} Посмотрите другие даты.
      </p>
    );
  } else if (session.status !== "scheduled" || started) {
    body = (
      <p className="notice" role="status">
        {session.status === "completed" ? "Занятие уже прошло." : "Занятие уже началось — запись закрыта."} Выберите другую дату.
      </p>
    );
  } else if (own) {
    body = (
      <p className="notice">
        {isInstructor ? "Вы ведёте это занятие." : "Это занятие вашей школы."} Записи и лист ожидания — в кабинете.
        {" "}
        <a href={session.organization ? routes.account.org(session.organization.id) : routes.account.instructor}>Открыть кабинет</a>
      </p>
    );
  } else if (!full) {
    body = (
      <BookingButton
        session={session}
        providerName={providerName}
        block
        label="Записаться на занятие"
        onFull={() => void query.refetch()}
      />
    );
  } else if (entry) {
    body = (
      <div className="gv-waitlist-box" role="status">
        <b>{entry.status === "offered" ? "Освободилось место!" : "Вы в листе ожидания"}</b>
        {entry.status === "offered"
          ? "Школа предложила вам место — проверьте уведомления и подтвердите запись."
          : entry.position
            ? `Ваше место в очереди: ${entry.position}. Сообщим, если кто-то откажется.`
            : "Сообщим, если кто-то откажется."}
        <div className="gv-waitlist-actions">
          <Button variant="danger" size="sm" loading={leave.isPending} onClick={() => leave.mutate()}>
            Покинуть лист ожидания
          </Button>
        </div>
      </div>
    );
  } else {
    body = (
      <>
        <p className="gv-waitlist-box">
          <b>Свободных мест нет</b>
          Встаньте в лист ожидания — если кто-то откажется, место предложат по очереди.
          {session.waitlist_count ? ` Сейчас в очереди: ${session.waitlist_count}.` : ""}
        </p>
        <Button variant="primary" block icon="clock" loading={join.isPending} onClick={joinWaitlist}>
          Встать в лист ожидания
        </Button>
      </>
    );
  }

  return (
    <div className="side-card gv-session-panel" aria-live="polite">
      <div className="spot-title">
        <h2>Запись</h2>
        <StatusBadge domain="session" status={session.status} />
      </div>
      <p className={full ? "gv-seats is-full" : "gv-seats"}>
        {full
          ? `Мест нет · ${session.capacity} из ${session.capacity} заняты`
          : `Свободно ${session.free_seats} ${plural(session.free_seats, WORDS.seat)} из ${session.capacity}`}
      </p>
      {session.price && (
        <p className="gv-program-price">
          {formatMoney(session.price, session.currency || "RUB")} <small className="small">за место</small>
        </p>
      )}
      {body}
      {query.isError && (
        <p className="small" role="alert">
          <Icon name="wifi-off" size={14} /> Не удалось обновить число мест.{" "}
          <Button variant="link" size="sm" onClick={() => void query.refetch()}>
            Повторить
          </Button>
        </p>
      )}
      {session.organization && (
        <ButtonLink href={routes.school(session.organization.slug)} variant="link" iconRight="arrow">
          Все занятия школы
        </ButtonLink>
      )}
    </div>
  );
}
