"""Отзывы со стороны автора (7.5, раздел 14, TRUST-01/02/08, BR-05, ATX-12/26).

Один текущий отзыв на автора и цель; новый отзыв — pending + кейс модерации; правка опубликованного
хранится как pending-ревизия, а публичная версия остаётся видимой до решения модератора.
"""
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.services.verification import require_verified_email
from apps.commerce.models import Booking, Inquiry
from apps.common.exceptions import DomainError, Forbidden, NotFound
from apps.learning.models import InstructorProfile
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services import claim_many
from apps.organizations.models import Organization
from apps.organizations.services.access import is_member
from apps.spots.services.catalog import public_spots
from apps.trust.models import Review
from apps.trust.services.audit import record
from apps.trust.services.moderation_queue import close_cases, open_case
from apps.trust.services.ratings import recalculate_for_review
from apps.trust.services.restrictions import require_can_publish

MAX_PHOTOS = 6
TARGET_FK = {
    Review.Target.SPOT: "spot",
    Review.Target.INSTRUCTOR: "instructor",
    Review.Target.ORGANIZATION: "organization",
}


def resolve_target(target_type, target_id):
    """Публичная цель отзыва или NotFound."""
    if target_type == Review.Target.SPOT:
        target = public_spots().filter(pk=target_id).first()
    elif target_type == Review.Target.INSTRUCTOR:
        target = InstructorProfile.objects.select_related("account").filter(
            pk=target_id, status=InstructorProfile.Status.PUBLISHED).first()
    elif target_type == Review.Target.ORGANIZATION:
        target = Organization.objects.filter(pk=target_id, status=Organization.Status.PUBLISHED).first()
    else:
        raise DomainError("validation_error", "Неизвестный тип объекта отзыва.", fields={"target_type": ["Неверное значение."]})
    if target is None:
        raise NotFound("Объект отзыва не найден.", code="target_not_found")
    return target


def target_name(review_or_target, target_type=None):
    target = review_or_target
    if isinstance(review_or_target, Review):
        target_type = review_or_target.target_type
        target = getattr(review_or_target, TARGET_FK[target_type])
    if target_type == Review.Target.INSTRUCTOR:
        profile = getattr(target.account, "profile", None)
        return profile.display_name if profile else "Инструктор"
    return target.name


def target_public_link(review):
    """Маршрут фронтенда публичной карточки цели (ARCHITECTURE §9)."""
    if review.target_type == Review.Target.SPOT:
        return f"/spots/{review.spot.slug}"
    if review.target_type == Review.Target.INSTRUCTOR:
        profile = getattr(review.instructor.account, "profile", None)
        return f"/instructors/{profile.handle}" if profile else "/instructors"
    org = review.organization
    if org.kind == Organization.Kind.SCHOOL:
        return f"/schools/{org.slug}"
    if org.kind == Organization.Kind.WORKSHOP:
        return f"/shapers/{org.slug}"
    return "/rentals"


def _context_label(booking, inquiry):
    if booking is not None:
        date = timezone.localtime(booking.starts_at).strftime("%d.%m.%Y")
        if booking.lesson_session_id:
            return f"Занятие «{booking.lesson_session.title}», {date}"[:200]
        return f"Аренда «{booking.inventory_item.title}», {date}"[:200]
    if inquiry is not None:
        return f"{inquiry.get_kind_display()}: {inquiry.subject}"[:200]
    return ""


def check_eligibility(author, target_type, target):
    """Кто вправе оценить (TRUST-02, DEC-04 по умолчанию): спот — любой; инструктор/организация — только
    после завершённой брони или обращения с этим исполнителем; никогда — о себе и своей организации (BR-05)."""
    if target_type == Review.Target.SPOT:
        return None, None, ""
    done = Booking.objects.filter(customer=author, status=Booking.Status.COMPLETED).select_related(
        "lesson_session", "inventory_item").order_by("-ends_at")
    closed = Inquiry.objects.filter(customer=author, status=Inquiry.Status.COMPLETED).order_by("-closed_at", "-created_at")
    if target_type == Review.Target.INSTRUCTOR:
        if target.account_id == author.pk:
            raise Forbidden("Нельзя оставить отзыв о себе.", code="self_review")
        booking = done.filter(Q(provider_account_id=target.account_id) | Q(lesson_session__instructor_id=target.account_id)).first()
        inquiry = None if booking else closed.filter(provider_account_id=target.account_id).first()
    else:
        if target.owner_id == author.pk or is_member(author, target):
            raise Forbidden("Нельзя оценивать собственную организацию.", code="self_review")
        booking = done.filter(provider_organization=target).first()
        inquiry = None if booking else closed.filter(provider_organization=target).first()
    if booking is None and inquiry is None:
        raise Forbidden("Оставить отзыв можно после завершённого занятия, аренды или заказа у этого исполнителя.",
                        code="review_not_allowed")
    return booking, inquiry, _context_label(booking, inquiry)


