import Link from "next/link";
import { FOOTER_NAV } from "@/lib/routes";
import { Icon } from "@/components/ui/Icon";

/** Prototype footer (DESIGN_SYSTEM §3.26): landscape photo, logo, white pill nav, copyright. */
export function SiteFooter() {
  return (
    <footer className="footer">
      <div className="wrap footer-inner">
        <Link className="logo" href="/" aria-label="Гдеволна.рф — на главную">
          <img src="/brand/logo.png" alt="Гдеволна" width={132} height={76} loading="lazy" />
        </Link>
        <nav aria-label="Разделы сайта (подвал)">
          {FOOTER_NAV.map((l) => (
            <Link key={l.href} href={l.href}>
              {l.label}
            </Link>
          ))}
        </nav>
        <span className="footer-glyphs" aria-hidden="true">
          <Icon name="target" size={20} />
          <Icon name="diamond" size={20} />
          <Icon name="waves" size={20} />
        </span>
      </div>
      <div className="wrap footer-bottom">© {new Date().getFullYear()} Гдеволна.рф · Сделано с любовью к российскому сёрфингу</div>
    </footer>
  );
}
