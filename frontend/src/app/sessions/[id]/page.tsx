/**
 * Публичная карточка занятия (SCH-05, SCH-08): время в часовом поясе места, спот, инструктор, школа, цена,
 * свободные места → запись или лист ожидания. SSR for the shell; seats and the viewer's waitlist entry are
 * refreshed on the client (SessionBookingPanel).
 */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { isApiError } from "@/lib/api/errors";
import { AGE_CATEGORY_LABELS, LESSON_FORMAT_LABELS, STUDENT_LEVEL_LABELS, labelOf, type LessonSession } from "@/lib/api/learning";
import { serverFetch, serverFetchSafe } from "@/lib/api/server";
import { formatDate, formatDuration, formatTime, formatUtcOffset } from "@/lib/format";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";
import { Avatar } from "@/components/ui/Avatar";
import { Tag } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { SessionBookingPanel } from "@/components/schools/SessionBookingPanel";
import "@/components/schools/schools.css";

export const revalidate = 30;

type Params = Promise<{ id: string }>;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function loadSession(id: string): Promise<LessonSession> {
  if (!UUID_RE.test(id)) notFound();
  return serverFetch<LessonSession>(`sessions/${id}`, { revalidate, tags: ["sessions", `session:${id}`] }).catch((err: unknown) => {
    if (isApiError(err) && err.isNotFound) notFound();
    throw err;
  });
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const session = UUID_RE.test(id) ? await serverFetchSafe<LessonSession>(`sessions/${id}`, { revalidate }) : null;
  const where = session?.organization?.name ?? session?.instructor?.display_name ?? "";
  return buildMetadata({
    title: session ? `${session.title}${where ? ` — ${where}` : ""}` : "Занятие",
    description: session
      ? `Занятие ${formatDate(session.starts_at, { timeZone: session.timezone, style: "long" })} в ${formatTime(session.starts_at, session.timezone)}${session.spot ? `, ${session.spot.name}` : ""}. Свободные места и запись.`
      : undefined,
    path: routes.session(id),
    // short-lived pages: keep them out of the index, the school/instructor pages are canonical
    noindex: true,
  });
}

export default async function SessionPage({ params }: { params: Params }) {
  const { id } = await params;
  const session = await loadSession(id);
  const tz = session.timezone;
  const minutes = Math.max(0, Math.round((new Date(session.ends_at).getTime() - new Date(session.starts_at).getTime()) / 60000));
  const level = session.program?.level ?? session.offer?.level;
  const format = session.program?.format ?? session.offer?.format;
  const instructor = session.instructor;

  return (
    <div className="wrap gv-session-page">
      <p className="gv-session-crumbs">
        {session.organization ? (
          <>
            <Link href={routes.schools}>Сёрф-школы</Link> · <Link href={routes.school(session.organization.slug)}>{session.organization.name}</Link>
          </>
        ) : instructor?.handle && instructor.has_public_profile !== false ? (
          <>
            <Link href={routes.instructors}>Инструкторы</Link> · <Link href={routes.instructor(instructor.handle)}>{instructor.display_name}</Link>
          </>
        ) : (
          <Link href={routes.instructors}>Инструкторы</Link>
        )}
      </p>
      <h1 className="gv-session-title">{session.title || session.program?.title || session.offer?.title || "Занятие"}</h1>
      <div className="conditions">
        {level && <Tag>{labelOf(STUDENT_LEVEL_LABELS, level)}</Tag>}
        {format && <Tag>{labelOf(LESSON_FORMAT_LABELS, format)}</Tag>}
        {session.program?.age_category && <Tag>{labelOf(AGE_CATEGORY_LABELS, session.program.age_category)}</Tag>}
        <Tag>{session.kind === "school" ? "Занятие школы" : "Частное занятие"}</Tag>
      </div>

      <div className="gv-school-layout">
        <div>
          {session.reschedule_reason && session.status === "scheduled" && (
            <p className="notice" role="status">
              <b>Занятие перенесено.</b> {session.reschedule_reason}
            </p>
          )}
          <div className="lesson-info-card gv-school-block">
            <dl className="gv-school-facts">
              <div>
                <dt>Дата</dt>
                <dd>{formatDate(session.starts_at, { timeZone: tz, style: "long" })}</dd>
              </div>
              <div>
                <dt>Время</dt>
                <dd>
                  {formatTime(session.starts_at, tz)}–{formatTime(session.ends_at, tz)} · местное время
                  {tz ? ` (${tz.replace(/_/g, " ")}, ${formatUtcOffset(tz, session.starts_at)})` : ""}
                </dd>
              </div>
              <div>
                <dt>Длительность</dt>
                <dd>{formatDuration(minutes)}</dd>
              </div>
              {session.spot && (
                <div>
                  <dt>Спот</dt>
                  <dd>
                    <Link href={routes.spot(session.spot.slug)}>{session.spot.name}</Link>
                    {session.spot.region?.name ? ` · ${session.spot.region.name}` : ""}
                  </dd>
                </div>
              )}
              {session.program && (
                <div>
                  <dt>Программа</dt>
                  <dd>
                    {session.program.title}
                    {session.program.sessions_count > 1 ? ` · курс из ${session.program.sessions_count} занятий` : ""}
                  </dd>
                </div>
              )}
              {session.offer && (
                <div>
                  <dt>Формат</dt>
                  <dd>{session.offer.title}</dd>
                </div>
              )}
              <div>
                <dt>Группа</dt>
                <dd>до {session.capacity} человек</dd>
              </div>
            </dl>
          </div>

          <section className="gv-school-block" aria-labelledby="who-title">
            <h2 id="who-title" className="section-title">
              Кто проводит
            </h2>
            {instructor ? (
              <div className="gv-team-member">
                <Avatar media={instructor.avatar} name={instructor.display_name} size={52} />
                <div>
                  <b>{instructor.display_name}</b>
                  <small>Инструктор{session.organization ? ` · ${session.organization.name}` : ""}</small>
                  {instructor.handle && instructor.has_public_profile && (
                    <Link href={routes.instructor(instructor.handle)}>Профиль инструктора →</Link>
                  )}
                </div>
              </div>
            ) : (
              <p className="small">Инструктора назначит школа — имя появится здесь до начала занятия.</p>
            )}
            {session.organization && (
              <p className="small">
                <Icon name="school" size={14} /> Организатор:{" "}
                <Link href={routes.school(session.organization.slug)}>{session.organization.name}</Link>
              </p>
            )}
          </section>

          <p className="lesson-form-note">
            Заявка ожидает подтверждения. Оплата на сайте не списывается — условия и снаряжение уточняются в переписке. При
            плохой погоде занятие могут перенести: мы пришлём уведомление.
          </p>
        </div>

        <aside className="gv-school-aside" aria-label="Запись на занятие">
          <SessionBookingPanel initial={session} />
        </aside>
      </div>
    </div>
  );
}
