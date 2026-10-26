/**
 * Главная (PUBLIC_SCREENS §2) — Server Component, ISR every 5 min.
 * Prototype blocks 1:1: hero · «О сайте» + «Как пользоваться сайтом» · live panel · features · «Свои люди рядом» ·
 * wide banner. Added: spot and instructor teasers from the public API (hidden when the API has no data yet).
 */
import type { Metadata } from "next";
import Link from "next/link";
import { listResults, serverFetchSafe } from "@/lib/api/server";
import type { InstructorListItem, Paginated, SpotListItem } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { buildMetadata, DEFAULT_DESCRIPTION, jsonLd, absoluteUrl, SITE_NAME } from "@/lib/seo";
import { Hero, SectionTitle, WideBanner } from "@/components/layout/PageBlocks";
import { InstructorTeaserCard, SpotTeaserCard, TeaserSection } from "@/components/home/HomeTeasers";
import { LivePanel, type LiveEvent } from "@/components/home/LivePanel";
import { ButtonLink } from "@/components/ui/Button";
import { Icon, type IconName } from "@/components/ui/Icon";

export const revalidate = 300;

export const metadata: Metadata = {
  ...buildMetadata({ path: "/", description: DEFAULT_DESCRIPTION }),
  title: { absolute: `${SITE_NAME} — где волна, там свои` },
};

const FEATURES: Array<{ title: string; text: string; image: string; href: string; icon: IconName }> = [
  { title: "Каталог сёрф-инструкторов", text: "Опытные инструкторы, проверенные локации и удобный поиск.", image: "/ui/feature-volcano-coast.webp", href: routes.instructors, icon: "clover" },
  { title: "Карта сёрф-спотов", text: "Места для сёрфинга, прогнозные ориентиры и важные детали.", image: "/ui/feature-map-russia.svg", href: routes.spots, icon: "target" },
  { title: "GG Surfer", text: "Найдите своих людей в регионе и катайтесь вместе.", image: "/ui/feature-coast-aerial.webp", href: routes.gg, icon: "heart" },
  { title: "Каталог шейперов", text: "Мастера, создающие доски ручной работы.", image: "/ui/feature-shaper-boards.svg", href: routes.shapers, icon: "ruler" },
  { title: "Сёрф-клуб", text: "Открытое сообщество, подарки и дружеские встречи.", image: "/ui/feature-mountain-lake.webp", href: routes.club, icon: "sparkle" },
  { title: "Аренда снаряжения", text: "Доски и гидрокостюмы у своих — в нужном регионе.", image: "/ui/feature-barrel-surfer.webp", href: routes.rentals, icon: "diamond" },
];

const STEPS = [
  "Выберите регион и найдите спот",
  "Познакомьтесь с сёрферами и инструкторами",
  "Забронируйте занятие или найдите компанию",
  "Добавьте любимые места в избранное",
];

