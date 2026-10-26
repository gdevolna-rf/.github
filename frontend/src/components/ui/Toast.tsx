"use client";
/**
 * Toasts (prototype `.toast`: bottom centre, #044f75, 2.9 s, one at a time — a new one replaces the old).
 *   const toast = useToast();
 *   toast.success("Профиль сохранён");
 *   toast.error(err, { action: { label: "Повторить", onClick: retry } });   // ApiError → its Russian message
 * Polite live region (errors: assertive). Sits above the mobile tab bar and the iOS safe area (ATX-22).
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import { errorMessage } from "@/lib/api/errors";

export type ToastTone = "info" | "success" | "error";

export interface ToastOptions {
  tone?: ToastTone;
  /** ms; default 2900 (prototype), 6000 for errors, 8000 with an action */
  duration?: number;
  action?: { label: string; onClick: () => void };
}

interface ToastState extends ToastOptions {
  id: number;
  message: string;
}

export interface ToastApi {
  show: (message: string, options?: ToastOptions) => void;
  info: (message: string, options?: Omit<ToastOptions, "tone">) => void;
  success: (message: string, options?: Omit<ToastOptions, "tone">) => void;
  /** Accepts a string or any thrown value (ApiError → its message). */
  error: (error: unknown, options?: Omit<ToastOptions, "tone">) => void;
  dismiss: () => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seq = useRef(0);

  const dismiss = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    setToast(null);
  }, []);

  const show = useCallback((message: string, options: ToastOptions = {}) => {
    if (timer.current) clearTimeout(timer.current);
    const tone = options.tone ?? "info";
    const duration = options.duration ?? (options.action ? 8000 : tone === "error" ? 6000 : 2900);
    seq.current += 1;
    setToast({ id: seq.current, message, ...options, tone });
    timer.current = setTimeout(() => setToast(null), duration);
  }, []);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      show,
      dismiss,
      info: (m, o) => show(m, { ...o, tone: "info" }),
      success: (m, o) => show(m, { ...o, tone: "success" }),
      error: (e, o) => show(typeof e === "string" ? e : errorMessage(e), { ...o, tone: "error" }),
    }),
    [show, dismiss],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="gv-toast-region" data-modal-exempt="" aria-live={toast?.tone === "error" ? "assertive" : "polite"} role="status">
        {toast && (
          <div key={toast.id} className={cx("toast", "gv-toast", `tone-${toast.tone}`)}>
            <span>{toast.message}</span>
            {toast.action && (
              <button
                type="button"
                className="gv-toast-action"
                onClick={() => {
                  toast.action?.onClick();
                  dismiss();
                }}
              >
                {toast.action.label}
              </button>
            )}
          </div>
        )}
      </div>
    </ToastContext.Provider>
  );
}

const noop: ToastApi = { show: () => {}, info: () => {}, success: () => {}, error: () => {}, dismiss: () => {} };

export function useToast(): ToastApi {
  return useContext(ToastContext) ?? noop;
}
