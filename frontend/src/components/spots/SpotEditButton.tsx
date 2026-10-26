"use client";
/** Pencil «Предложить правку» (SPT-07): on the photo (`photo`) or as an action pill (`pill`). */
import { Button, Icon } from "@/components/ui";
import { useSpotViewer } from "./SpotViewer";

export function SpotEditButton({ variant = "pill" }: { variant?: "photo" | "pill" }) {
  const { spot, openEdit } = useSpotViewer();
  if (variant === "photo") {
    return (
      <button
        type="button"
        className="gv-spot-edit-trigger gv-spot-edit-static"
        onClick={openEdit}
        aria-label={`Предложить правку данных спота «${spot.name}»`}
        title="Предложить правку"
      >
        <Icon name="pencil" size={16} />
      </button>
    );
  }
  return (
    <Button variant="pill" icon="pencil" onClick={openEdit}>
      Предложить правку
    </Button>
  );
}
