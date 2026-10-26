"use client";
/**
 * Favourite toggle (MSG-11, UX-04 standard heart): one SVG heart everywhere, pink active state
 * (#ec789c on #fff0f5), aria-pressed. Optimistic POST/DELETE /favorites with rollback + toast on error.
 * Guests get the login prompt.
 *
 *   <HeartButton type="spot" id={spot.id} name={spot.name} />                  // round button on a photo
 *   <HeartButton type="instructor" id={p.id} name={p.name} variant="pill" />   // «В избранное» pill
 */
import { useLoginPrompt } from "@/components/auth/LoginPrompt";
import { useMe } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { useIsFavorite, useToggleFavorite } from "@/lib/favorites/hooks";
import type { FavoriteTargetType } from "@/lib/api/types";
import { Icon } from "./Icon";
import { useToast } from "./Toast";

export interface HeartButtonProps {
  type: FavoriteTargetType;
  id: string | number;
  /** Object name for the accessible label: «Добавить в избранное: Халактырский пляж». */
  name?: string;
  /** photo = 35px circle over a photo (`.like-btn`); light = small light circle; pill = «♡ В избранное». */
  variant?: "photo" | "light" | "pill";
  className?: string;
}

export function HeartButton({ type, id, name, variant = "photo", className }: HeartButtonProps) {
  const { me, isLoading } = useMe();
  const active = useIsFavorite(type, id);
  const toggle = useToggleFavorite();
  const toast = useToast();
  const { prompt } = useLoginPrompt();

  const onClick = () => {
    if (!me) {
      if (!isLoading) prompt("Войдите, чтобы сохранять споты, инструкторов, доски и снаряжение в избранное.");
      return;
    }
    const on = !active;
    toggle.mutate(
      { type, id, on },
      {
        onSuccess: () => toast.success(on ? "Добавлено в избранное ♡" : "Убрано из избранного"),
        onError: (err) =>
          toast.error(err, {
            action: { label: "Повторить", onClick: () => toggle.mutate({ type, id, on }) },
          }),
      },
    );
  };

  // Stable accessible name + aria-pressed (WAI-ARIA toggle button); the tooltip tells what a click will do.
  const label = `В избранное${name ? `: ${name}` : ""}`;
  const hint = active ? "Убрать из избранного" : "Добавить в избранное";

  if (variant === "pill") {
    return (
      <button
        type="button"
        className={cx("pill-btn gv-heart-pill", active && "pink-heart", className)}
        aria-pressed={active}
        aria-label={label}
        title={hint}
        onClick={onClick}
      >
        <Icon name="heart" size={16} filled={active} />
        <span>{active ? "В избранном" : "В избранное"}</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      className={cx("like-btn gv-heart", variant === "light" && "is-light", active && "active", className)}
      aria-pressed={active}
      aria-label={label}
      title={hint}
      onClick={onClick}
    >
      <Icon name="heart" size={18} filled={active} />
    </button>
  );
}
