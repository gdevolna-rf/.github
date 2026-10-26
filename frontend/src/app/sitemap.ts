import type { MetadataRoute } from "next";
import { serverFetchAll } from "@/lib/api/server";
import { routes, STATIC_PUBLIC_ROUTES } from "@/lib/routes";
import { absoluteUrl } from "@/lib/seo";

/**
 * sitemap.xml (NAV-05, ATX-32): static sections + every published card from the public API.
 * Each source is fetched independently; a failing/unfinished endpoint is skipped, never breaks the sitemap.
 */
export const revalidate = 3600;

type Item = { slug?: string; handle?: string; id?: string | number; updated_at?: string; modified_at?: string };

const SOURCES: Array<{ path: string; query?: Record<string, string>; url: (i: Item) => string | null; priority: number }> = [
  { path: "spots", url: (i) => (i.slug ? routes.spot(i.slug) : null), priority: 0.8 },
  { path: "instructors", url: (i) => (i.handle ? routes.instructor(i.handle) : null), priority: 0.7 },
  { path: "organizations", query: { kind: "school" }, url: (i) => (i.slug ? routes.school(i.slug) : null), priority: 0.7 },
  { path: "shapers", url: (i) => (i.slug ? routes.shaper(i.slug) : null), priority: 0.6 },
  { path: "boards", url: (i) => (i.id != null ? routes.board(i.id) : null), priority: 0.6 },
  { path: "rentals", url: (i) => (i.id != null ? routes.rental(i.id) : null), priority: 0.5 },
  { path: "club/events", url: (i) => (i.slug ? routes.clubEvent(i.slug) : null), priority: 0.5 },
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const entries: MetadataRoute.Sitemap = STATIC_PUBLIC_ROUTES.map((r) => ({
    url: absoluteUrl(r.path),
    lastModified: now,
    changeFrequency: r.changeFrequency,
    priority: r.priority,
  }));

  const results = await Promise.allSettled(
    SOURCES.map((s) => serverFetchAll<Item>(s.path, { query: s.query, revalidate: 3600, tags: ["sitemap"], maxPages: 50, timeoutMs: 8000 })),
  );
  const seen = new Set(entries.map((e) => e.url));
  results.forEach((res, idx) => {
    if (res.status !== "fulfilled") return;
    const source = SOURCES[idx];
    for (const item of res.value) {
      const path = source.url(item);
      if (!path) continue;
      const url = absoluteUrl(path);
      if (seen.has(url)) continue;
      seen.add(url);
      const modified = item.updated_at ?? item.modified_at;
      entries.push({ url, lastModified: modified ? new Date(modified) : undefined, changeFrequency: "weekly", priority: source.priority });
    }
  });
  return entries;
}