def _claim_photos(photo_ids, author):
    ids = list(dict.fromkeys(str(i) for i in photo_ids))
    if len(ids) > MAX_PHOTOS:
        raise DomainError("too_many_files", f"Не больше {MAX_PHOTOS} фото к отзыву.",
                          fields={"photo_ids": [f"Не больше {MAX_PHOTOS} файлов."]})
    return claim_many(ids, author, purposes=[MediaAsset.Purpose.REVIEW_PHOTO], kinds=[MediaAsset.Kind.IMAGE])


def _summary(review, revision=False):
    prefix = "Правка отзыва" if revision else "Отзыв"
    return f"{prefix} {review.rating}★ — {target_name(review)}"[:300]


def submit_review(author, *, target_type, target_id, rating, text, photo_ids=None, request=None):
    """Создать или заменить свой отзыв. Возвращает (review, created)."""
    require_verified_email(author, "публикации отзыва")
    require_can_publish(author)
    target = resolve_target(target_type, target_id)
    booking, inquiry, label = check_eligibility(author, target_type, target)
    fk = {TARGET_FK[target_type]: target}
    text = (text or "").strip()
    with transaction.atomic():
        photos = _claim_photos(photo_ids, author) if photo_ids is not None else None
        review = Review.objects.select_for_update().filter(author=author, **fk).first()
        created = False
        if review is None:
            try:
                with transaction.atomic():
                    review = Review.objects.create(
                        author=author, target_type=target_type, rating=rating, text=text, booking=booking,
                        inquiry=inquiry, context_label=label, status=Review.Status.PENDING, **fk,
                    )
                created = True
            except IntegrityError:  # параллельный первый отзыв того же автора — продолжаем как правку
                review = Review.objects.select_for_update().get(author=author, **fk)
        if created:
            if photos:
                review.photos.set(photos)
            open_case("review", _summary(review), review=review)
            record(author, "review.submitted", review, after={"rating": rating, "text": text}, request=request)
            return review, True

        if review.status == Review.Status.PUBLISHED:
            current_photos = {p.pk for p in review.photos.all()}
            same = (rating == review.rating and text == review.text
                    and (photos is None or {p.pk for p in photos} == current_photos))
            if same:
                # Возврат к опубликованной версии — отменяет ожидающую ревизию.
                if review.has_pending_revision:
                    review.has_pending_revision, review.pending_rating, review.pending_text = False, None, ""
                    review.save(update_fields=["has_pending_revision", "pending_rating", "pending_text", "updated_at"])
                    review.pending_photos.clear()
                    close_cases("withdrawn", None, "Автор вернул опубликованную версию", review=review)
                return review, False
            review.pending_rating, review.pending_text, review.has_pending_revision = rating, text, True
            review.save(update_fields=["pending_rating", "pending_text", "has_pending_revision", "updated_at"])
            review.pending_photos.set(photos if photos is not None else review.photos.all())
            open_case("review", _summary(review, revision=True), review=review)
            record(author, "review.revision_submitted", review,
                   before={"rating": review.rating, "text": review.text}, after={"rating": rating, "text": text},
                   request=request)
            return review, False

        # pending / rejected / hidden → новая версия снова уходит на модерацию
        before = {"rating": review.rating, "text": review.text, "status": review.status}
        review.rating, review.text, review.status = rating, text, Review.Status.PENDING
        review.has_pending_revision, review.pending_rating, review.pending_text = False, None, ""
        review.moderator, review.moderated_at, review.moderation_note = None, None, ""
        review.booking, review.inquiry, review.context_label = booking, inquiry, label
        review.save()
        review.pending_photos.clear()
        if photos is not None:
            review.photos.set(photos)
        open_case("review", _summary(review), review=review)
        record(author, "review.resubmitted", review, before=before, after={"rating": rating, "text": text},
               request=request)
        return review, False


def delete_own_review(review_id, author, request=None):
    """Автор убирает свой отзыв: статус hidden, рейтинг цели пересчитывается (если был опубликован)."""
    with transaction.atomic():
        review = Review.objects.select_for_update().filter(pk=review_id, author=author).first()
        if review is None:
            raise NotFound("Отзыв не найден.")
        if review.status == Review.Status.HIDDEN:
            return review
        was_published = review.status == Review.Status.PUBLISHED
        before = {"status": review.status, "rating": review.rating}
        review.status = Review.Status.HIDDEN
        review.has_pending_revision, review.pending_rating, review.pending_text = False, None, ""
        review.moderation_note = "Удалён автором"
        review.save()
        review.pending_photos.clear()
        close_cases("withdrawn", None, "Отзыв удалён автором", review=review)
        if was_published:
            recalculate_for_review(review)
        record(author, "review.deleted_by_author", review, before=before, after={"status": review.status},
               request=request)
    return review
