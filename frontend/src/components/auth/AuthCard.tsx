import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

/** Auth screens use the prototype modal look as a page card (PUBLIC_SCREENS §12: «same modal style»). */
export function AuthCard({
  title,
  lead,
  children,
  footer,
  narrow,
}: {
  title: string;
  lead?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  narrow?: boolean;
}) {
  return (
    <div className={cx("gv-auth", narrow && "is-narrow")}>
      <section className="gv-auth-card" aria-labelledby="auth-title">
        <h1 id="auth-title">{title}</h1>
        {lead && <p className="gv-auth-lead">{lead}</p>}
        {children}
        {footer && <div className="gv-auth-foot">{footer}</div>}
      </section>
    </div>
  );
}

export function FormError({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <div className="gv-form-error" role="alert">
      {message}
    </div>
  );
}
