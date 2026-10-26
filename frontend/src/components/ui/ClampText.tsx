"use client";
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { cx } from "@/lib/cx";

/**
 * Long user text (UX-13, DSN-06): clamps to `lines` and offers «Показать полностью» only when it overflows.
 * Use for descriptions, reviews, bios. Titles use CSS `.gv-clamp-1/2` + full text in `title`.
 */
export function ClampText({ children, lines = 4, className }: { children: ReactNode; lines?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const id = useId();
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || expanded) return;
    const check = () => setOverflows(el.scrollHeight - el.clientHeight > 2);
    check();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [children, expanded, lines]);

  return (
    <div className={cx("gv-clamp", className)}>
      <div
        id={id}
        ref={ref}
        className="gv-clamp-body"
        style={expanded ? undefined : { WebkitLineClamp: lines, lineClamp: lines } as CSSProperties}
        data-expanded={expanded || undefined}
      >
        {children}
      </div>
      {(overflows || expanded) && (
        <button type="button" className="feature-link gv-clamp-toggle" aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Свернуть" : "Показать полностью"}
        </button>
      )}
    </div>
  );
}
