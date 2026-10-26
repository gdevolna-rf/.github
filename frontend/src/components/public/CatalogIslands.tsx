"use client";
/** Клиентские действия публичных страниц аренды, GG Surfer, клуба и мерча. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { publicApi, type RentalDetail } from "@/lib/api/publicCatalogs";
import { isApiError } from "@/lib/api/errors";
import { routes } from "@/lib/routes";
import { formatMoney } from "@/lib/format";
import { useMe } from "@/lib/auth/hooks";
import { useRequireAuth } from "@/components/auth/LoginPrompt";
import { Button, StatusBadge, TextInput, useToast } from "@/components/ui";

const errText = (e: unknown, fallback: string) => (isApiError(e) ? e.message : fallback);

/** Бронирование экземпляра (RENT-05): цена считается сервером; пересечение подтверждённых броней → 409. */
export function RentalBookingForm({ item }: { item: Pick<RentalDetail, "id" | "is_own" | "min_rental_hours" | "rental_price_per_day" | "rental_price_per_hour" | "currency"> }) {
  const router = useRouter();
  const requireAuth = useRequireAuth();
  const key = useRef<string | undefined>(undefined);
  const today = new Date().toISOString().slice(0, 10);
  const [from, setFrom] = useState(`${today}T09:00`);
  const [to, setTo] = useState(`${today}T18:00`);
  const book = useMutation({
    mutationFn: () => publicApi.rentalBook(item.id, new Date(from).toISOString(), new Date(to).toISOString(), key.current),
    onSuccess: (b) => router.push(routes.account.booking(b.id)),
    onSettled: (_d, err) => {
      if (!err) key.current = undefined;
    },
  });
  if (item.is_own) return <p className="muted">Это ваше объявление — брони клиентов видны в кабинете проката.</p>;
  return (
    <form
      className="lc-form"
      onSubmit={(e) => {
        e.preventDefault();
        requireAuth(() => {
          key.current ??= crypto.randomUUID();
          book.mutate();
        }, "Чтобы забронировать, войдите в аккаунт.");
      }}
    >
      <div className="lc-form-row">
        <TextInput label="С" type="datetime-local" required value={from} onChange={(e) => setFrom(e.target.value)} />
        <TextInput label="По" type="datetime-local" required value={to} onChange={(e) => setTo(e.target.value)} />
      </div>
      <p className="small muted">
        {item.rental_price_per_hour ? `${formatMoney(item.rental_price_per_hour, item.currency)} / час · ` : ""}
        {item.rental_price_per_day ? `${formatMoney(item.rental_price_per_day, item.currency)} / день · ` : ""}
        минимум {item.min_rental_hours} ч. Итоговую стоимость рассчитает сервер, бронь подтверждает владелец.
      </p>
      {book.isError && (
        <p className="gv-field-error" role="alert">
          {isApiError(book.error) && book.error.code === "resource_taken" ? "Это время уже занято подтверждённой бронью — выберите другие даты." : errText(book.error, "Не удалось забронировать.")}
        </p>
      )}
      <Button type="submit" variant="primary" loading={book.isPending}>
        Забронировать
      </Button>
    </form>
  );
}

export function WriteToSurferButton({ accountId, canMessage, acceptsMessages }: { accountId: string; canMessage: boolean; acceptsMessages: boolean }) {
  const router = useRouter();
  const requireAuth = useRequireAuth();
  const { me } = useMe();
  const toast = useToast();
  const start = useMutation({
    mutationFn: () => publicApi.directConversation(accountId),
    onSuccess: (c) => router.push(`${routes.account.inquiries}?conversation=${c.id}`),
    onError: (e) => toast.error(e),
  });
  if (!acceptsMessages) return <span className="small muted">Не принимает сообщения</span>;
  if (me && !canMessage) return null;
  return (
    <Button variant="primary" icon="chat" loading={start.isPending} onClick={() => requireAuth(() => start.mutate(), "Чтобы написать участнику, войдите в аккаунт.")}>
      Написать
    </Button>
  );
}

export function ClubRegistrationBox({ eventId, slug, isOpen }: { eventId: string; slug: string; isOpen: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const requireAuth = useRequireAuth();
  const { me } = useMe();
  const detail = useQuery({ queryKey: ["club", "event", slug, me?.id ?? "guest"], queryFn: () => publicApi.clubEvent(slug) });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["club", "event", slug] });
  const register = useMutation({
    mutationFn: () => publicApi.clubRegister(eventId),
    onSuccess: (r) => {
      toast.success(r.status === "waitlist" ? "Мест нет — вы в листе ожидания" : "Вы зарегистрированы");
      refresh();
    },
    onError: (e) => toast.error(e),
  });
  const cancel = useMutation({ mutationFn: () => publicApi.clubCancel(eventId), onSuccess: refresh, onError: (e) => toast.error(e) });
  const mine = detail.data?.my_registration;
  if (mine && mine.status !== "cancelled") {
    return (
      <div className="lc-form-actions">
        <StatusBadge domain="eventRegistration" status={mine.status} />
        {mine.waitlist_position ? <span className="small muted">Место в очереди: {mine.waitlist_position}</span> : null}
        <Button variant="link" loading={cancel.isPending} onClick={() => cancel.mutate()}>
          Отменить участие
        </Button>
      </div>
    );
  }
  if (!isOpen) return <p className="muted">Регистрация закрыта.</p>;
  return (
    <Button variant="primary" loading={register.isPending} onClick={() => requireAuth(() => register.mutate(), "Чтобы участвовать, войдите в аккаунт.")}>
      {detail.data?.is_full ? "В лист ожидания" : "Участвовать"}
    </Button>
  );
}

export function ProductInterestButton({ productId, slug }: { productId: string; slug: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const requireAuth = useRequireAuth();
  const { me } = useMe();
  const detail = useQuery({ queryKey: ["shop", slug, me?.id ?? "guest"], queryFn: () => publicApi.product(slug), enabled: Boolean(me) });
  const subscribed = Boolean(detail.data?.my_interest);
  const toggle = useMutation({
    mutationFn: () => (subscribed ? publicApi.productInterestRemove(productId) : publicApi.productInterest(productId)),
    onSuccess: () => {
      toast.success(subscribed ? "Подписка отменена" : "Сообщим, когда товар появится");
      void qc.invalidateQueries({ queryKey: ["shop", slug] });
    },
    onError: (e) => toast.error(e),
  });
  return (
    <Button variant={subscribed ? "line" : "primary"} icon="bell" loading={toggle.isPending} onClick={() => requireAuth(() => toggle.mutate(), "Чтобы получить уведомление, войдите в аккаунт.")}>
      {subscribed ? "Вы подписаны — отменить" : "Сообщить о поступлении"}
    </Button>
  );
}
