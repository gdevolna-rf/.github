"use client";
/** Spot reviews at the bottom of the page (SPT-03/10): published list + the viewer's own review / form. */
import { ReviewForm } from "@/components/trust/ReviewForm";
import { ReviewsSection } from "@/components/trust/ReviewsSection";
import type { Paginated } from "@/lib/api/types";
import type { PublicReview } from "@/lib/api/publicReviews";
import { useSpotViewer } from "./SpotViewer";

export function SpotReviews({ initial }: { initial: Paginated<PublicReview> | null }) {
  const { spot, myReview } = useSpotViewer();
  return (
    <ReviewsSection
      targetType="spot"
      targetId={spot.id}
      initial={initial}
      ratingAvg={spot.rating_avg}
      ratingCount={spot.rating_count}
      title="Отзывы о споте"
      emptyText="Будьте первым — расскажите, какая здесь волна и как зайти в воду."
      form={<ReviewForm key={myReview === undefined ? "loading" : "ready"} targetType="spot" targetId={spot.id} targetName={spot.name} initialReview={myReview} />}
    />
  );
}