export default async function HomePage() {
  const [spotsData, instructorsData, eventsData] = await Promise.all([
    serverFetchSafe<Paginated<SpotListItem> | SpotListItem[]>("spots", { query: { page_size: 3 }, tags: ["spots"] }),
    serverFetchSafe<Paginated<InstructorListItem> | InstructorListItem[]>("instructors", { query: { page_size: 3 }, tags: ["instructors"] }),
    serverFetchSafe<Paginated<LiveEvent> | LiveEvent[]>("club/events", { query: { page_size: 6 }, tags: ["club"] }),
  ]);
  const spots = listResults(spotsData).filter((s) => s?.slug).slice(0, 3);
  const instructors = listResults(instructorsData).filter((i) => i?.handle).slice(0, 3);
  const events = listResults(eventsData).filter((e) => e?.slug);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={jsonLd({
          "@context": "https://schema.org",
          "@type": "WebSite",
          name: SITE_NAME,
          url: absoluteUrl("/"),
          inLanguage: "ru-RU",
          potentialAction: {
            "@type": "SearchAction",
            target: `${absoluteUrl("/search")}?q={search_term_string}`,
            "query-input": "required name=search_term_string",
          },
        })}
      />
      <Hero
        variant="home"
        title={
          <>
            Гдеволна.рф —<br /> где волна, там свои
          </>
        }
        text="Здесь находят любимые споты, знакомятся с людьми и открывают российский сёрфинг — от Камчатки и Сахалина до Крыма."
        cta={{ href: routes.spots, label: "Найти свою волну" }}
      />
      <div className="wrap">
        <section className="section" aria-labelledby="about-title">
          <div className="home-columns">
            <div className="about-hero">
              <h2 id="about-title">
                <Icon name="diamond" size={22} className="gv-title-icon" /> &nbsp;О сайте «Гдеволна.рф»
              </h2>
              <p>
                <b>Гдеволна.рф</b> — уютное место для тех, кто любит сёрфинг в России. Мы собираем вместе споты, инструкторов,
                мастеров досок и людей, которые понимают, зачем вставать на рассвете ради хорошей волны.
              </p>
              <p>Наше дело — помогать находить друг друга. Даже если до ближайшего океана лететь полдня.</p>
              <ButtonLink href={routes.club} variant="pill" iconRight="arrow">
                Узнать о проекте
              </ButtonLink>
            </div>
            <div className="side-card">
              <h3>
                <Icon name="clover" size={19} className="gv-title-icon" /> &nbsp;Как пользоваться сайтом
              </h3>
              <ol className="gv-steps">
                {STEPS.map((s, i) => (
                  <li key={s} className="step">
                    <i aria-hidden="true">{i + 1}</i>
                    <span>{s}</span>
                  </li>
                ))}
              </ol>
              <ButtonLink href={routes.gg} variant="pill" block className="gv-side-cta" iconRight="arrow">
                Знакомьтесь через GG Surfer
              </ButtonLink>
            </div>
          </div>
        </section>

        <LivePanel events={events} />

        <section className="section" aria-labelledby="features-title">
          <SectionTitle id="features-title">Что вы найдёте на сайте</SectionTitle>
          <div className="grid grid-3">
            {FEATURES.map((f) => (
              <article key={f.href} className="feature">
                <div className="feature-image">
                  <img src={f.image} alt="" loading="lazy" decoding="async" />
                  <span className="float-icon" aria-hidden="true">
                    <Icon name={f.icon} size={20} />
                  </span>
                </div>
                <div className="feature-body">
                  <h3>{f.title}</h3>
                  <p>{f.text}</p>
                  <Link href={f.href} className="feature-link" aria-label={`Перейти: ${f.title}`}>
                    Перейти <Icon name="arrow" size={15} />
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </section>

        {spots.length > 0 && (
          <TeaserSection title="Споты, куда стоит съездить" href={routes.spots} linkLabel="Все споты на карте">
            {spots.map((s) => (
              <SpotTeaserCard key={s.slug} spot={s} />
            ))}
          </TeaserSection>
        )}

        {instructors.length > 0 && (
          <TeaserSection title="Инструкторы рядом с волной" href={routes.instructors} linkLabel="Каталог инструкторов">
            {instructors.map((p) => (
              <InstructorTeaserCard key={p.handle} instructor={p} />
            ))}
          </TeaserSection>
        )}

        <section className="section" aria-labelledby="people-title">
          <div className="grid grid-2">
            <div>
              <SectionTitle id="people-title">Свои люди рядом</SectionTitle>
              <p className="muted">
                Приехал на Камчатку или Сахалин? Открой карту и посмотри, кто готов подсказать дорогу, показать спот или разделить
                поездку.
              </p>
              <ButtonLink href={routes.gg} variant="primary" iconRight="arrow">
                Открыть GG Surfer
              </ButtonLink>
            </div>
            <figure className="quote">
              <blockquote>«Сёрфинг — это способ увидеть мир по-новому. Особенно если рядом свои»</blockquote>
            </figure>
          </div>
        </section>

        <WideBanner />
      </div>
    </>
  );
}
