import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Providers } from "@/components/providers";
import { MobileTabBar } from "@/components/layout/MobileTabBar";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { OfflineBanner } from "@/components/ui/OfflineBanner";
import { rootMetadata } from "@/lib/seo";

export const metadata: Metadata = rootMetadata();

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // env(safe-area-inset-*) needs viewport-fit=cover (bottom tab bar on iPhone, ATX-22)
  viewportFit: "cover",
  themeColor: "#f9fdff",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <Providers>
          <a href="#app" className="gv-skip-link">
            Перейти к содержанию
          </a>
          <SiteHeader />
          <OfflineBanner />
          <main id="app" tabIndex={-1}>
            {children}
          </main>
          <SiteFooter />
          <MobileTabBar />
        </Providers>
      </body>
    </html>
  );
}
