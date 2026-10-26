/** /surfers/[handle] — публичный профиль участника GG Surfer (COM-02, COM-06, ATX-34: без даты рождения). */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import { cache } from "react";
import { TrackView } from "@/components/analytics/TrackView";
import { WriteToSurferButton } from "@/components/public/CatalogIslands";
import { ReportButton } from "@/components/trust/ReportButton";
import { Avatar, StatStrip } from "@/components/ui";
import { isApiError } from "@/lib/api/errors";
import type { SurferDetail } from "@/lib/api/publicCatalogs";
import { serverFetch, serverFetchSafe } from "@/lib/api/server";
import type { Paginated } from "@/lib/api/types";
import type { DiaryEntry } from "@/lib/api/mine";
import { formatDate } from "@/lib/format";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 60;
type Params = Promise<{ handle: string }>;

const load = cache(async (handle: string) => {
  try {
    return await serverFetch<SurferDetail | { redirect: string }>(`surfers/${encodeURIComponent(handle)}`, { revalidate: 60 });
  } catch (e) {
    if (isApiError(e) && e.isNotFound) return null;
    throw e;
  }
});

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const s = await load((await params).handle);
  if (!s || "redirect" in s) return { title: "GG Surfer" };
  return buildMetadata({ title: `${s.display_name} — GG Surfer`, description: s.bio_excerpt, path: routes.surfer(s.handle) });
}

export default async function SurferPage({ params }: { params: Params }) {
  const { handle } = await params;
  const s = await load(handle);
  if (!s) notFound();
  if ("redirect" in s) permanentRedirect(routes.surfer(s.redirect));
  const diary = await serverFetchSafe<Paginated<DiaryEntry>>(`surfers/${encodeURIComponent(s.handle)}/diary`, { revalidate: 60 });
  return (
    <div className="wrap gv-page-body">
      <TrackView subjectType="surfer" subjectId={s.id} />
      <nav className="small muted">
        <Link href={routes.gg}>GG Surfer</Link>
      </nav>
      <header className="gv-spot-page-head">
        <div className="member-card-top">
          <Avatar media={s.avatar} name={s.display_name} size={88} />
          <div>
            <h1 className="spot-title">{s.display_name}</h1>
            <div className="muted">{[s.region?.name, s.riding_level_label, s.age ? `${s.age} лет` : ""].filter(Boolean).join(" · ")}</div>
          </div>
        </div>
        <div className="gv-spot-page-actions">
          {!s.is_me && <WriteToSurferButton accountId={s.id} canMessage={s.can_message} acceptsMessages={s.accepts_messages} />}
          {s.instructor_url && <Link href={s.instructor_url}>Профиль инструктора →</Link>}
          <ReportButton targetType="account" targetId={s.id} variant="link" />
        </div>
      </header>
      {s.diary && (
        <StatStrip
          items={[
            { label: "Дней катания", value: s.diary.ride_days },
            { label: "В этом году", value: s.diary.this_year_days },
            { label: "Спотов", value: s.diary.spots_visited },
          ]}
        />
      )}
      {s.bio && <p className="spot-summary">{s.bio}</p>}
      <dl className="gv-facts">
        {s.surfing_since && <div className="gv-fact"><dt>Катается с</dt><dd>{s.surfing_since}</dd></div>}
        {s.preferred_board_types.length > 0 && <div className="gv-fact"><dt>Доски</dt><dd>{s.preferred_board_types.join(", ")}</dd></div>}
        {s.favorite_spots.length > 0 && <div className="gv-fact"><dt>Любимые споты</dt><dd>{s.favorite_spots.map((f) => f.name).join(", ")}</dd></div>}
        {s.interests.length > 0 && <div className="gv-fact"><dt>Интересы</dt><dd>{s.interests.join(", ")}</dd></div>}
        {s.languages.length > 0 && <div className="gv-fact"><dt>Языки</dt><dd>{s.languages.join(", ")}</dd></div>}
      </dl>
      {s.fun_facts.length > 0 && (
        <ul>
          {s.fun_facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      )}
      {diary && diary.results.length > 0 && (
        <section aria-labelledby="diary">
          <h2 id="diary">Дневник катания</h2>
          <ul className="lc-list">
            {diary.results.map((e) => (
              <li key={e.id} className="lc-list-row">
                <span className="lc-grow">
                  <b>{formatDate(e.date)}</b> · {e.spot?.name ?? e.spot_name} {e.conditions ? `· ${e.conditions}` : ""}
                  {e.notes && <div className="small muted">{e.notes}</div>}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
