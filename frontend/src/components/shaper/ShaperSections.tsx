"use client";
/** Подразделы кабинета шейпера: профиль мастерской (SHP-01..05) и статистика (MET-03, SHO-07, ATX-29). */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { shaperApi, shaperKeys } from "@/lib/api/shaper";
import { QueryState, Segmented, StatStrip } from "@/components/ui";
import { periodBounds, type PeriodKey } from "@/components/learning-cabinet/MetricsPanel";
import { DEFAULT_TIME_ZONE } from "@/lib/format";
import { ShaperGate } from "./ShaperShell";
import { WorkshopForm } from "./WorkshopForm";
import { formatMetric } from "./ShaperPanel";

export function WorkshopPage() {
  return (
    <ShaperGate title="Профиль мастерской" whenMissing={(organization) => <WorkshopForm workshop={null} organization={organization} />}>
      {(workshop, organization) => <WorkshopForm workshop={workshop} organization={organization} />}
    </ShaperGate>
  );
}

const STRIP = ["published_models", "model_views", "inquiries_active", "unique_clients", "conversion", "revenue_confirmed"];

function Stats({ workshopId }: { workshopId: string }) {
  const [period, setPeriod] = useState<PeriodKey>("30");
  const bounds = periodBounds(period, DEFAULT_TIME_ZONE);
  const metrics = useQuery({
    queryKey: shaperKeys.metrics(workshopId, bounds.from, bounds.to),
    queryFn: () => shaperApi.metrics({ organization_id: workshopId, from: bounds.from, to: bounds.to, tz: DEFAULT_TIME_ZONE }),
  });
  return (
    <div className="gv-sc-stats">
      <Segmented
        ariaLabel="Период"
        value={period}
        onChange={(v) => setPeriod(v as PeriodKey)}
        options={[
          { value: "7", label: "7 дней" },
          { value: "30", label: "30 дней" },
          { value: "90", label: "90 дней" },
        ]}
      />
      <QueryState query={metrics}>
        {(data) => {
          const byKey = new Map(data.metrics.map((m) => [m.key, m]));
          const interest = data.breakdowns.interest_by_board_type ?? [];
          return (
            <>
              <StatStrip
                items={STRIP.filter((k) => byKey.has(k)).map((k) => ({ label: byKey.get(k)!.label, value: formatMetric(byKey.get(k)), hint: byKey.get(k)!.formula }))}
              />
              <div className="gv-table-scroll">
                <table className="gv-table">
                  <caption className="sr-only">Показатели мастерской за период</caption>
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
                        <td>{m.label}</td>
                        <td>{formatMetric(m)}</td>
                        <td className="small muted">{m.formula}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {interest.length > 0 && (
                <section aria-label="Интерес по типам досок">
                  <h3>Интерес по типам досок</h3>
                  <ul className="gv-sc-interest">
                    {interest.map((row) => (
                      <li key={row.board_type}>
                        <span>{row.name}</span> <b>{row.views}</b> просмотров · <b>{row.inquiries}</b> обращений
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              <p className="small muted">
                Выручка — только суммы, подтверждённые при завершении обращений; заявки и неподтверждённые суммы в неё не входят.
              </p>
            </>
          );
        }}
      </QueryState>
    </div>
  );
}

export function ShaperStats() {
  return <ShaperGate title="Статистика мастерской">{(workshop) => <Stats workshopId={workshop.id} />}</ShaperGate>;
}
