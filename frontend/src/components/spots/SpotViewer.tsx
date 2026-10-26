"use client";
/**
 * Per-viewer part of the spot page. The SSR card is public (no cookies), so `my_review` and
 * `my_pending_proposals` are fetched again in the browser for signed-in users and shared via context.
 * The context also owns the single «Предложить правку» dialog (pencil on the photo, action buttons, `?edit=1`
 * deep link from catalogue cards); guests get the login prompt instead (SPT-07, table 16).
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useLoginPrompt } from "@/components/auth/LoginPrompt";
import { spotKeys, spotsApi, type PendingProposalShort, type SpotDetail, type SpotDictionaries } from "@/lib/api/spots";
import type { OwnReview } from "@/lib/api/publicReviews";
import { useMe } from "@/lib/auth/hooks";
import { SpotProposalDialog } from "./SpotProposalDialog";

interface SpotViewerState {
  spot: SpotDetail;
  /** undefined while loading for a signed-in user; null = no review */
  myReview: OwnReview | null | undefined;
  pendingProposals: PendingProposalShort[];
  isOwnDataLoading: boolean;
  openEdit: () => void;
  refresh: () => void;
}

const Ctx = createContext<SpotViewerState | null>(null);

const EDIT_REASON = "Чтобы предложить правку спота, войдите в аккаунт — так модератор сможет уточнить детали.";

export function SpotViewerProvider({
  spot,
  dictionaries,
  children,
}: {
  spot: SpotDetail;
  dictionaries: SpotDictionaries | null;
  children: ReactNode;
}) {
  const { me, isLoading } = useMe();
  const { prompt } = useLoginPrompt();
  const [editOpen, setEditOpen] = useState(false);
  const query = useQuery({
    queryKey: spotKeys.detail(spot.slug),
    queryFn: () => spotsApi.detail(spot.slug),
    enabled: Boolean(me),
    staleTime: 30_000,
  });
  const fresh = query.data;
  const { refetch } = query;

  const openEdit = useCallback(() => {
    if (me) setEditOpen(true);
    else if (!isLoading) prompt(EDIT_REASON);
  }, [me, isLoading, prompt]);

  const value = useMemo<SpotViewerState>(
    () => ({
      spot,
      myReview: !me ? (isLoading ? undefined : null) : fresh ? fresh.my_review : query.isError ? null : undefined,
      pendingProposals: fresh?.my_pending_proposals ?? [],
      isOwnDataLoading: Boolean(me) && query.isPending,
      openEdit,
      refresh: () => void refetch(),
    }),
    [spot, me, isLoading, fresh, query.isError, query.isPending, openEdit, refetch],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      <SpotProposalDialog open={editOpen} onClose={() => setEditOpen(false)} spot={fresh ?? spot} dictionaries={dictionaries} />
    </Ctx.Provider>
  );
}

export function useSpotViewer(): SpotViewerState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSpotViewer must be used inside SpotViewerProvider");
  return ctx;
}

/** `?edit=1` (pencil on a catalogue card) opens the proposal form once auth is known. Wrap in <Suspense>. */
export function SpotEditFromUrl() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { openEdit } = useSpotViewer();
  const { isLoading } = useMe();
  const wanted = params.get("edit") === "1";
  useEffect(() => {
    if (!wanted || isLoading) return;
    openEdit();
    const next = new URLSearchParams(params.toString());
    next.delete("edit");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [wanted, isLoading, openEdit, params, pathname, router]);
  return null;
}
