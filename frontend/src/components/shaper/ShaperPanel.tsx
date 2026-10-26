"use client";
/**
 * «Панель управления» шейпера (SHO-01, BRD-01, MET-02): incoming inquiries and the compact one-line metrics on
 * top, a models digest below (no editor — models are managed only in «Мои доски»), the promo banner.
 * Without a workshop: the registration form for a shaper, an explanation otherwise.
 */
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { shaperApi, shaperKeys, metricByKey, type DashboardMetric, type InquiryPreview, type Workshop } from "@/lib/api/shaper";
import { formatMoney, formatNumber, formatRelative, plural, pluralize, WORDS } from "@/lib/format";
import { routes } from "@/lib/routes";
import { Avatar } from "@/components/ui/Avatar";
import { StatusBadge } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { StatStrip } from "@/components/ui/StatStrip";
import { EmptyState, ErrorState, LoadingState, NoAccess } from "@/components/ui/States";
import { isApiError } from "@/lib/api/errors";
import { ShaperGate } from "./ShaperShell";
import { shaperRoutes } from "./routes";
import { WorkshopForm } from "./WorkshopForm";

export function formatMetric(m: DashboardMetric | undefined): string {
  if (!m || m.value === null || m.value === undefined || m.value === "") return "—";
  if (m.unit === "money") return formatMoney(m.value, m.currency ?? "RUB") || "—";
  if (m.unit === "percent") return `${formatNumber(Number(m.value))} %`;
  return formatNumber(Number(m.value));
}

function InquiryRow({ inquiry }: { inquiry: InquiryPreview }) {
  const party = inquiry.counterpart;
  const about = [inquiry.kind_label, inquiry.context?.title || inquiry.subject, inquiry.agreed_amount ? formatMoney(inquiry.agreed_amount, inquiry.currency) : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <li className="request-item gv-sc-request">
      <Avatar media={party?.avatar ?? party?.logo ?? null} name={party?.name ?? "Клиент"} size={35} />
      <div className="request-copy">
        <Link href={routes.account.inquiry(inquiry.id)} className="gv-sc-request-link">
          <strong className="gv-clamp-1" title={party?.name ?? undefined}>
            {party?.name ?? "Клиент"}
          </strong>
        </Link>
        <small title={about}>{about}</small>
        {inquiry.last_message?.body && <small title={inquiry.last_message.body}>{inquiry.last_message.is_mine ? "Вы: " : ""}{inquiry.last_message.body}</small>}
      </div>
      <div className="request-meta gv-sc-request-meta">
        <span className="request-date">{formatRelative(inquiry.last_message?.created_at ?? inquiry.updated_at)}</span>
        <StatusBadge domain="inquiry" status={inquiry.status} />
        {inquiry.unread_count > 0 && (
          <span className="gv-sc-unread" aria-label={`${inquiry.unread_count} ${plural(inquiry.unread_count, WORDS.newMessage)}`}>
            {inquiry.unread_count > 99 ? "99+" : inquiry.unread_count}
          </span>
        )}
      </div>
    </li>
  );
}

