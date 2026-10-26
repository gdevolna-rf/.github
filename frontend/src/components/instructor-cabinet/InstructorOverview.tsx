"use client";
/**
 * Instructor «Обзор» (CABINET_SCREENS §6.2.1): card status (publication + certificate), one compact metrics row
 * (MET-02 — only here and in «Статистика»), the nearest sessions from the unified schedule and entry cards.
 */
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ik, instructorApi } from "@/lib/api/instructorCabinet";
import { useMe } from "@/lib/auth/hooks";
import { formatTime, isoDateInZone, pluralize } from "@/lib/format";
import { routes } from "@/lib/routes";
import { Avatar } from "@/components/ui/Avatar";
import { StatusBadge } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { CertificateBadge } from "@/components/ui/CertificateBadge";
import { Icon, type IconName } from "@/components/ui/Icon";
import { QueryState } from "@/components/ui/QueryState";
import { StatStrip } from "@/components/ui/StatStrip";
import { EmptyState, LoadingState } from "@/components/ui/States";
import { formatMetric, useMetrics } from "@/components/learning-cabinet/MetricsPanel";
import { addDays, formatDay, todayIn, tzLabel } from "@/components/learning-cabinet/time";
import { useInstructorProfile, useInstructorZone, useOffers } from "./hooks";
import { instructorLinks, instructorPaths as p } from "./paths";

const STRIP = ["profile_views", "bookings", "completed_lessons", "load", "rating"];

function MetricsStrip({ timeZone }: { timeZone: string }) {
  const to = todayIn(timeZone);
  const q = useMetrics({ scope: "instructor", from: addDays(to, -29), to, tz: timeZone });
  if (q.isPending) return <LoadingState variant="inline" label="Считаем показатели…" />;
  if (q.isError || !q.data) return null; // the full error state lives in «Статистика»
  const byKey = new Map(q.data.metrics.map((m) => [m.key, m]));
  const items = STRIP.map((k) => byKey.get(k))
    .filter(Boolean)
    .map((m) => ({ label: m!.label, value: formatMetric(m!), hint: m!.formula, tone: m!.value === null ? ("muted" as const) : undefined }));
  return (
    <div className="lc-overview-metrics">
      <StatStrip ariaLabel="Показатели за 30 дней" items={items} />
      <Link href={p.stats} className="feature-link">
        Вся статистика и формулы <Icon name="arrow" size={14} />
      </Link>
    </div>
  );
}

function UpcomingSessions({ timeZone }: { timeZone: string }) {
  const from = todayIn(timeZone);
  const to = addDays(from, 13);
  const query = useQuery({
    queryKey: ik.schedule(from, to, timeZone),
    queryFn: () => instructorApi.schedule({ from, to, tz: timeZone, status: "scheduled,in_progress" }),
  });
  return (
    <section className="gv-ac-card lc-overview-upcoming" aria-labelledby="ins-upcoming">
      <div className="gv-ac-card-head">
        <h3 id="ins-upcoming">Ближайшие занятия</h3>
        <Icon name="calendar" size={22} className="gv-ac-card-icon" />
      </div>
      <QueryState
        query={query}
        loading={<LoadingState variant="skeleton" lines={3} />}
        isEmpty={(d) => d.results.length === 0}
        empty={<EmptyState compact title="На две недели вперёд занятий нет" text="Добавьте частный слот по своему предложению или дождитесь назначения от школы." />}
      >
        {(data) => (
          <ul className="lc-upcoming">
            {data.results.slice(0, 5).map((s) => (
              <li key={s.id} className="gv-ac-line">
                <div className="gv-ac-line-main">
                  <strong className="gv-clamp-1" title={s.title}>
                    {s.title}
                  </strong>
                  <small>
                    {formatDay(isoDateInZone(s.starts_at, s.timezone), "weekday")}, {formatTime(s.starts_at, s.timezone)} · {tzLabel(s.timezone, s.starts_at)}
                    {" · "}
                    {s.organization ? s.organization.name : "частное"} · {s.seats_taken} из {s.capacity}
                  </small>
                </div>
                <StatusBadge domain="session" status={s.status} />
              </li>
            ))}
            {data.results.length > 5 && <li className="lc-muted">И ещё {pluralize(data.results.length - 5, ["занятие", "занятия", "занятий"])}</li>}
          </ul>
        )}
      </QueryState>
      <div className="gv-ac-form-action">
        <ButtonLink href={p.schedule} variant="soft" iconRight="arrow">
          Расписание
        </ButtonLink>
        <ButtonLink href={`${p.schedule}?new=1`} variant="soft" icon="plus">
          Частный слот
        </ButtonLink>
      </div>
    </section>
  );
}

