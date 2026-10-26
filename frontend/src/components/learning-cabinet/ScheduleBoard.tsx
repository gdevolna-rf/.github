"use client";
/**
 * Schedule calendar shared by the instructor (GET me/schedule) and school (GET organizations/{id}/sessions)
 * cabinets (INS-07, SCH-05, AT-06): week grid · day (prototype `.lesson-day` strip + day list) · list of 4 weeks.
 * View and date live in the URL (`?view=week&date=2026-10-21`, NAV-05). Each session is placed on the day of its
 * own zone and shows the zone label (sessions of one instructor can be in different regions).
 */
import { keepPreviousData, useQuery, type QueryKey } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import { formatTime, isoDateInZone, plural } from "@/lib/format";
import type { LessonSession } from "@/lib/api/learningCabinet";
import { isApiError } from "@/lib/api/errors";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { IconButton } from "@/components/ui/IconButton";
import { Modal } from "@/components/ui/Modal";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, LoadingState, NoAccess } from "@/components/ui/States";
import { addDays, dayOfMonth, dayRange, formatDay, formatDayRange, startOfWeek, todayIn, tzLabel, weekdayShort } from "./time";

export type ScheduleView = "week" | "day" | "list";
const VIEWS: ScheduleView[] = ["week", "day", "list"];
const LIST_DAYS = 28;
const SESSION_WORDS = ["занятие", "занятия", "занятий"] as const;

export interface ScheduleRange {
  view: ScheduleView;
  /** first and last visible day (inclusive) */
  from: string;
  to: string;
  selected: string;
  today: string;
}

/** Pure range logic (unit-tested): week → Mon…Sun of the anchor, list → 4 weeks from that Monday. */
export function scheduleRange(view: ScheduleView, anchor: string, today: string): ScheduleRange {
  const weekStart = startOfWeek(anchor);
  if (view === "list") return { view, from: weekStart, to: addDays(weekStart, LIST_DAYS - 1), selected: anchor, today };
  return { view, from: weekStart, to: addDays(weekStart, 6), selected: anchor, today };
}

/** Group sessions by their local calendar day (in each session's own zone). */
export function groupByDay<T extends LessonSession>(sessions: T[]): Map<string, T[]> {
  const map = new Map<string, T[]>();
  for (const s of sessions) {
    const day = isoDateInZone(s.starts_at, s.timezone);
    const list = map.get(day);
    if (list) list.push(s);
    else map.set(day, [s]);
  }
  for (const list of map.values()) list.sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  return map;
}

const isDay = (v: string | null): v is string => Boolean(v && /^\d{4}-\d{2}-\d{2}$/.test(v));

export interface ScheduleBoardProps<T extends LessonSession> {
  /** zone used for «today» and for the fetch bounds (instructor/school region) */
  viewTz: string;
  queryKey: (from: string, to: string) => QueryKey;
  /** fetch sessions starting in [from, to] (dates inclusive, `tz` = viewTz); the board widens the range by a day */
  fetcher: (from: string, to: string) => Promise<T[]>;
  /** full card with actions */
  renderSession: (session: T) => ReactNode;
  toolbarExtra?: ReactNode;
  emptyTitle?: string;
  emptyText?: ReactNode;
  /** called with the loaded sessions (e.g. to keep a details modal in sync) */
  idPrefix?: string;
}

