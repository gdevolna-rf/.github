import type { ReactNode } from "react";

/**
 * /shapers segment: the catalogue (`children`) + the `@modal` slot. A soft navigation from the catalogue to
 * /shapers/[slug] is intercepted by `@modal/(.)[slug]` and shows the profile as a modal over the list with its
 * own URL (SHP-10, UX-12); a direct visit renders the standalone SEO page app/shapers/[slug]/page.tsx.
 */
export default function ShapersLayout({ children, modal }: { children: ReactNode; modal: ReactNode }) {
  return (
    <>
      {children}
      {modal}
    </>
  );
}