export function InstructorOverview() {
  const { me } = useMe();
  const profileQ = useInstructorProfile(Boolean(me?.specialties.includes("instructor")));
  const offersQ = useOffers(Boolean(profileQ.data));
  const zone = useInstructorZone(profileQ.data);
  const profile = profileQ.data;
  const activeOffers = (offersQ.data ?? []).filter((o) => o.is_active).length;
  const missing = profile ? Object.keys(profile.publish_check?.missing ?? {}).length : 0;

  const cards: Array<{ title: string; text: string; href: string; icon: IconName; cta: string }> = [
    { title: "Обращения учеников", text: "Вопросы и заявки на занятия — в общем разделе «Обращения» с чатом.", href: instructorLinks.inquiries, icon: "chat", cta: "Открыть" },
    { title: "Записи на занятия", text: "Подтверждайте и отклоняйте записи учеников на ваши слоты.", href: instructorLinks.bookings, icon: "calendar", cta: "Открыть" },
    {
      title: "Предложения",
      text: offersQ.data ? `Активных: ${activeOffers}. Формат, длительность, цена, спот и правила занятия.` : "Формат, длительность, цена, спот и правила занятия.",
      href: p.offers,
      icon: "brief",
      cta: "Управлять",
    },
    {
      title: "Сертификат",
      text: "Необязателен. После проверки модератором в карточке появится отметка «Сертификат проверен».",
      href: p.certificates,
      icon: "shield",
      cta: "Сертификаты",
    },
  ];

  return (
    <div className="lc-overview">
      <QueryState query={profileQ} loading={<LoadingState variant="skeleton" lines={3} />}>
        {(data) =>
          data ? (
            <section className="gv-ac-card lc-card-status" aria-label="Ваша карточка инструктора">
              <Avatar media={data.avatar} name={data.display_name} size={56} />
              <div className="lc-card-status-main">
                <strong>{data.display_name}</strong>
                <div className="lc-session-tags">
                  <StatusBadge domain="publication" status={data.status} />
                  <CertificateBadge status={data.certificate_status} audience="owner" compact />
                </div>
                <small>
                  {data.status === "published"
                    ? "Карточка видна в каталоге инструкторов."
                    : missing
                      ? `Для публикации осталось заполнить: ${pluralize(missing, ["пункт", "пункта", "пунктов"])}.`
                      : "Все обязательные поля заполнены — карточку можно опубликовать."}
                </small>
              </div>
              <div className="gv-card-head-actions">
                <ButtonLink href={p.profile} variant="soft" icon="pencil">
                  Карточка
                </ButtonLink>
                {data.status === "published" && data.handle && (
                  <ButtonLink href={routes.instructor(data.handle)} variant="soft" iconRight="external">
                    На сайте
                  </ButtonLink>
                )}
              </div>
            </section>
          ) : (
            <EmptyState
              compact
              title="Карточка инструктора ещё не создана"
              text="Заполните карточку: регион, форматы, цену и пару слов о себе. Сертификат не обязателен — его можно добавить позже."
              action={{ label: "Заполнить карточку", href: p.profile }}
            />
          )
        }
      </QueryState>
      <MetricsStrip timeZone={zone} />
      <div className="gv-ac-cards">
        <UpcomingSessions timeZone={zone} />
        {cards.map((c) => (
          <article key={c.href} className="gv-ac-card">
            <div className="gv-ac-card-head">
              <h3>{c.title}</h3>
              <Icon name={c.icon} size={22} className="gv-ac-card-icon" />
            </div>
            <p>{c.text}</p>
            <ButtonLink href={c.href} variant="soft" iconRight="arrow">
              {c.cta}
            </ButtonLink>
          </article>
        ))}
      </div>
      <p className="lc-footnote">
        Время занятий показано по месту проведения. Основной часовой пояс (по региону карточки): {tzLabel(zone)}.
      </p>
    </div>
  );
}
