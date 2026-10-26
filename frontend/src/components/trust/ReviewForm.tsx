"use client";
/**
 * «Мой отзыв» block (SPT-10, TRUST-01/02, BR-05/08): create or update the viewer's review; every version goes
 * through moderation (status «На модерации»). Guests get the login prompt. Server refusals are shown as is:
 * unverified email (with «Отправить письмо ещё раз»), review of yourself / own organisation, «только после
 * завершённого занятия» for instructors and schools.
 *
 *   <ReviewForm targetType="spot" targetId={spot.id} targetName={spot.name} initialReview={spot.my_review} />
 *
 * Without `initialReview` (instructor/school pages) the component looks the review up in GET /me/reviews.
 */
import { useEffect, useId, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLoginPrompt } from "@/components/auth/LoginPrompt";
import { Button, Icon, RatingInput, StatusBadge, Textarea, useToast } from "@/components/ui";
import { authApi } from "@/lib/api/auth";
import { isApiError } from "@/lib/api/errors";
import { reviewKeys, reviewsApi, type OwnReview, type ReviewTargetType } from "@/lib/api/publicReviews";
import { useMe } from "@/lib/auth/hooks";
import { choiceCode } from "@/lib/labels";
import { apiFieldErrors, type FormErrors } from "@/lib/forms";
import { routes } from "@/lib/routes";
import "./trust.css";

export interface ReviewFormProps {
  targetType: ReviewTargetType;
  targetId: string;
  targetName: string;
  /** `my_review` from the detail response; `undefined` → look it up in /me/reviews; `null` → no review. */
  initialReview?: OwnReview | null;
  /** Shown before the first review, e.g. «Отзыв можно оставить после завершённого занятия». */
  eligibilityNote?: string;
  /** Hide the whole block for the owner of the object (no reviews about yourself). */
  hidden?: boolean;
}

type Field = "rating" | "text";

export function ReviewForm({ targetType, targetId, targetName, initialReview, eligibilityNote, hidden }: ReviewFormProps) {
  const { me, isLoading } = useMe();
  const { prompt } = useLoginPrompt();
  const lookup = initialReview === undefined && Boolean(me);
  const mine = useQuery({
    queryKey: reviewKeys.mine,
    queryFn: reviewsApi.mine,
    enabled: lookup,
    staleTime: 60_000,
  });
  const found =
    initialReview !== undefined
      ? initialReview
      : (mine.data?.results.find((r) => r.target?.type === targetType && String(r.target?.id) === String(targetId)) ?? null);

  const [saved, setSaved] = useState<OwnReview | null | undefined>(undefined);
  const review = saved !== undefined ? saved : found;
  const [editing, setEditing] = useState(false);
  // The hydration render must match the guest SSR markup (`/me` may already be cached when a streamed boundary hydrates).
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);

  if (hidden) return null;

  if (!me || !hydrated) {
    return (
      <div className="gv-review-cta">
        <p>{eligibilityNote ?? `Были на месте? Расскажите, как вам ${targetName}.`}</p>
        <Button
          variant="primary"
          icon="star"
          onClick={() => !isLoading && prompt("Чтобы оставить отзыв, войдите в аккаунт.")}
        >
          Оставить отзыв
        </Button>
      </div>
    );
  }

  if (editing) {
    return (
      <ReviewEditor
        targetType={targetType}
        targetId={targetId}
        targetName={targetName}
        review={review ?? null}
        onCancel={() => setEditing(false)}
        onSaved={(r) => {
          setSaved(r);
          setEditing(false);
        }}
      />
    );
  }

  if (review) {
    const status = choiceCode(review.status);
    return (
      <div className="gv-review-mine" aria-live="polite">
        <div className="gv-review-mine-head">
          <b>Ваш отзыв</b>
          <StatusBadge domain="review" status={status} />
          {review.has_pending_revision && <StatusBadge domain="review" status="pending" className="gv-review-revision" />}
        </div>
        {review.has_pending_revision ? (
          <p className="gv-review-mine-note">
            Изменённая версия на модерации; пока показывается опубликованная.
          </p>
        ) : status === "pending" ? (
          <p className="gv-review-mine-note">Отзыв появится на странице после проверки модератором.</p>
        ) : null}
        {review.moderation_note && (status === "rejected" || status === "hidden") && (
          <p className="gv-review-mine-note">Комментарий модератора: {review.moderation_note}</p>
        )}
        <p className="gv-review-mine-text">
          {"★".repeat(review.has_pending_revision && review.pending_rating ? review.pending_rating : review.rating)}{" "}
          {review.has_pending_revision && review.pending_text ? review.pending_text : review.text}
        </p>
        <Button variant="pill" icon="pencil" onClick={() => setEditing(true)}>
          Изменить отзыв
        </Button>
      </div>
    );
  }

  return (
    <div className="gv-review-cta">
      <p>{eligibilityNote ?? `Были на месте? Расскажите, как вам ${targetName}.`}</p>
      <Button variant="primary" icon="star" onClick={() => setEditing(true)} loading={lookup && mine.isPending}>
        Оставить отзыв
      </Button>
    </div>
  );
}

