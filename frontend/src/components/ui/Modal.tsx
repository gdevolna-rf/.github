"use client";
/**
 * Accessible modal (UX-12, ATX-31, prototype DESIGN_SYSTEM §3.16 look):
 * - role="dialog" + aria-modal + aria-labelledby (title is required; hide it visually with hideTitle);
 * - focus moves inside on open, Tab/Shift+Tab are trapped, focus returns to the opener on close;
 * - Escape closes the top-most modal; click/tap on the backdrop closes (only when the press started there);
 * - page scroll is locked; the rest of the page is `inert` (not focusable, hidden from screen readers);
 * - stacking: a modal opened from a modal works, Escape closes only the top one.
 * Deep links (SHP-10): drive `open` from the URL with useSearchParamModal() or use <RouteModal>.
 */
import { createPortal } from "react-dom";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import { useRouter } from "next/navigation";
import { cx } from "@/lib/cx";
import { Icon } from "./Icon";

export type ModalSize = "default" | "wide" | "xl" | "sheet";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  hideTitle?: boolean;
  description?: ReactNode;
  size?: ModalSize;
  children?: ReactNode;
  /** Sticky action row at the bottom (buttons). */
  footer?: ReactNode;
  /** Element to focus on open; default: `[data-autofocus]` inside, else the dialog itself. */
  initialFocusRef?: RefObject<HTMLElement | null>;
  closeOnBackdrop?: boolean;
  closeLabel?: string;
  className?: string;
}

const FOCUSABLE =
  'a[href], area[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), iframe, audio[controls], video[controls], [contenteditable]:not([contenteditable="false"]), [tabindex]:not([tabindex="-1"])';

function focusables(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => !el.closest("[hidden]") && !el.closest("[inert]") && el.getAttribute("aria-hidden") !== "true",
  );
}

/* ---- module-level stack: scroll lock + inert background shared by all open modals ---- */
const stack: HTMLElement[] = [];
let savedBodyOverflow = "";
let savedBodyPadding = "";

function syncPage() {
  const top = stack[stack.length - 1];
  for (const el of Array.from(document.body.children)) {
    if (!(el instanceof HTMLElement) || el.hasAttribute("data-modal-exempt")) continue;
    const shouldInert = Boolean(top) && el !== top;
    const marked = el.getAttribute("data-gv-inert");
    if (shouldInert && !marked) {
      el.setAttribute("data-gv-inert", el.hasAttribute("inert") ? "keep" : "set");
      el.setAttribute("inert", "");
    } else if (!shouldInert && marked) {
      if (marked === "set") el.removeAttribute("inert");
      el.removeAttribute("data-gv-inert");
    }
  }
  const body = document.body;
  if (top && !body.hasAttribute("data-scroll-locked")) {
    const scrollbar = window.innerWidth - document.documentElement.clientWidth;
    savedBodyOverflow = body.style.overflow;
    savedBodyPadding = body.style.paddingRight;
    body.style.overflow = "hidden";
    if (scrollbar > 0) body.style.paddingRight = `${scrollbar}px`;
    body.setAttribute("data-scroll-locked", "");
  } else if (!top && body.hasAttribute("data-scroll-locked")) {
    body.style.overflow = savedBodyOverflow;
    body.style.paddingRight = savedBodyPadding;
    body.removeAttribute("data-scroll-locked");
  }
}

export function Modal({
  open,
  onClose,
  title,
  hideTitle,
  description,
  size = "default",
  children,
  footer,
  initialFocusRef,
  closeOnBackdrop = true,
  closeLabel = "Закрыть",
  className,
}: ModalProps) {
  const [mounted, setMounted] = useState(false);
  const backdropRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const pressedOnBackdrop = useRef(false);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const id = useId().replace(/:/g, "");
  const titleId = `${id}-title`;
  const descId = description ? `${id}-desc` : undefined;

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open || !mounted) return;
    const backdrop = backdropRef.current;
    const panel = panelRef.current;
    if (!backdrop || !panel) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    stack.push(backdrop);
    syncPage();

    const target = initialFocusRef?.current ?? panel.querySelector<HTMLElement>("[data-autofocus]") ?? panel;
    target.focus({ preventScroll: true });

    const onKeyDown = (e: KeyboardEvent) => {
      if (stack[stack.length - 1] !== backdrop) return;
      if (e.key === "Escape") {
        e.stopPropagation();
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables(panel);
      if (!items.length) {
        e.preventDefault();
        panel.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === panel || !panel.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || !panel.contains(active))) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown, true);

    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      const idx = stack.indexOf(backdrop);
      if (idx >= 0) stack.splice(idx, 1);
      syncPage();
      if (opener && opener.isConnected) opener.focus({ preventScroll: true });
    };
  }, [open, mounted, initialFocusRef]);

  if (!open || !mounted) return null;

  return createPortal(
    <div
      ref={backdropRef}
      className={cx("modal-backdrop", "gv-modal-backdrop", size === "sheet" && "is-sheet")}
      onPointerDown={(e) => {
        pressedOnBackdrop.current = e.target === e.currentTarget;
      }}
      onClick={(e) => {
        if (closeOnBackdrop && pressedOnBackdrop.current && e.target === e.currentTarget) onCloseRef.current();
        pressedOnBackdrop.current = false;
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        tabIndex={-1}
        className={cx("modal", "gv-modal", size === "wide" && "wide", size === "xl" && "wide gv-modal-xl", size === "sheet" && "gv-sheet", className)}
      >
        <button type="button" className="close gv-modal-close" aria-label={closeLabel} onClick={() => onCloseRef.current()}>
          <Icon name="close" size={18} />
        </button>
        <h2 id={titleId} className={cx("gv-modal-title", hideTitle && "sr-only")}>
          {title}
        </h2>
        {description && (
          <p id={descId} className="gv-modal-desc">
            {description}
          </p>
        )}
        <div className="gv-modal-body">{children}</div>
        {footer && <div className="gv-modal-footer">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

/**
 * Modal for an intercepting route (`app/shapers/@modal/(.)[slug]/page.tsx`): the URL is the real profile
 * URL (deep link, SEO page exists separately), closing goes back in history (SHP-10).
 */
export function RouteModal(props: Omit<ModalProps, "open" | "onClose"> & { onClose?: () => void }) {
  const router = useRouter();
  const close = useCallback(() => {
    props.onClose?.();
    router.back();
  }, [props, router]);
  return <Modal {...props} open onClose={close} />;
}
