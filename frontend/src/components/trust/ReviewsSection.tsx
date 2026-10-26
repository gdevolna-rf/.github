"use client";
/**
 * Published reviews of a spot / instructor / school (SPT-03, SPT-10, TRUST-01/02): author avatar and name, date,
 * stars, service context, text, photos; «Показать ещё» pages through GET /reviews. Only server data — the average
 * comes from the API (published reviews only), never computed here.
 *
 *   <ReviewsSection targetType="spot" targetId={spot.id} initial={firstPage} ratingAvg={spot.rating_avg}
 *     ratingCount={spot.rating_count} form={<ReviewForm … />} />
 */
import type { ReactNode } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Avatar, Button, ClampText, EmptyState, ErrorState, LoadingState, Stars } from "@/components/ui";
import { pageFromUrl } from "@/lib/api/client";
import { mediaSrc } from "@/lib/api/media";
import { reviewKeys, reviewsApi, type PublicReview, type ReviewTargetType } from "@/lib/api/publicReviews";
import type { Paginated } from "@/lib/api/types";
import { formatDate, formatRating, plural, WORDS } from "@/lib/format";
import { ReportButton } from "./ReportButton";
import "./trust.css";

const PAGE_SIZE = 10;

export interface ReviewsSectionProps {
  targetType: ReviewTargetType;
  targetId: string;
  /** First page fetched on the server (SSR, SEO). */
  initial?: Paginated<PublicReview> | null;
  ratingAvg?: string | number | null;
  ratingCount?: number | null;
  title?: string;
  /** Text under the empty state. */
  emptyText?: string;
  /** Review form / «мой отзыв» block. */
  form?: ReactNode;
  id?: string;
}

export function ReviewsSection({
  targetType,
  targetId,
  initial,
  ratingAvg,
  ratingCount,
  title = "Отзывы",
  emptyText = "Отзывы появятся после проверки модератором.",
  form,
  id = "reviews",
}: ReviewsSectionProps) {
  const query = useInfiniteQuery({
    queryKey: reviewKeys.list(targetType, targetId),
    queryFn: ({ pageParam }) => reviewsApi.list(targetType, targetId, pageParam, PAGE_SIZE),
    initialPageParam: 1,
    getNextPageParam: (last) => pageFromUrl(last.next),
    initialData: initial ? { pages: [initial], pageParams: [1] } : undefined,
    staleTime: 60_000,
  });
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  const total = query.data?.pages[0]?.count ?? ratingCount ?? 0;
  const count = ratingCount ?? total;
  const avg = Number(ratingAvg ?? 0);

  return (
    <section className="gv-reviews" id={id} aria-labelledby={`${id}-title`}>
      <div className="gv-reviews-head">
        <h2 id={`${id}-title`} className="gv-reviews-title">
          {title}
        </h2>
        {count > 0 ? (
          <div className="gv-reviews-score" aria-label={`Средняя оценка ${formatRating(avg)} из 5, ${count} ${plural(count, WORDS.review)}`}>
            <b>{formatRating(avg)}</b>
            <Stars value={avg} size={16} />
            <span>
              {count} {plural(count, WORDS.review)}
            </span>
          </div>
        ) : (
          <span className="gv-reviews-score is-empty">Пока без отзывов</span>
        )}
      </div>
      <p className="gv-reviews-policy">
        Показываем только отзывы, прошедшие модерацию. Средняя оценка считается по опубликованным отзывам.
      </p>

      {form}

      {query.isPending ? (
        <LoadingState variant="skeleton" lines={3} />
      ) : query.isError && !items.length ? (
        <ErrorState compact error={query.error} onRetry={() => void query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState compact title="Отзывов пока нет" text={emptyText} />
      ) : (
        <>
          <ul className="gv-review-list">
            {items.map((r) => (
              <ReviewItem key={r.id} review={r} />
            ))}
          </ul>
          {query.hasNextPage && (
            <div className="gv-reviews-more">
              <Button variant="pill" loading={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
                Показать ещё
              </Button>
            </div>
          )}
          {query.isFetchNextPageError && (
            <ErrorState compact error={query.error} onRetry={() => void query.fetchNextPage()} />
          )}
        </>
      )}
    </section>
  );
}

export function ReviewItem({ review }: { review: PublicReview }) {
  const author = review.author;
  const name = author?.is_deleted ? "Удалённый пользователь" : (author?.display_name ?? "Пользователь");
  const when = review.published_at ?? review.created_at;
  return (
    <li className="gv-review">
      <div className="gv-review-head">
        <Avatar media={author?.avatar} name={name} size={42} />
        <div className="gv-review-who">
          <span className="gv-review-name">{name}</span>
          <span className="gv-review-meta">
            <time dateTime={when}>{formatDate(when, { style: "long" })}</time>
            {review.context_label ? ` · ${review.context_label}` : ""}
          </span>
        </div>
        <span className="gv-review-stars" aria-label={`Оценка ${review.rating} из 5`}>
          <Stars value={review.rating} size={14} />
        </span>
      </div>
      {review.text && (
        <ClampText lines={5} className="gv-review-text">
          {review.text}
        </ClampText>
      )}
      {review.photos?.length > 0 && (
        <ul className="gv-review-photos" aria-label="Фото к отзыву">
          {review.photos.slice(0, 6).map((p) => (
            <li key={p.id}>
              <a href={p.url ?? "#"} target="_blank" rel="noopener noreferrer">
                <img src={mediaSrc(p, "thumb") ?? ""} alt={p.alt_text || `Фото к отзыву ${name}`} loading="lazy" />
              </a>
            </li>
          ))}
        </ul>
      )}
      <div className="gv-review-foot">
        <ReportButton targetType="review" targetId={review.id} label="Пожаловаться на отзыв" />
      </div>
    </li>
  );
}