function ReviewEditor({
  targetType,
  targetId,
  targetName,
  review,
  onCancel,
  onSaved,
}: {
  targetType: ReviewTargetType;
  targetId: string;
  targetName: string;
  review: OwnReview | null;
  onCancel: () => void;
  onSaved: (review: OwnReview) => void;
}) {
  const formId = useId().replace(/:/g, "");
  const toast = useToast();
  const queryClient = useQueryClient();
  const [rating, setRating] = useState<number | null>(review ? (review.pending_rating ?? review.rating) : null);
  const [text, setText] = useState(review ? (review.has_pending_revision && review.pending_text ? review.pending_text : review.text) : "");
  const [errors, setErrors] = useState<FormErrors<Field>>({});
  const [notVerified, setNotVerified] = useState<string | null>(null);

  const resend = useMutation({
    mutationFn: authApi.resendVerification,
    onSuccess: () => toast.success("Письмо со ссылкой отправлено"),
    onError: (err) => toast.error(err),
  });

  const mutation = useMutation({
    mutationFn: () => reviewsApi.submit({ target_type: targetType, target_id: targetId, rating: rating ?? 0, text: text.trim() }),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
      toast.success("Спасибо! Отзыв отправлен на модерацию");
      onSaved(saved);
    },
    onError: (err) => {
      if (isApiError(err) && err.code === "email_not_verified") {
        setNotVerified(err.message);
        return;
      }
      if (isApiError(err) && (err.isForbidden || err.isNotFound)) {
        setErrors({ _form: err.message });
        return;
      }
      setErrors(apiFieldErrors(err));
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next: FormErrors<Field> = {};
    if (!rating) next.rating = "Поставьте оценку от 1 до 5.";
    if (!text.trim()) next.text = "Напишите пару слов о своём опыте.";
    setErrors(next);
    setNotVerified(null);
    if (Object.keys(next).length) return;
    mutation.mutate();
  };

  return (
    <form id={formId} className="gv-review-editor" onSubmit={submit} noValidate aria-label={`Отзыв: ${targetName}`}>
      <h3>{review ? "Изменить отзыв" : "Оставить отзыв"}</h3>
      {notVerified && (
        <div className="gv-form-error" role="alert">
          <Icon name="mail" size={18} />
          <span>
            {notVerified}{" "}
            <button type="button" className="gv-inline-link" onClick={() => resend.mutate()} disabled={resend.isPending}>
              Отправить письмо ещё раз
            </button>{" "}
            · <a href={routes.account.settings}>Настройки</a>
          </span>
        </div>
      )}
      {errors._form && (
        <div className="gv-form-error" role="alert">
          <Icon name="alert" size={18} />
          <span>{errors._form}</span>
        </div>
      )}
      <RatingInput value={rating} onChange={setRating} required error={errors.rating} />
      <Textarea
        label="Комментарий"
        required
        rows={4}
        maxLength={3000}
        placeholder="Расскажите о своём опыте: волна, вход в воду, люди, что взять с собой…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        error={errors.text}
        hint="Отзыв публикуется после проверки модератором."
      />
      <div className="gv-review-editor-actions">
        <Button variant="pill" onClick={onCancel}>
          Отмена
        </Button>
        <Button variant="primary" type="submit" loading={mutation.isPending} iconRight="send">
          Отправить на модерацию
        </Button>
      </div>
    </form>
  );
}
