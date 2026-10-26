/** /gg — GG Surfer: сообщество по добровольному согласию (COM-01..03, BR-12). Приватность соблюдает сервер. */
import type { Metadata } from "next";
import Link from "next/link";
import { Hero } from "@/components/layout/PageBlocks";
import { WriteToSurferButton } from "@/components/public/CatalogIslands";
import { Avatar } from "@/components/ui";
import { serverFetchSafe } from "@/lib/api/server";
import type { SurferCard } from "@/lib/api/publicCatalogs";
import type { Paginated } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

export const revalidate = 60;
type SP = Promise<Record<string, string | string[] | undefined>>;

export const metadata: Metadata = buildMetadata({
  title: "GG Surfer — свои люди на волне",
  description: "Найдите компанию для катания по региону, споту и уровню. Участие в сообществе — по желанию.",
  path: routes.gg,
});

const LEVELS = [
  ["", "Любой уровень"],
  ["beginner", "Новичок"],
  ["intermediate", "Средний"],
  ["advanced", "Продвинутый"],
  ["pro", "Профи"],
];

export default async function GGPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const q = new URLSearchParams();
  for (const k of ["region", "level", "spot", "q", "page"]) if (typeof sp[k] === "string" && sp[k]) q.set(k, sp[k] as string);
  const [data, regions] = await Promise.all([
    serverFetchSafe<Paginated<SurferCard>>(`surfers?${q.toString()}`, { revalidate: 60, tags: ["surfers"] }),
    serverFetchSafe<Array<{ slug: string; name: string }>>("regions", { revalidate: 3600 }),
  ]);
  return (
    <>
      <Hero variant="home" tall={false} title="GG Surfer" text="Свои люди на волне: найдите компанию для катания, а местным — тех, кому показать спот." />
      <div className="wrap gv-page-body">
        <p className="gg-kindness small">
          В каталоге только те, кто сам включил GG Surfer в настройках. Регион и возраст показываются по выбору участника.{" "}
          <Link href={routes.account.settings}>Включить GG Surfer →</Link>
        </p>
        <form className="gg-filters filters" method="get" action={routes.gg}>
          <label className="filter">
            <span>Регион</span>
            <select name="region" defaultValue={typeof sp.region === "string" ? sp.region : ""}>
              <option value="">Все регионы</option>
              {(regions ?? []).map((r) => (
                <option key={r.slug} value={r.slug}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            <span>Уровень</span>
            <select name="level" defaultValue={typeof sp.level === "string" ? sp.level : ""}>
              {LEVELS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            <span>Поиск</span>
            <input name="q" defaultValue={typeof sp.q === "string" ? sp.q : ""} placeholder="Имя, интересы" />
          </label>
          <button className="btn primary" type="submit">
            Найти
          </button>
        </form>
        {!data || data.results.length === 0 ? (
          <div className="gv-spot-empty">
            <h3>Пока никого не нашли</h3>
            <p>Попробуйте другой регион или уровень.</p>
          </div>
        ) : (
          <div className="member-list grid-3">
            {data.results.map((s) => (
              <article key={s.id} className="member-card">
                <div className="member-card-top">
                  <Avatar media={s.avatar} name={s.display_name} size={64} />
                  <div>
                    <h3 className="member-card-name">
                      <Link href={routes.surfer(s.handle)}>{s.display_name}</Link>
                    </h3>
                    <div className="small muted">
                      {[s.region?.name, s.riding_level_label, s.age ? `${s.age} лет` : "", s.experience_years ? `стаж ${s.experience_years} л.` : ""].filter(Boolean).join(" · ")}
                    </div>
                  </div>
                </div>
                {s.bio_excerpt && <p>{s.bio_excerpt}</p>}
                {s.favorite_spots.length > 0 && <p className="small">Споты: {s.favorite_spots.map((f) => f.name).join(", ")}</p>}
                {s.interests.length > 0 && <p className="small muted">{s.interests.join(" · ")}</p>}
                <div className="member-card-foot">
                  {!s.is_me && <WriteToSurferButton accountId={s.id} canMessage={s.can_message} acceptsMessages={s.accepts_messages} />}
                  <Link href={routes.surfer(s.handle)}>Профиль →</Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
