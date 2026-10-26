import { cx } from "@/lib/cx";

/** Small wave-coloured spinner. Decorative: pair it with visible text or aria-busy on the parent. */
export function Spinner({ size = 18, className }: { size?: number; className?: string }) {
  return (
    <span className={cx("gv-spinner", className)} style={{ width: size, height: size }} aria-hidden="true" />
  );
}
