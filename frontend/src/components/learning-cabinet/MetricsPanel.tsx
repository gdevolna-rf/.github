"use client";
/**
 * Dashboard metrics from GET me/metrics (TZ 10.1, MET-04/05, INS-10, SCH-12): a compact one-line strip for the
 * key numbers (MET-02) + a table with every metric and its formula, visible as text (not only a tooltip) so
 * the numbers are explainable and keyboard/screen-reader accessible. Values are server aggregates only.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { formatMoney, formatNumber, formatRating } from "@/lib/format";
import { lk, metricsApi, type DashboardMetric, type MetricsQuery, type MetricsResponse } from "@/lib/api/learningCabinet";
import { isApiError } from "@/lib/api/errors";
import { Segmented } from "@/components/ui/Segmented";
import { StatStrip } from "@/components/ui/StatStrip";
import { ErrorState, LoadingState, NoAccess } from "@/components/ui/States";
import { addDays, formatDay, todayIn } from "./time";

export type PeriodKey = "7" | "30" | "90";

export function periodBounds(key: PeriodKey, timeZone: string, now = new Date()): { from: string; to: string } {
  const to = todayIn(timeZone, now);
  return { from: addDays(to, -(Number(key) - 1)), to };
}

/** Human value of a metric: «—» when the formula has no data (null), never a fake 0 (MET-07). */
export function formatMetric(m: Pick<DashboardMetric, "value" | "unit" | "currency">): string {
  if (m.value === null || m.value === undefined || m.value === "") return "—";
  const n = typeof m.value === "number" ? m.value : Number(m.value);
  switch (m.unit) {
    case "percent":
      return Number.isFinite(n) ? `${formatNumber(n)} %` : "—";
    case "money":
      return formatMoney(m.value, m.currency ?? "RUB") || "—";
    case "rating":
      return Number.isFinite(n) ? formatRating(n) : "—";
    case "minutes":
      return Number.isFinite(n) ? `${formatNumber(n, 0)} мин` : "—";
    default:
      return Number.isFinite(n) ? formatNumber(n, 1) : String(m.value);
  }
}

export function useMetrics(q: MetricsQuery, enabled = true) {
  return useQuery({ queryKey: lk.metrics(q), queryFn: () => metricsApi.get(q), enabled, staleTime: 60_000, placeholderData: keepPreviousData });
}

export function MetricsPanel({
  scope,
  organizationId,
  timeZone,
  stripKeys,
  children,
  title = "Показатели",
}: {
  scope: MetricsQuery["scope"];
  organizationId?: string;
  timeZone: string;
  /** metrics shown in the compact strip (others only in the table) */
  stripKeys: string[];
  /** breakdowns renderer */
  children?: (data: MetricsResponse) => ReactNode;
  title?: string;
}) {
  const [period, setPeriod] = useState<PeriodKey>("30");
  const bounds = periodBounds(period, timeZone);
  const query = useMetrics({ scope, organization_id: organizationId, from: bounds.from, to: bounds.to, tz: timeZone });

  let body: ReactNode;
  if (query.isPending) body = <LoadingState variant="skeleton" lines={6} label="Считаем показатели…" />;
  else if (query.isError && !query.data) {
    const err = query.error;
    if (isApiError(err) && err.isForbidden) {
      body = <NoAccess title="Статистика недоступна" text={err.message} />;
    } else {
      body = <ErrorState error={err} onRetry={() => void query.refetch()} title="Не удалось посчитать показатели" />;
    }
  } else {
    const data = query.data as MetricsResponse;
    const byKey = new Map(data.metrics.map((m) => [m.key, m]));
    const strip = stripKeys.map((k) => byKey.get(k)).filter((m): m is DashboardMetric => Boolean(m));
    body = (
      <>
        <StatStrip
          ariaLabel={title}
          items={strip.map((m) => ({ label: m.label, value: formatMetric(m), hint: m.formula, tone: m.value === null ? "muted" : "default" }))}
        />
        <div className="lc-table-wrap" tabIndex={0} role="region" aria-label="Все показатели и формулы">
          <table className="lc-table">
            <caption className="sr-only">Показатели за период и как они считаются</caption>
            <thead>
              <tr>
                <th scope="col">Показатель</th>
                <th scope="col">Значение</th>
                <th scope="col">Как считается</th>
              </tr>
            </thead>
            <tbody>
              {data.metrics.map((m) => (
                <tr key={m.key}>
                  <th scope="row">{m.label}</th>
                  <td className="lc-num">{formatMetric(m)}</td>
                  <td className="lc-formula">{m.formula}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {children?.(data)}
        <p className="lc-footnote">
          Период: {formatDay(data.period.from, "dayMonth")} — {formatDay(data.period.to, "long")} ({data.period.timezone}). «—» — данных для расчёта пока нет.
          Считаются только события и сделки, подтверждённые сервером (версия правил {data.rule_version}).
        </p>
      </>
    );
  }

  return (
    <div className="lc-metrics">
      <div className="lc-metrics-head">
        <Segmented<PeriodKey>
          ariaLabel="Период статистики"
          size="sm"
          value={period}
          onChange={setPeriod}
          options={[
            { value: "7", label: "7 дней" },
            { value: "30", label: "30 дней" },
            { value: "90", label: "90 дней" },
          ]}
        />
        {query.isFetching && !query.isPending ? <span className="lc-muted">Обновляем…</span> : null}
      </div>
      {body}
    </div>
  );
}
