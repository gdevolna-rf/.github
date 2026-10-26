/**
 * Shared public page blocks from the prototype (Server Components):
 *   <Hero variant="home|people" title text cta />   — `.hero` photo header (DESIGN_SYSTEM §3.3)
 *   <SectionTitle>…</SectionTitle>                   — `.section-title` with the ◈ prefix
 *   <WideBanner />                                   — «Где волна — там жизнь» strip (home/spots/GG/rentals)
 *   <PageHead title text />                          — `.pagehead` (h2 29px + lead)
 */
import type { CSSProperties, ReactNode } from "react";
import { cx } from "@/lib/cx";
import { routes } from "@/lib/routes";
import { ButtonLink } from "@/components/ui/Button";

export function Hero({
  variant = "people",
  tall,
  kicker = "Люди · волны · Россия",
  title,
  text,
  cta,
  photo,
}: {
  /** home: surfer on rocks (Главная, GG Surfer); people: surfer on a wave (catalogues) */
  variant?: "home" | "people";
  tall?: boolean;
  kicker?: string;
  title: ReactNode;
  text?: ReactNode;
  cta?: { href: string; label: string };
  /** override the background photo (URL) */
  photo?: string;
}) {
  const style = photo ? ({ [variant === "people" ? "--people-photo" : "--hero-photo"]: `url(${photo})` } as CSSProperties) : undefined;
  return (
    <section className={cx("hero", variant === "people" && "people", (tall ?? variant === "home") && "tall")} style={style}>
      <div className="wrap">
        <div className="kicker">{kicker}</div>
        <h1>{title}</h1>
        {text && <p>{text}</p>}
        {cta && (
          <ButtonLink href={cta.href} variant="primary" iconRight="arrow">
            {cta.label}
          </ButtonLink>
        )}
      </div>
    </section>
  );
}

export function SectionTitle({ children, as: H = "h2", id, className }: { children: ReactNode; as?: "h1" | "h2" | "h3"; id?: string; className?: string }) {
  return (
    <H className={cx("section-title", className)} id={id}>
      {children}
    </H>
  );
}

export function PageHead({ title, text }: { title: ReactNode; text?: ReactNode }) {
  return (
    <div className="pagehead">
      <h2>{title}</h2>
      {text && <p>{text}</p>}
    </div>
  );
}

export function WideBanner({
  title = "Где волна — там жизнь",
  text = "Вулканы, снег, Ладога и горы Крыма. Открывайте для себя новые горизонты!",
  cta = { href: routes.spots, label: "Перейти к карте спотов" },
}: {
  title?: string;
  text?: string;
  cta?: { href: string; label: string };
}) {
  return (
    <div className="wide-banner">
      <div>
        <h2>{title}</h2>
        <p>{text}</p>
        <ButtonLink href={cta.href} variant="pill" iconRight="arrow">
          {cta.label}
        </ButtonLink>
      </div>
    </div>
  );
}
