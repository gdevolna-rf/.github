/**
 * Public reviews on spot / instructor / school pages (SPT-03/10, TRUST-01/02, BR-08).
 * Shapes: backend/apps/trust/serializers.py (PublicReviewSerializer, MyReviewSerializer) and
 * backend/apps/spots/serializers.py (MyReviewShortSerializer — `my_review` of the spot detail).
 */
import { api } from "./client";
import type { IsoDateTime, Media, Paginated, PublicAccount, UUID } from "./types";

export type ReviewTargetType = "spot" | "instructor" | "organization";

export interface PublicReview {
  id: UUID;
  target_type: ReviewTargetType;
  rating: number;
  text: string;
  author: PublicAccount;
  context_label: string;
  photos: Media[];
  published_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

/** The viewer's own review (spot detail `my_review` or an item of GET /me/reviews). */
export interface OwnReview {
  id: UUID;
  rating: number;
  text: string;
  status: string | { code: string; label?: string };
  has_pending_revision: boolean;
  pending_rating: number | null;
  pending_text: string;
  moderation_note: string;
  published_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  target?: { type: ReviewTargetType; id: UUID; name: string; link: string };
}

export interface ReviewSubmitInput {
  target_type: ReviewTargetType;
  target_id: UUID;
  rating: number;
  text: string;
  photo_ids?: UUID[] | null;
}

export const reviewsApi = {
  list: (targetType: ReviewTargetType, targetId: string, page = 1, pageSize = 10) =>
    api.get<Paginated<PublicReview>>("reviews", {
      query: { target_type: targetType, target_id: targetId, page, page_size: pageSize },
    }),
  /** Create or replace my review → 201 (new) / 200 (revision). Always goes through moderation. */
  submit: (body: ReviewSubmitInput) => api.post<OwnReview>("reviews", body),
  mine: () => api.get<Paginated<OwnReview>>("me/reviews", { query: { page_size: 100 } }),
};

export const reviewKeys = {
  list: (targetType: ReviewTargetType, targetId: string) => ["reviews", targetType, targetId] as const,
  mine: ["reviews", "mine"] as const,
};
