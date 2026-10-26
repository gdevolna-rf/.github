/**
 * SEO helpers (NAV-05, ATX-32): canonical URLs on PUBLIC_SITE_URL, OpenGraph, robots.
 * Use `buildMetadata()` from `generateMetadata()` of every public page.
 */
import type { Metadata } from "next";

export const SITE_NAME = "Гдеволна.рф";
export const SITE_TAGLINE = "где волна, там свои";
export const DEFAULT_DESCRIPTION =
  "Споты, сёрф-инструкторы, школы, шейперы и аренда снаряжения для сёрфинга в России — от Камчатки и Сахалина до Крыма.";
export const DEFAULT_OG_IMAGE = "/ui/hero-home.webp";

/** Public origin, e.g. https://гдеволна.рф (env PUBLIC_SITE_URL; http://localhost:8080 in dev). */
export function siteUrl(): string {
  return (process.env.PUBLIC_SITE_URL || process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:8080").replace(/\/+$/, "");
}

export function absoluteUrl(path = "/"): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${siteUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

export interface PageMeta {
  title?: string;
  description?: string;
  /** Path of the canonical URL ("/spots/khalaktyrskiy-plyazh"); query strings are dropped. */
  path: string;
  image?: string | null;
  type?: "website" | "article" | "profile";
  /** Private / thin pages (account, auth, search results). */
  noindex?: boolean;
}

export function buildMetadata({ title, description, path, image, type = "website", noindex }: PageMeta): Metadata {
  const canonical = path.split("?")[0] || "/";
  const desc = description || DEFAULT_DESCRIPTION;
  const img = image || DEFAULT_OG_IMAGE;
  return {
    title,
    description: desc,
    alternates: { canonical },
    openGraph: {
      type,
      locale: "ru_RU",
      siteName: SITE_NAME,
      url: canonical,
      title: title ? `${title} · ${SITE_NAME}` : `${SITE_NAME} — ${SITE_TAGLINE}`,
      description: desc,
      images: [{ url: img }],
    },
    twitter: { card: "summary_large_image", title: title ?? SITE_NAME, description: desc, images: [img] },
    robots: noindex ? { index: false, follow: false } : undefined,
  };
}

/** Root metadata: title template, metadataBase (makes canonical/OG URLs absolute). */
export function rootMetadata(): Metadata {
  return {
    metadataBase: new URL(siteUrl()),
    title: { default: `${SITE_NAME} — ${SITE_TAGLINE}`, template: `%s · ${SITE_NAME}` },
    description: DEFAULT_DESCRIPTION,
    applicationName: SITE_NAME,
    alternates: { canonical: "/" },
    openGraph: {
      type: "website",
      locale: "ru_RU",
      siteName: SITE_NAME,
      title: `${SITE_NAME} — ${SITE_TAGLINE}`,
      description: DEFAULT_DESCRIPTION,
      images: [{ url: DEFAULT_OG_IMAGE }],
    },
    formatDetection: { telephone: false, email: false, address: false },
  };
}

/** JSON-LD helper: <script type="application/ld+json" dangerouslySetInnerHTML={jsonLd(obj)} /> */
export function jsonLd(data: Record<string, unknown>): { __html: string } {
  return { __html: JSON.stringify(data).replace(/</g, "\\u003c") };
}