function Dashboard({ workshop, organization }: { workshop: Workshop; organization: string | null }) {
  const metrics = useQuery({
    queryKey: shaperKeys.metrics(workshop.id),
    queryFn: () => shaperApi.metrics({ organization_id: workshop.id }),
  });
  const inquiries = useQuery({
    queryKey: shaperKeys.inquiriesPreview(organization),
    queryFn: () => shaperApi.inquiries({ organization: workshop.id, page_size: 3 }),
  });
  const models = useQuery({
    queryKey: shaperKeys.models(workshop.id, {}),
    queryFn: () => shaperApi.models(workshop.id),
  });

  const byStatus = metrics.data?.breakdowns.inquiries_by_status ?? {};
  const list = models.data?.results ?? [];
  const digest = {
    total: list.length,
    published: list.filter((m) => m.status === "published").length,
    inStock: list.filter((m) => m.availability === "in_stock").length,
    toOrder: list.filter((m) => m.availability === "made_to_order").length,
    drafts: list.filter((m) => m.status === "draft").length,
  };

  return (
    <div className="gv-sc-dashboard">
      {workshop.status !== "published" && workshop.status !== "pending_review" && (
        <div className="gv-ac-note gv-sc-draft-note" role="note">
          <Icon name="info" size={15} /> Мастерская не опубликована — её не видно в каталоге шейперов.{" "}
          <Link href={shaperRoutes.workshop(organization)}>Опубликовать в разделе «Мастерская»</Link>
        </div>
      )}
      {metrics.isError ? (
        isApiError(metrics.error) && metrics.error.isForbidden ? null : (
          <ErrorState compact error={metrics.error} title="Статистика не загрузилась" onRetry={() => void metrics.refetch()} />
        )
      ) : (
        <StatStrip
          ariaLabel="Показатели мастерской за 30 дней"
          items={[
            { label: "Моделей в каталоге", value: metrics.isPending ? "…" : formatMetric(metricByKey(metrics.data, "published_models")), hint: metricByKey(metrics.data, "published_models")?.formula },
            { label: "Новые обращения", value: metrics.isPending ? "…" : formatNumber(byStatus.new ?? 0), hint: "Обращения периода в статусе «Новое»" },
            { label: "В работе", value: metrics.isPending ? "…" : formatNumber(byStatus.in_progress ?? 0), hint: "Обращения периода в статусе «В работе»" },
            { label: "Завершено", value: metrics.isPending ? "…" : formatMetric(metricByKey(metrics.data, "inquiries_completed")), hint: metricByKey(metrics.data, "inquiries_completed")?.formula },
          ]}
        />
      )}

      <div className="lower-dash">
        <section className="card" aria-labelledby="sc-inq-title">
          <div className="section-head">
            <h3 id="sc-inq-title">
              <Icon name="mail" className="ic" size={19} /> Входящие обращения
            </h3>
            <Link className="plain gv-sc-more" href={shaperRoutes.inquiries}>
              Все обращения <Icon name="arrow" size={13} />
            </Link>
          </div>
          {inquiries.isPending ? (
            <LoadingState variant="skeleton" lines={3} />
          ) : inquiries.isError ? (
            isApiError(inquiries.error) && inquiries.error.isForbidden ? (
              <NoAccess />
            ) : (
              <ErrorState compact error={inquiries.error} onRetry={() => void inquiries.refetch()} />
            )
          ) : inquiries.data.results.length === 0 ? (
            <EmptyState compact title="Обращений пока нет" text="Когда клиент закажет доску или напишет мастерской, обращение появится здесь — писать можно ещё до принятия заявки." />
          ) : (
            <ul className="gv-sc-requests" aria-label="Последние обращения">
              {inquiries.data.results.slice(0, 3).map((i) => (
                <InquiryRow key={i.id} inquiry={i} />
              ))}
            </ul>
          )}
        </section>

        <section className="card" aria-labelledby="sc-kpi-title">
          <div className="section-head">
            <h3 id="sc-kpi-title">
              <Icon name="graph" className="ic" size={19} /> Показатели мастерской
            </h3>
            <Link className="plain gv-sc-more" href={shaperRoutes.stats(organization)}>
              Вся статистика <Icon name="arrow" size={13} />
            </Link>
          </div>
          {metrics.isPending ? (
            <LoadingState variant="skeleton" lines={2} />
          ) : metrics.isError ? (
            <p className="form-help">
              {isApiError(metrics.error) && metrics.error.isForbidden ? metrics.error.message : "Показатели временно недоступны."}
            </p>
          ) : (
            <div className="gv-overview-metrics">
              {(["model_views", "unique_clients", "conversion", "revenue_confirmed"] as const).map((key) => {
                const m = metricByKey(metrics.data, key);
                return (
                  <div key={key} className="gv-mini-kpi" title={m?.formula}>
                    <strong>{formatMetric(m)}</strong>
                    <small>{key === "revenue_confirmed" ? "Подтверждённая выручка" : (m?.label ?? key)}</small>
                  </div>
                );
              })}
            </div>
          )}
          <p className="form-help">За последние 30 дней · только подтверждённые суммы и квалифицированные просмотры.</p>
        </section>
      </div>

      <section className="card gv-overview-models" aria-labelledby="sc-models-title">
        <div className="section-head">
          <h3 id="sc-models-title">
            <Icon name="board" className="ic" size={19} /> Мои модели досок
          </h3>
          <ButtonLink href={shaperRoutes.boards(organization)} variant="primary" iconRight="arrow">
            Управлять моделями
          </ButtonLink>
        </div>
        {models.isPending ? (
          <LoadingState variant="skeleton" lines={1} />
        ) : models.isError ? (
          <ErrorState compact error={models.error} onRetry={() => void models.refetch()} />
        ) : digest.total === 0 ? (
          <p className="form-help">Моделей пока нет. Добавьте первую доску в разделе «Мои доски» — артикул присвоится автоматически.</p>
        ) : (
          <div className="gv-models-digest">
            <span>
              <b>{pluralize(digest.total, WORDS.model)}</b> всего
            </span>
            <span>
              <b>{formatNumber(digest.published)}</b> опубликовано
            </span>
            <span>
              <b>{formatNumber(digest.inStock)}</b> в наличии
            </span>
            <span>
              <b>{formatNumber(digest.toOrder)}</b> под заказ
            </span>
            {digest.drafts > 0 && (
              <span>
                <b>{formatNumber(digest.drafts)}</b> {plural(digest.drafts, ["черновик", "черновика", "черновиков"])}
              </span>
            )}
          </div>
        )}
        <p className="form-help">Редактирование и полный список ваших моделей — только в разделе «Мои доски».</p>
      </section>

      <section className="dash-promo" aria-labelledby="sc-promo-title">
        <h3 id="sc-promo-title">Делитесь своей философией</h3>
        <p>
          Покажите, как рождаются ваши доски.
          <br />
          Вдохновляйте новое поколение сёрферов.
        </p>
        <ButtonLink href={shaperRoutes.workshop(organization)} variant="line" className="outlined" iconRight="arrow">
          Редактировать профиль
        </ButtonLink>
      </section>
    </div>
  );
}

export function ShaperPanel() {
  return (
    <ShaperGate whenMissing={(organization) => <WorkshopForm workshop={null} organization={organization} />}>
      {(workshop, organization) => <Dashboard workshop={workshop} organization={organization} />}
    </ShaperGate>
  );
}
