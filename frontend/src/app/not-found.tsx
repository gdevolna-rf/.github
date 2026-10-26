import type { Metadata } from "next";
import { routes } from "@/lib/routes";
import { ButtonLink } from "@/components/ui/Button";

export const metadata: Metadata = { title: "Страница не найдена", robots: { index: false, follow: true } };

/** 404 for unknown URLs and notFound() — prototype empty-state language. */
export default function NotFound() {
  return (
    <div className="gv-special">
      <div className="empty surfer-empty gv-empty">
        <span className="gv-empty-art" aria-hidden="true" />
        <h1 className="gv-special-title">Похоже, эта волна уже ушла</h1>
        <p>Страница не найдена: возможно, ссылка устарела или адрес набран с ошибкой.</p>
        <div className="view-tools">
          <ButtonLink href="/" variant="primary" iconRight="arrow">
            На главную
          </ButtonLink>
          <ButtonLink href={routes.spots} variant="pill">
            Карта спотов
          </ButtonLink>
          <ButtonLink href={routes.search()} variant="pill" icon="search">
            Поиск
          </ButtonLink>
        </div>
      </div>
    </div>
  );
}
