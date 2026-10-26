"use client";
/**
 * «Обращения» — единый inbox (8.6, MSG-01/02/06/07, SHO-02/03, ATX-27): вкладки Входящие / Исходящие / Личные
 * сообщения (GG Surfer), фильтры роли, организации и статуса из URL (`?box=&role=&organization=&status=`,
 * ссылки из уведомлений и кабинетов), непрочитанные — реальные сообщения по read-курсорам. `?conversation=`
 * открывает личную переписку. Компактная строка показателей допустима здесь (MET-02).
 */
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { inboxApi, inboxKeys, type InboxBox, type InquiryListQuery, type InquiryRoleFilter } from "@/lib/api/account-inbox";
import { pageFromUrl } from "@/lib/api/client";
import { useCounters, useMe } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { plural } from "@/lib/format";
import { STATUS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { StatStrip } from "@/components/ui/StatStrip";
import { EmptyState, ErrorState, LoadingState, NoAccess } from "@/components/ui/States";
import { NavTabs } from "@/components/ui/Tabs";
import { isApiError } from "@/lib/api/errors";
import { ROLE_FILTER_LABELS } from "../shared/options";
import { isProvider, useUrlState } from "../shared/utils";
import { DirectChatPage } from "./DirectChatPage";
import { ConversationRow, InquiryRow } from "./InboxRows";

type Tab = InboxBox | "direct";
const ROLE_VALUES: InquiryRoleFilter[] = ["instructor", "shaper", "school", "rental"];

function useCount(key: readonly unknown[], fn: () => Promise<{ count: number }>, enabled = true) {
  return useQuery({ queryKey: key, queryFn: fn, enabled, staleTime: 15_000, select: (d) => d.count }).data ?? 0;
}

export function InboxPage() {
  const { me } = useMe();
  const counters = useCounters();
  const url = useUrlState();
  const conversationId = url.get("conversation");
  const provider = isProvider(me);

  const rawBox = url.get("box");
  const rawRole = url.get("role") as InquiryRoleFilter | "";
  // `?role=customer` from links = outgoing; any pro role = incoming
  const tab: Tab =
    rawBox === "incoming" || rawBox === "outgoing" || rawBox === "direct"
      ? (rawBox as Tab)
      : rawRole === "customer"
        ? "outgoing"
        : rawRole || url.get("organization")
          ? "incoming"
          : provider
            ? "incoming"
            : "outgoing";
  const role = tab === "incoming" && ROLE_VALUES.includes(rawRole as InquiryRoleFilter) ? (rawRole as InquiryRoleFilter) : undefined;
  const status = url.get("status");
  const organization = tab === "incoming" ? url.get("organization") : "";
  const unreadOnly = url.get("unread") === "1";

  const query: InquiryListQuery = useMemo(
    () => ({ box: tab === "direct" ? undefined : tab, role, status: status || undefined, organization: organization || undefined, unread: unreadOnly || undefined }),
    [tab, role, status, organization, unreadOnly],
  );

  const list = useInfiniteQuery({
    queryKey: inboxKeys.list(query),
    queryFn: ({ pageParam }) => inboxApi.list({ ...query, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (last) => pageFromUrl(last.next),
    enabled: tab !== "direct" && !conversationId,
  });
  const direct = useInfiniteQuery({
    queryKey: [...inboxKeys.directList, unreadOnly],
    queryFn: ({ pageParam }) => inboxApi.conversations({ kind: "direct", unread: unreadOnly, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (last) => pageFromUrl(last.next),
    enabled: tab === "direct" && !conversationId,
  });

  const unreadIncoming = useCount(inboxKeys.count({ box: "incoming", unread: true }), () => inboxApi.list({ box: "incoming", unread: true, page_size: 1 }), provider);
  const unreadOutgoing = useCount(inboxKeys.count({ box: "outgoing", unread: true }), () => inboxApi.list({ box: "outgoing", unread: true, page_size: 1 }));
  const unreadDirect = useCount(inboxKeys.directCount, () => inboxApi.conversations({ kind: "direct", unread: true, page_size: 1 }));
  const inWork = useCount(inboxKeys.count({ box: "incoming", status: "in_progress" }), () => inboxApi.list({ box: "incoming", status: "in_progress", page_size: 1 }), provider);

  if (!me) return <LoadingState label="Загружаем обращения…" />;
  if (conversationId) return <DirectChatPage conversationId={conversationId} backHref={url.hrefWith({ conversation: null, box: "direct" })} />;

  // role chips only for the roles this account actually has
  const kinds = new Set(me.organizations.map((o) => o.kind));
  const myRoles = ROLE_VALUES.filter(
    (r) =>
      (r === "instructor" && me.specialties.includes("instructor")) ||
      (r === "shaper" && (me.specialties.includes("shaper") || kinds.has("workshop"))) ||
      (r === "school" && kinds.has("school")) ||
      (r === "rental" && (me.specialties.includes("rental") || kinds.has("rental"))),
  );
  const orgOptions = me.organizations.map((o) => ({ value: o.id, label: o.name }));
  const statusOptions = Object.entries(STATUS.inquiry).map(([value, def]) => ({ value, label: def.label }));
  const filtered = Boolean(role || status || organization || unreadOnly);
  const resetFilters = () => url.set({ role: null, status: null, organization: null, unread: null });

  const tabHref = (t: Tab) => `${routes.account.inquiries}?box=${t}`;
  const tabs = [
    ...(provider || tab === "incoming" ? [{ href: tabHref("incoming"), label: "Входящие", badge: unreadIncoming }] : []),
    { href: tabHref("outgoing"), label: "Мои заявки", badge: unreadOutgoing },
    { href: tabHref("direct"), label: "Личные сообщения", badge: unreadDirect },
  ];

  const rows = list.data?.pages.flatMap((p) => p.results) ?? [];
  const directRows = direct.data?.pages.flatMap((p) => p.results) ?? [];
  const active = tab === "direct" ? direct : list;
  const total = tab === "direct" ? (direct.data?.pages[0]?.count ?? 0) : (list.data?.pages[0]?.count ?? 0);

  return (
    <section className="gv-ac-panel acc-inbox" aria-labelledby="inbox-title">
      <h2 id="inbox-title">Обращения</h2>
      <p className="gv-ac-desc">
        Заявки и переписка в одном месте: входящие по вашим направлениям, ваши собственные заявки и личные сообщения GG
        Surfer. Писать можно сразу после заявки — даже до ответа исполнителя.
      </p>
      <StatStrip
        ariaLabel="Обращения: что требует внимания"
        items={[
          { label: "Непрочитанных сообщений", value: counters.unread_messages, tone: counters.unread_messages ? "accent" : "muted" },
          ...(provider
            ? [
                { label: "Новых входящих", value: counters.new_inquiries, tone: counters.new_inquiries ? ("accent" as const) : ("muted" as const) },
                { label: "В работе", value: inWork, tone: "default" as const },
              ]
            : []),
        ]}
      />

      <NavTabs ariaLabel="Папки обращений" current={tabHref(tab)} items={tabs} className="acc-inbox-tabs" />

      {tab !== "direct" && (
        <div className="acc-filters" role="group" aria-label="Фильтры обращений">
          {tab === "incoming" && myRoles.length > 1 && (
            <div className="acc-chips" role="group" aria-label="Роль">
              <button type="button" className={cx("gv-chip-toggle", !role && "on")} aria-pressed={!role} onClick={() => url.set({ role: null })}>
                Все роли
              </button>
              {myRoles.map((r) => (
                <button key={r} type="button" className={cx("gv-chip-toggle", role === r && "on")} aria-pressed={role === r} onClick={() => url.set({ role: role === r ? null : r })}>
                  {ROLE_FILTER_LABELS[r]}
                </button>
              ))}
            </div>
          )}
          {tab === "outgoing" && <p className="acc-filter-note">Роль: {ROLE_FILTER_LABELS.customer} — заявки, которые вы отправили исполнителям.</p>}
          <div className="acc-filter-selects">
            <Select label="Статус" placeholder="Все статусы" options={statusOptions} value={status} onChange={(e) => url.set({ status: e.target.value || null })} />
            {tab === "incoming" && orgOptions.length > 0 && (
              <Select label="Организация" placeholder="Все и личные" options={orgOptions} value={organization} onChange={(e) => url.set({ organization: e.target.value || null })} />
            )}
          </div>
        </div>
      )}
      <div className="acc-filter-bar">
        <button type="button" className={cx("gv-chip-toggle", unreadOnly && "on")} aria-pressed={unreadOnly} onClick={() => url.set({ unread: unreadOnly ? null : "1" })}>
          Только непрочитанные
        </button>
        {!active.isPending && !active.isError && (
          <span className="gv-ac-list-count" aria-live="polite">
            {total} {plural(total, tab === "direct" ? ["диалог", "диалога", "диалогов"] : ["обращение", "обращения", "обращений"])}
          </span>
        )}
        {filtered && (
          <Button variant="link" onClick={resetFilters}>
            Сбросить фильтры
          </Button>
        )}
      </div>

      {active.isPending ? (
        <LoadingState variant="skeleton" lines={5} label="Загружаем обращения…" />
      ) : active.isError && !active.data ? (
        isApiError(active.error) && active.error.isForbidden ? (
          <NoAccess />
        ) : (
          <ErrorState error={active.error} onRetry={() => void active.refetch()} />
        )
      ) : tab === "direct" ? (
        directRows.length === 0 ? (
          <EmptyState
            compact
            title={unreadOnly ? "Непрочитанных сообщений нет" : "Личных сообщений пока нет"}
            text="Найдите компанию для катания в GG Surfer — переписка появится здесь."
            action={unreadOnly ? { label: "Показать все", onClick: resetFilters } : { label: "Открыть GG Surfer", href: routes.gg }}
          />
        ) : (
          <ul className="acc-rows" aria-label="Личные сообщения">
            {directRows.map((c) => (
              <ConversationRow key={c.id} item={c} href={`${routes.account.inquiries}?conversation=${c.id}`} />
            ))}
          </ul>
        )
      ) : rows.length === 0 ? (
        <EmptyState
          compact
          title={filtered ? "По фильтрам ничего не нашлось" : tab === "incoming" ? "Входящих обращений пока нет" : "Вы ещё не отправляли заявок"}
          text={
            filtered
              ? "Попробуйте другой статус или роль."
              : tab === "incoming"
                ? "Когда клиент напишет по вашему занятию, доске или аренде, обращение и чат появятся здесь."
                : "Выберите инструктора, доску или снаряжение и нажмите «Написать» или «Заказать»."
          }
          action={filtered ? { label: "Сбросить фильтры", onClick: resetFilters } : tab === "outgoing" ? { label: "Найти инструктора", href: routes.instructors } : undefined}
        />
      ) : (
        <ul className="acc-rows" aria-label={tab === "incoming" ? "Входящие обращения" : "Мои заявки"}>
          {rows.map((item) => (
            <InquiryRow key={item.id} item={item} />
          ))}
        </ul>
      )}

      {active.hasNextPage && (
        <div className="acc-more">
          <Button variant="soft" loading={active.isFetchingNextPage} onClick={() => void active.fetchNextPage()}>
            Показать ещё
          </Button>
        </div>
      )}
      <p className="gv-ac-muted acc-footnote">Непрочитанные диалоги отмечены голубым. Открытие переписки помечает сообщения прочитанными на всех ваших устройствах.</p>
    </section>
  );
}
