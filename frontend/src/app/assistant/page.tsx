/**
 * Помощник подбора (AIX-01…03, ARCHITECTURE §9 `/assistant`): rule-based beta — no AI, only catalogue data with
 * sources and safety disclaimers. Server Component shell (regions and hazard labels for the forms) + client
 * island with two tools: recommendations by region/level and the board volume calculator.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { AssistantTools } from "@/components/assistant/AssistantTools";
import { boardFromParams, BOARD_PARAMS, RECOMMEND_PARAMS, recommendFromParams } from "@/components/assistant/assistantModel";
import type { RegionOption } from "@/components/assistant/RecommendTool";
import { Hero } from "@/components/layout/PageBlocks";
import { Icon } from "@/components/ui/Icon";
import { Tag } from "@/components/ui/Badge";
import { serverFetchSafe } from "@/lib/api/server";
import { routes } from "@/lib/routes";
import { buildMetadata } from "@/lib/seo";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export const metadata: Metadata = buildMetadata({
  title: "Помощник подбора",
  description:
    "Подбор спота, инструктора, проката и объёма доски по простым правилам на данных каталога Гдеволны — с источниками и оговорками о безопасности.",
  path: "/assistant",
});

interface Dictionaries {
  hazards?: Array<{ code: string; label: string }>;
}

export default async function AssistantPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const [regions, dictionaries] = await Promise.all([
    serverFetchSafe<RegionOption[]>("regions", { revalidate: 3600, tags: ["regions"] }),
    serverFetchSafe<Dictionaries>("spots/dictionaries", { revalidate: 3600, tags: ["spots"] }),
  ]);
  const hazardLabels = Object.fromEntries((dictionaries?.hazards ?? []).map((h) => [h.code, h.label]));
  const hasBoard = Object.values(BOARD_PARAMS).some((k) => params[k]);
  const hasRecommend = Object.values(RECOMMEND_PARAMS).some((k) => params[k]);

  return (
    <>
      <Hero
        variant="people"
        kicker="Бета · подбор по правилам"
        title="Помощник подбора"
        text="Подскажем спот под ваш уровень, инструктора, прокат и объём доски — по понятным правилам и данным каталога."
      />
      <div className="wrap gv-ax-page">
        <section className="section" aria-labelledby="ax-about">
          <div className="gv-ax-intro">
            <div>
              <h2 id="ax-about" className="gv-ax-intro-title">
                Как это работает <Tag variant="gg">бета · подбор по правилам, не ИИ</Tag>
              </h2>
              <p>
                Помощник не придумывает ответы: он отбирает опубликованные споты, профили и объявления по уровню,
                региону и сезону, а объём доски считает по открытой формуле. У каждой рекомендации указан источник и
                дата обновления данных. Прогноз показываем, только если он есть у провайдера на выбранную дату.
              </p>
            </div>
            <p className="notice gv-ax-safety" role="note">
              <Icon name="shield" size={16} /> <b>Безопасность прежде всего.</b> Подборка — ориентир, а не гарантия:
              перед выходом в воду проверьте прогноз и штормовые предупреждения, оцените течения и свои силы, не
              катайтесь в одиночку на незнакомом споте. Сомневаетесь — <Link href={routes.instructors}>возьмите занятие с инструктором</Link>.
            </p>
          </div>
          <AssistantTools
            regions={regions ?? []}
            hazardLabels={hazardLabels}
            initialBoard={hasBoard ? boardFromParams(params) : undefined}
            initialRecommend={hasRecommend ? recommendFromParams(params) : undefined}
          />
        </section>
      </div>
    </>
  );
}