export function ScheduleBoard<T extends LessonSession>({
  viewTz,
  queryKey,
  fetcher,
  renderSession,
  toolbarExtra,
  emptyTitle = "Занятий нет",
  emptyText,
  idPrefix = "sched",
}: ScheduleBoardProps<T>) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const today = todayIn(viewTz);
  const rawView = params?.get("view") as ScheduleView | null;
  const view: ScheduleView = rawView && VIEWS.includes(rawView) ? rawView : "week";
  const rawDate = params?.get("date") ?? null;
  const anchor = isDay(rawDate) ? rawDate : today;
  const range = scheduleRange(view, anchor, today);
  const [openId, setOpenId] = useState<string | null>(null);

  const setParams = (next: { view?: ScheduleView; date?: string }) => {
    const p = new URLSearchParams(params?.toString() ?? "");
    if (next.view) p.set("view", next.view);
    if (next.date) p.set("date", next.date);
    router.replace(`${pathname}?${p.toString()}`, { scroll: false });
  };

  const fetchFrom = addDays(range.from, -1);
  const fetchTo = addDays(range.to, 1);
  const query = useQuery({
    queryKey: queryKey(fetchFrom, fetchTo),
    queryFn: () => fetcher(fetchFrom, fetchTo),
    placeholderData: keepPreviousData,
  });

  const byDay = useMemo(() => groupByDay(query.data ?? []), [query.data]);
  const days = dayRange(range.from, view === "list" ? LIST_DAYS : 7);
  const visibleCount = days.reduce((n, d) => n + (byDay.get(d)?.length ?? 0), 0);
  const step = view === "list" ? LIST_DAYS : 7;
  const opened = openId ? (query.data ?? []).find((s) => s.id === openId) ?? null : null;
  const selectedDay = days.includes(range.selected) ? range.selected : days[0];

  let body: ReactNode;
  if (query.isPending) body = <LoadingState variant="skeleton" lines={5} label="Загружаем расписание…" />;
  else if (query.isError && !query.data) {
    body =
      isApiError(query.error) && query.error.isForbidden ? (
        <NoAccess />
      ) : (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="Не удалось загрузить расписание" />
      );
  } else if (view === "week") {
    body = (
      <div className="lc-week" role="list" aria-label={`Неделя ${formatDayRange(range.from, range.to)}`}>
        {days.map((day) => {
          const items = byDay.get(day) ?? [];
          return (
            <section key={day} role="listitem" className={cx("lc-week-day", day === today && "is-today")} aria-label={`${formatDay(day, "weekday")}: ${items.length} ${plural(items.length, SESSION_WORDS)}`}>
              <button type="button" className="lc-week-head" onClick={() => setParams({ view: "day", date: day })} title="Открыть день">
                <span>{weekdayShort(day)}</span>
                <strong>{dayOfMonth(day)}</strong>
                {day === today && <small>сегодня</small>}
              </button>
              {items.length ? (
                <ul className="lc-week-items">
                  {items.map((s) => (
                    <li key={s.id}>
                      <button type="button" className={cx("lc-week-item", `is-${s.status}`)} onClick={() => setOpenId(s.id)} aria-haspopup="dialog">
                        <b>{formatTime(s.starts_at, s.timezone)}</b>
                        <span className="gv-clamp-2">{s.title}</span>
                        <small>
                          {s.seats_taken}/{s.capacity}
                          {s.timezone !== viewTz ? ` · ${tzLabel(s.timezone, s.starts_at).split(" · ")[0]}` : ""}
                        </small>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="lc-week-empty">Нет занятий</p>
              )}
            </section>
          );
        })}
      </div>
    );
  } else if (view === "day") {
    const items = byDay.get(selectedDay) ?? [];
    body = (
      <>
        <div className="lesson-cal-grid lc-daystrip" role="group" aria-label="Дни недели">
          {days.map((day) => {
            const n = byDay.get(day)?.length ?? 0;
            return (
              <button
                key={day}
                type="button"
                className={cx("lesson-day", day === selectedDay && "selected", day === today && "today", n === 0 && "closed")}
                aria-pressed={day === selectedDay}
                aria-label={`${formatDay(day, "weekday")}: ${n} ${plural(n, SESSION_WORDS)}`}
                onClick={() => setParams({ view: "day", date: day })}
              >
                {dayOfMonth(day)}
                <span>
                  {weekdayShort(day)} · {n ? n : "—"}
                </span>
              </button>
            );
          })}
        </div>
        <h3 className="lc-day-title">{formatDay(selectedDay, "weekday")}</h3>
        {items.length ? (
          <div className="lc-session-list">{items.map((s) => <div key={s.id}>{renderSession(s)}</div>)}</div>
        ) : (
          <EmptyState compact title="В этот день занятий нет" text={emptyText} />
        )}
      </>
    );
  } else {
    const filled = days.filter((d) => byDay.get(d)?.length);
    body = filled.length ? (
      <div className="lc-session-days">
        {filled.map((day) => (
          <section key={day} aria-labelledby={`${idPrefix}-${day}`}>
            <h3 id={`${idPrefix}-${day}`} className={cx("lc-day-title", day === today && "is-today")}>
              {formatDay(day, "weekday")}
              {day === today ? " · сегодня" : ""}
            </h3>
            <div className="lc-session-list">{(byDay.get(day) ?? []).map((s) => <div key={s.id}>{renderSession(s)}</div>)}</div>
          </section>
        ))}
      </div>
    ) : (
      <EmptyState compact title={emptyTitle} text={emptyText} />
    );
  }

  return (
    <div className="lc-sched">
      <div className="lc-sched-toolbar">
        <div className="lc-sched-nav">
          <IconButton
            icon="chevron-left"
            shape="round"
            iconSize={18}
            label={view === "list" ? "Предыдущие 4 недели" : "Предыдущая неделя"}
            onClick={() => setParams({ date: addDays(range.from, -step) })}
          />
          <strong className="lc-sched-range" aria-live="polite">
            {formatDayRange(range.from, range.to)}
          </strong>
          <IconButton
            icon="chevron-right"
            shape="round"
            iconSize={18}
            label={view === "list" ? "Следующие 4 недели" : "Следующая неделя"}
            onClick={() => setParams({ date: addDays(range.from, step) })}
          />
          <Button variant="soft" size="sm" onClick={() => setParams({ date: today })} disabled={today >= range.from && today <= range.to && anchor === today}>
            Сегодня
          </Button>
        </div>
        <Segmented<ScheduleView>
          ariaLabel="Вид расписания"
          size="sm"
          value={view}
          onChange={(v) => setParams({ view: v })}
          options={[
            { value: "week", label: "Неделя", icon: "grid" },
            { value: "day", label: "День", icon: "calendar" },
            { value: "list", label: "Список", icon: "filter" },
          ]}
        />
        {toolbarExtra ? <div className="lc-sched-extra">{toolbarExtra}</div> : null}
      </div>
      <p className="lc-sched-hint">
        <Icon name="clock" size={14} /> Время указано по месту проведения занятия — часовой пояс подписан у каждого занятия.
        {!query.isPending && !query.isError ? ` На экране: ${visibleCount} ${plural(visibleCount, SESSION_WORDS)}.` : ""}
        {query.isFetching && !query.isPending ? " Обновляем…" : ""}
      </p>
      {body}
      <Modal open={Boolean(opened)} onClose={() => setOpenId(null)} title={opened?.title ?? "Занятие"} size="wide">
        {opened ? renderSession(opened) : null}
      </Modal>
    </div>
  );
}
