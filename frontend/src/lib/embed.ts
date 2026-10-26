/**
 * Video embed URL from a YouTube / RuTube link (prototype `normaliseStream`, PUBLIC_SCREENS §13.3).
 * Only https; YouTube → youtube-nocookie.com/embed/{id}; RuTube /video/{id} → rutube.ru/play/embed/{id}.
 * Returns null for anything else — never embed arbitrary URLs.
 */
export function toEmbedUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw);
    if (u.protocol !== "https:") return null;
    const host = u.hostname.toLowerCase();
    const okId = (id: string | null | undefined) => (id && /^[-_a-zA-Z0-9]{6,20}$/.test(id) ? id : null);
    if (host === "youtu.be") {
      const id = okId(u.pathname.slice(1).split("/")[0]);
      return id ? `https://www.youtube-nocookie.com/embed/${id}` : null;
    }
    if (["youtube.com", "www.youtube.com", "m.youtube.com"].includes(host)) {
      const id = okId(u.searchParams.get("v") || u.pathname.split("/").filter(Boolean).pop());
      return id ? `https://www.youtube-nocookie.com/embed/${id}` : null;
    }
    if (["rutube.ru", "www.rutube.ru"].includes(host)) {
      const id = (u.pathname.match(/video\/([\w-]+)/) || [])[1];
      return id ? `https://rutube.ru/play/embed/${id}` : null;
    }
    return null;
  } catch {
    return null;
  }
}
