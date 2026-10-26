/**
 * Frontend routes (ARCHITECTURE §9) and navigation config — the single source for header, footer,
 * mobile tab bar, catalog sheet, account navigation and sitemap. Never hard-code these paths in pages.
 */
import type { IconName } from "@/components/ui/icons/registry";

const seg = (v: string | number) => encodeURIComponent(String(v));

export const routes = {
  home: "/",
  spots: "/spots",
  spot: (slug: string) => `/spots/${seg(slug)}`,
  instructors: "/instructors",
  instructor: (handle: string) => `/instructors/${seg(handle)}`,
  schools: "/schools",
  school: (slug: string) => `/schools/${seg(slug)}`,
  session: (id: string) => `/sessions/${seg(id)}`,
  shapers: "/shapers",
  boardsCatalog: "/shapers?tab=boards",
  shaper: (slug: string) => `/shapers/${seg(slug)}`,
  board: (id: string | number) => `/boards/${seg(id)}`,
  rentals: "/rentals",
  rental: (id: string | number) => `/rentals/${seg(id)}`,
  gg: "/gg",
  surfer: (handle: string) => `/surfers/${seg(handle)}`,
  club: "/club",
  clubEvent: (slug: string) => `/club/events/${seg(slug)}`,
  shop: "/shop",
  product: (slug: string) => `/shop/${seg(slug)}`,
  search: (q?: string) => (q ? `/search?q=${encodeURIComponent(q)}` : "/search"),
  assistant: "/assistant",
  login: "/login",
  register: "/register",
  verifyEmail: "/verify-email",
  resetPassword: "/reset-password",
  invite: (token: string) => `/invites/${seg(token)}`,
  account: {
    root: "/account",
    profile: "/account/profile",
    settings: "/account/settings",
    specialties: "/account/specialties",
    inquiries: "/account/inquiries",
    inquiry: (id: string) => `/account/inquiries/${seg(id)}`,
    bookings: "/account/bookings",
    booking: (id: string) => `/account/bookings/${seg(id)}`,
    favorites: "/account/favorites",
    notifications: "/account/notifications",
    proposals: "/account/proposals",
    reviews: "/account/reviews",
    invites: "/account/invites",
    diary: "/account/diary",
    instructor: "/account/instructor",
    shaper: "/account/shaper",
    rental: "/account/rental",
    orgs: "/account/orgs",
    org: (id: string) => `/account/orgs/${seg(id)}`,
  },
  moderation: "/moderation",
} as const;

export interface NavItem {
  href: string;
  label: string;
  /** Short label for narrow desktops (≤1100px) and the catalog sheet title. */
  short: string;
  icon: IconName;
  description: string;
  /** Path prefixes that make the item active. */
  match: string[];
}

/** NAV-01: every section of the site, in header order. */
export const MAIN_NAV: NavItem[] = [
  {
    href: routes.instructors,
    label: "Каталог сёрф-инструкторов",
    short: "Инструкторы",
    icon: "clover",
    description: "Опытные инструкторы, отзывы учеников и запись на занятие.",
    match: ["/instructors"],
  },
  {
    href: routes.spots,
    label: "Карта сёрф-спотов",
    short: "Споты",
    icon: "target",
    description: "Места для сёрфинга, условия волны и важные детали.",
    match: ["/spots"],
  },
  {
    href: routes.gg,
    label: "GG Surfer",
    short: "GG Surfer",
    icon: "heart",
    description: "Свои люди в регионе: компания для катания и подсказки.",
    match: ["/gg", "/surfers"],
  },
  {
    href: routes.rentals,
    label: "Аренда",
    short: "Аренда",
    icon: "board",
    description: "Доски и гидрокостюмы у своих — в нужном регионе.",
    match: ["/rentals"],
  },
  {
    href: routes.shapers,
    label: "Шейперы",
    short: "Шейперы",
    icon: "ruler",
    description: "Мастерские и доски ручной работы: все модели и профили мастеров.",
    match: ["/shapers", "/boards"],
  },
  {
    href: routes.club,
    label: "О нас и клуб",
    short: "Клуб",
    icon: "sparkle",
    description: "Открытое сообщество, события и дружеские встречи.",
    match: ["/club"],
  },
  {
    href: routes.schools,
    label: "Сёрф-школы",
    short: "Школы",
    icon: "school",
    description: "Школы, программы обучения и ближайшие занятия со свободными местами.",
    match: ["/schools", "/sessions"],
  },
];

/** Footer links (prototype order + schools). */
export const FOOTER_NAV: Array<{ href: string; label: string }> = [
  { href: routes.instructors, label: "Каталог сёрф-инструкторов" },
  { href: routes.spots, label: "Карта спотов" },
  { href: routes.schools, label: "Сёрф-школы" },
  { href: routes.gg, label: "GG Surfer" },
  { href: routes.rentals, label: "Аренда" },
  { href: routes.shapers, label: "Шейперы" },
  { href: routes.club, label: "О нас и клуб" },
];

/** Paths under which the «Каталог» tab of the mobile bar is active. */
export const CATALOG_PREFIXES = MAIN_NAV.flatMap((i) => i.match).concat(["/search", "/shop", "/assistant"]);

export function isActivePath(pathname: string, prefixes: string[]): boolean {
  return prefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/** Static public routes for sitemap.ts. */
export const STATIC_PUBLIC_ROUTES: Array<{ path: string; priority: number; changeFrequency: "daily" | "weekly" | "monthly" }> = [
  { path: routes.home, priority: 1, changeFrequency: "daily" },
  { path: routes.spots, priority: 0.9, changeFrequency: "daily" },
  { path: routes.instructors, priority: 0.9, changeFrequency: "daily" },
  { path: routes.schools, priority: 0.8, changeFrequency: "daily" },
  { path: routes.shapers, priority: 0.8, changeFrequency: "daily" },
  { path: routes.rentals, priority: 0.8, changeFrequency: "daily" },
  { path: routes.gg, priority: 0.6, changeFrequency: "weekly" },
  { path: routes.club, priority: 0.6, changeFrequency: "weekly" },
];
