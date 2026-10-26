import type { SVGProps } from "react";
import { cx } from "@/lib/cx";
import { ICONS, type IconName } from "./icons/registry";

export type { IconName };

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name" | "children"> {
  name: IconName;
  /** px; CSS may override (e.g. header buttons render icons at 21px). */
  size?: number;
  /** Accessible name. Without it the icon is decorative (aria-hidden). */
  title?: string;
  /** Fill the shape with currentColor (active heart, filled star). */
  filled?: boolean;
}

const escapeXml = (s: string) => s.replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" })[c]!);

/**
 * One icon family (UX-04): 24px grid, stroke 1.9, round caps, currentColor; optically centred because
 * every glyph shares the same viewBox. Works in Server and Client Components.
 */
export function Icon({ name, size = 20, title, filled, className, ...rest }: IconProps) {
  const def = ICONS[name];
  if (!def) return null;
  return (
    <svg
      viewBox={def.viewBox}
      width={size}
      height={size}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={def.strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
      className={cx("gv-icon", className)}
      {...rest}
      dangerouslySetInnerHTML={{ __html: (title ? `<title>${escapeXml(title)}</title>` : "") + def.body }}
    />
  );
}
