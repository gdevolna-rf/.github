import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/seo";

/** robots.txt (NAV-05, ATX-32): public catalogues are crawlable, private/auth areas are not. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/account", "/moderation", "/dev/", "/api/", "/admin/", "/invites/", "/login", "/register", "/verify-email", "/reset-password", "/search"],
      },
    ],
    sitemap: `${siteUrl()}/sitemap.xml`,
    host: siteUrl(),
  };
}
