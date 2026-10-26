import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "@/lib/cx";
import { Icon, type IconName } from "./Icon";
import { Spinner } from "./Spinner";

/**
 * Prototype button styles (DESIGN_SYSTEM §3.2):
 *  primary — gradient CTA (`.primary`; white on hero photos automatically)
 *  line    — outlined rounded rect (`.line-btn`, header «Войти»)
 *  pill    — outlined pill (`.pill-btn`, «Узнать о проекте →», «Сбросить»)
 *  link    — text link button (`.feature-link`, «Перейти →»)
 *  soft    — cabinet button (`.gv-ac-btn`)
 *  danger  — outline danger (`.lesson-outline-danger`, «Отменить заявку»)
 */
export type ButtonVariant = "primary" | "line" | "pill" | "link" | "soft" | "danger";

const VARIANT: Record<ButtonVariant, string> = {
  primary: "primary",
  line: "line-btn",
  pill: "pill-btn",
  link: "feature-link",
  soft: "gv-ac-btn",
  danger: "lesson-outline-danger",
};

interface CommonProps {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  /** full width */
  block?: boolean;
  icon?: IconName;
  iconRight?: IconName;
  children?: ReactNode;
  className?: string;
}

function classes({ variant = "primary", size, block, className }: CommonProps, extra?: string) {
  return cx(VARIANT[variant], size === "sm" && "gv-btn-sm", block && "gv-block", extra, className);
}

function Content({ icon, iconRight, loading, children }: CommonProps & { loading?: boolean }) {
  return (
    <>
      {loading ? <Spinner size={16} /> : icon ? <Icon name={icon} size={16} /> : null}
      {children !== undefined && children !== null && <span className="gv-btn-label">{children}</span>}
      {iconRight && <Icon name={iconRight} size={16} />}
    </>
  );
}

export interface ButtonProps extends CommonProps, Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "className"> {
  /** Shows a spinner, disables the button and sets aria-busy. */
  loading?: boolean;
}

export function Button({ variant, size, block, icon, iconRight, loading, children, className, type = "button", disabled, ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={classes({ variant, size, block, className }, loading ? "is-loading" : undefined)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      <Content icon={icon} iconRight={iconRight} loading={loading}>
        {children}
      </Content>
    </button>
  );
}

export interface ButtonLinkProps extends CommonProps, Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "children" | "className" | "href"> {
  href: string;
  prefetch?: boolean;
}

/** Same look as Button, rendered as a Next.js <Link> (navigation must be a link, not a button). */
export function ButtonLink({ href, variant, size, block, icon, iconRight, children, className, prefetch, ...rest }: ButtonLinkProps) {
  const external = /^https?:\/\//.test(href);
  if (external) {
    return (
      <a href={href} className={classes({ variant, size, block, className })} target="_blank" rel="noopener noreferrer" {...rest}>
        <Content icon={icon} iconRight={iconRight ?? "external"}>
          {children}
        </Content>
      </a>
    );
  }
  return (
    <Link href={href} prefetch={prefetch} className={classes({ variant, size, block, className })} {...rest}>
      <Content icon={icon} iconRight={iconRight}>
        {children}
      </Content>
    </Link>
  );
}
