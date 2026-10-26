"""Отзывы (7.5, 14, BR-05/08, TRUST-01/02/08, AT-08, F09, ATX-12, ATX-26)."""
from decimal import Decimal

import pytest

from apps.analytics.models import AnalyticsEvent
from apps.commerce.models import Inquiry
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import Notification
from apps.organizations.models import Membership
from apps.spots.models import Spot
from apps.trust.models import AccountRestriction, AuditEvent, ModerationCase, Review
from apps.trust.services.ratings import recalculate_all
from apps.trust.tasks import recalculate_ratings
from apps.trust.tests.helpers import completed_lesson_booking, completed_rental_booking, inquiry
from tests.factories import (
    AccountFactory,
    InstructorProfileFactory,
    InventoryItemFactory,
    MediaAssetFactory,
    OrganizationFactory,
    SpotFactory,
    WorkshopFactory,
    add_member,
)

pytestmark = pytest.mark.django_db


def _post(client, target_type, target_id, rating=4, text="Отличный спот", **extra):
    return client.post("/api/v1/reviews", {"target_type": target_type, "target_id": str(target_id), "rating": rating,
                                           "text": text, **extra}, format="json")


def _approve(mod_client, review_id, **body):
    response = mod_client.post(f"/api/v1/moderation/reviews/{review_id}/approve", body, format="json")
    assert response.status_code == 200, response.json()
    return response.json()


def _public(api_client, target_type, target_id):
    return api_client.get(f"/api/v1/reviews?target_type={target_type}&target_id={target_id}").json()


def test_guest_cannot_post_review(api_client):
    spot = SpotFactory()
    assert _post(api_client, "spot", spot.id).status_code == 401


def test_unverified_email_cannot_review(make_client):
    client = make_client(AccountFactory(email_verified_at=None))
    response = _post(client, "spot", SpotFactory().id)
    assert response.status_code == 403 and response.json()["error"]["code"] == "email_not_verified"


def test_restricted_account_cannot_review(make_client):
    client = make_client()
    AccountRestriction.objects.create(account=client.account, kind="suspended", reason="Спам")
    response = _post(client, "spot", SpotFactory().id)
    assert response.status_code == 403 and response.json()["error"]["code"] == "account_restricted"


def test_expired_or_lifted_restriction_does_not_block(make_client):
    from django.utils import timezone
    import datetime as dt

    client = make_client()
    AccountRestriction.objects.create(account=client.account, kind="publishing", reason="x",
                                      expires_at=timezone.now() - dt.timedelta(hours=1))
    AccountRestriction.objects.create(account=client.account, kind="suspended", reason="y", lifted_at=timezone.now())
    assert _post(client, "spot", SpotFactory().id).status_code == 201


def test_spot_review_is_pending_until_moderation_then_published_and_counted(make_client, api_client, mod_client):
    """AT-08 / F09 / ATX-12: 4★ виден после модерации; рейтинг только нужного спота."""
    spot, neighbour = SpotFactory(), SpotFactory(rating_avg=Decimal("0"), rating_count=0)
    author = make_client()
    response = _post(author, "spot", spot.id, rating=4)
    assert response.status_code == 201
    review_id = response.json()["id"]
    assert response.json()["status"]["code"] == "pending"
    case = ModerationCase.objects.get(review_id=review_id)
    assert case.kind == "review" and case.status == "open"
    assert _public(api_client, "spot", spot.id)["count"] == 0
    spot.refresh_from_db()
    assert spot.rating_count == 0

    data = _approve(mod_client, review_id)
    assert data["status"]["code"] == "published"
    spot.refresh_from_db()
    neighbour.refresh_from_db()
    assert (spot.rating_avg, spot.rating_count) == (Decimal("4.00"), 1)
    assert (neighbour.rating_avg, neighbour.rating_count) == (Decimal("0.00"), 0)
    listing = _public(api_client, "spot", spot.id)
    assert listing["count"] == 1
    item = listing["results"][0]
    assert item["rating"] == 4 and item["author"]["display_name"] and "email" not in item["author"]
    assert item["published_at"]
    case.refresh_from_db()
    assert case.status == "resolved" and case.resolution == "approved"
    assert AuditEvent.objects.filter(action="review.published", object_id=review_id).exists()
    assert Notification.objects.filter(recipient=author.account, kind="review_published").exists()
    event = AnalyticsEvent.objects.get(name="review_published")
    assert event.subject_type == "spot" and event.subject_id == str(spot.id)
    assert api_client.get(f"/api/v1/spots/{spot.slug}").json()["rating_count"] == 1


def test_average_is_arithmetic_mean_of_published_only(make_client, mod_client):
    spot = SpotFactory()
    ids = [_post(make_client(), "spot", spot.id, rating=r).json()["id"] for r in (5, 4, 2)]
    _approve(mod_client, ids[0])
    _approve(mod_client, ids[1])  # третий остаётся pending
    spot.refresh_from_db()
    assert (spot.rating_avg, spot.rating_count) == (Decimal("4.50"), 2)


def test_repeat_submit_replaces_pending_review_without_new_vote(make_client, mod_client):
    spot = SpotFactory()
    client = make_client()
    first = _post(client, "spot", spot.id, rating=3)
    second = _post(client, "spot", spot.id, rating=5, text="Передумал")
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert Review.objects.filter(author=client.account).count() == 1
    assert ModerationCase.objects.filter(review_id=first.json()["id"], status="open").count() == 1
    _approve(mod_client, first.json()["id"])
    spot.refresh_from_db()
    assert (spot.rating_avg, spot.rating_count) == (Decimal("5.00"), 1)


def test_editing_published_review_keeps_public_version_until_revision_approved(make_client, api_client, mod_client):
    spot = SpotFactory()
    client = make_client()
    review_id = _post(client, "spot", spot.id, rating=4, text="Хорошо").json()["id"]
    _approve(mod_client, review_id)
    response = _post(client, "spot", spot.id, rating=2, text="Стало хуже")
    assert response.status_code == 200
    mine = response.json()
    assert mine["status"]["code"] == "published" and mine["has_pending_revision"] is True
    assert mine["pending_rating"] == 2 and mine["rating"] == 4
    public = _public(api_client, "spot", spot.id)["results"][0]
    assert (public["rating"], public["text"]) == (4, "Хорошо")
    spot.refresh_from_db()
    assert (spot.rating_avg, spot.rating_count) == (Decimal("4.00"), 1)

    _approve(mod_client, review_id)
    public = _public(api_client, "spot", spot.id)["results"][0]
    assert (public["rating"], public["text"]) == (2, "Стало хуже")
    spot.refresh_from_db()
    assert (spot.rating_avg, spot.rating_count) == (Decimal("2.00"), 1)
    assert AnalyticsEvent.objects.filter(name="review_published").count() == 1


def test_rejecting_revision_keeps_published_version(make_client, mod_client):
    spot = SpotFactory()
    client = make_client()
    review_id = _post(client, "spot", spot.id, rating=5).json()["id"]
    _approve(mod_client, review_id)
    _post(client, "spot", spot.id, rating=1, text="Оскорбления")
    response = mod_client.post(f"/api/v1/moderation/reviews/{review_id}/reject", {"note": "Нарушение правил"}, format="json")
    assert response.status_code == 200
    review = Review.objects.get(pk=review_id)
    assert review.status == "published" and review.rating == 5 and not review.has_pending_revision


def test_resubmitting_identical_published_text_cancels_pending_revision(make_client, mod_client):
    spot = SpotFactory()
    client = make_client()
    review_id = _post(client, "spot", spot.id, rating=5, text="Супер").json()["id"]
    _approve(mod_client, review_id)
    _post(client, "spot", spot.id, rating=3, text="Так себе")
    data = _post(client, "spot", spot.id, rating=5, text="Супер").json()
    assert data["has_pending_revision"] is False
    assert not ModerationCase.objects.filter(review_id=review_id, status="open").exists()


def test_review_photos_must_be_own_review_photos(make_client, mod_client, api_client):
    client = make_client()
    spot = SpotFactory()
    photo = MediaAssetFactory(owner=client.account, purpose=MediaAsset.Purpose.REVIEW_PHOTO)
    foreign = MediaAssetFactory(purpose=MediaAsset.Purpose.REVIEW_PHOTO)
    assert _post(client, "spot", spot.id, photo_ids=[str(foreign.id)]).status_code == 400
    review_id = _post(client, "spot", spot.id, photo_ids=[str(photo.id)]).json()["id"]
    _approve(mod_client, review_id)
    assert _public(api_client, "spot", spot.id)["results"][0]["photos"][0]["id"] == str(photo.id)


def test_review_of_hidden_spot_is_404(make_client):
    spot = SpotFactory(status=Spot.Status.HIDDEN)
    assert _post(make_client(), "spot", spot.id).status_code == 404


def test_rating_out_of_range_is_400(make_client):
    spot = SpotFactory()
    assert _post(make_client(), "spot", spot.id, rating=6).status_code == 400
    assert _post(make_client(), "spot", spot.id, rating=0).status_code == 400
    assert _post(make_client(), "spot", spot.id, text="   ").status_code == 400


# --- кто вправе оценить (TRUST-02, BR-05, ATX-26) ---------------------------------------------------

def test_instructor_review_requires_completed_service(make_client):
    instructor = InstructorProfileFactory()
    client = make_client()
    response = _post(client, "instructor", instructor.id)
    assert response.status_code == 403 and response.json()["error"]["code"] == "review_not_allowed"
    inquiry(client.account, status=Inquiry.Status.IN_PROGRESS, provider_account=instructor.account)
    assert _post(client, "instructor", instructor.id).status_code == 403


def test_instructor_review_after_completed_private_lesson_has_context(make_client):
    instructor = InstructorProfileFactory()
    client = make_client()
    completed_lesson_booking(client.account, instructor_account=instructor.account)
    response = _post(client, "instructor", instructor.id, rating=5)
    assert response.status_code == 201, response.json()
    assert response.json()["context_label"].startswith("Занятие «")
    review = Review.objects.get(pk=response.json()["id"])
    assert review.booking is not None


def test_student_of_school_lesson_can_review_the_teaching_instructor(make_client):
    instructor = InstructorProfileFactory()
    school = OrganizationFactory()
    client = make_client()
    completed_lesson_booking(client.account, organization=school, instructor_account=instructor.account)
    assert _post(client, "instructor", instructor.id).status_code == 201
    assert _post(client, "organization", school.id).status_code == 201


def test_completed_inquiry_allows_organization_review(make_client):
    workshop = WorkshopFactory()
    client = make_client()
    inquiry(client.account, provider_organization=workshop)
    response = _post(client, "organization", workshop.id)
    assert response.status_code == 201
    assert "Ремонт доски" in response.json()["context_label"]


def test_completed_rental_allows_organization_review(make_client):
    rental = OrganizationFactory(kind="rental")
    client = make_client()
    completed_rental_booking(client.account, InventoryItemFactory(owner_account=None, owner_organization=rental))
    assert _post(client, "organization", rental.id).status_code == 201


def test_instructor_cannot_review_self(make_client):
    instructor = InstructorProfileFactory()
    response = _post(make_client(instructor.account), "instructor", instructor.id)
    assert response.status_code == 403 and response.json()["error"]["code"] == "self_review"


def test_owner_cannot_review_own_workshop_even_with_completed_order(make_client):
    """ATX-26."""
    workshop = WorkshopFactory()
    client = make_client(workshop.owner)
    completed_rental_booking(client.account, InventoryItemFactory(owner_account=None, owner_organization=workshop))
    response = _post(client, "organization", workshop.id)
    assert response.status_code == 403 and response.json()["error"]["code"] == "self_review"


def test_active_member_cannot_review_own_school_but_former_member_can(make_client):
    school = OrganizationFactory()
    member = AccountFactory()
    membership = add_member(school, member, role=Membership.Role.INSTRUCTOR)
    completed_lesson_booking(member, organization=school)
    client = make_client(member)
    assert _post(client, "organization", school.id).json()["error"]["code"] == "self_review"
    membership.status = Membership.Status.REVOKED
    membership.save()
    assert _post(client, "organization", school.id).status_code == 201


def test_unpublished_organization_cannot_be_reviewed(make_client):
    school = OrganizationFactory(status="draft")
    assert _post(make_client(), "organization", school.id).status_code == 404


# --- списки, удаление, пересчёт ----------------------------------------------------------------

def test_public_list_requires_target_and_shows_only_published(api_client, make_client):
    spot = SpotFactory()
    assert api_client.get("/api/v1/reviews").status_code == 400
    assert api_client.get(f"/api/v1/reviews?target_type=spot&target_id={SpotFactory(status='hidden').id}").status_code == 404
    author = AccountFactory()
    Review.objects.create(author=author, target_type="spot", spot=spot, rating=5, status="rejected")
    Review.objects.create(author=AccountFactory(), target_type="spot", spot=spot, rating=4, status="hidden")
    Review.objects.create(author=AccountFactory(), target_type="spot", spot=spot, rating=3, status="pending")
    assert _public(api_client, "spot", spot.id)["count"] == 0


def test_me_reviews_lists_all_own_reviews_with_target(make_client):
    client = make_client()
    spot = SpotFactory(name="Англичанка")
    Review.objects.create(author=client.account, target_type="spot", spot=spot, rating=5, status="rejected",
                          moderation_note="Реклама")
    Review.objects.create(author=AccountFactory(), target_type="spot", spot=spot, rating=4)
    data = client.get("/api/v1/me/reviews").json()
    assert data["count"] == 1
    item = data["results"][0]
    assert item["target"]["name"] == "Англичанка" and item["target"]["link"] == f"/spots/{spot.slug}"
    assert item["moderation_note"] == "Реклама"
    assert client.get("/api/v1/me/reviews?status=published").json()["count"] == 0


def test_author_deletes_review_and_rating_is_recalculated(make_client, mod_client):
    spot = SpotFactory()
    client = make_client()
    review_id = _post(client, "spot", spot.id, rating=5).json()["id"]
    _approve(mod_client, review_id)
    assert make_client().delete(f"/api/v1/reviews/{review_id}").status_code == 404
    assert client.delete(f"/api/v1/reviews/{review_id}").status_code == 204
    review = Review.objects.get(pk=review_id)
    spot.refresh_from_db()
    assert review.status == "hidden" and (spot.rating_avg, spot.rating_count) == (Decimal("0.00"), 0)
    # после удаления можно написать заново — снова через модерацию
    again = _post(client, "spot", spot.id, rating=3)
    assert again.status_code == 200 and again.json()["status"]["code"] == "pending"


def test_demo_reviews_are_not_counted_and_recalculation_task_fixes_drift(make_client):
    spot = SpotFactory(rating_avg=Decimal("4.80"), rating_count=18, is_demo=True)  # демо-оценки из прототипа
    other = SpotFactory()
    Review.objects.create(author=AccountFactory(), target_type="spot", spot=other, rating=4, status="published")
    Review.objects.create(author=AccountFactory(), target_type="spot", spot=other, rating=2, status="published",
                          is_demo=True)
    result = recalculate_ratings.delay().get()
    assert result["fixed"] == 2
    spot.refresh_from_db()
    other.refresh_from_db()
    assert (spot.rating_avg, spot.rating_count) == (Decimal("0.00"), 0)
    assert (other.rating_avg, other.rating_count) == (Decimal("4.00"), 1)
    assert recalculate_all() == 0


def test_organization_and_instructor_ratings_are_recalculated(make_client, mod_client):
    school = OrganizationFactory()
    instructor = InstructorProfileFactory()
    client = make_client()
    completed_lesson_booking(client.account, organization=school, instructor_account=instructor.account)
    org_review = _post(client, "organization", school.id, rating=3).json()["id"]
    ins_review = _post(client, "instructor", instructor.id, rating=5).json()["id"]
    _approve(mod_client, org_review)
    _approve(mod_client, ins_review)
    school.refresh_from_db()
    instructor.refresh_from_db()
    assert (school.rating_avg, school.rating_count) == (Decimal("3.00"), 1)
    assert (instructor.rating_avg, instructor.rating_count) == (Decimal("5.00"), 1)
    # исполнитель получает уведомление о новом опубликованном отзыве
    assert Notification.objects.filter(recipient=instructor.account, kind="review_published").exists()
    assert Notification.objects.filter(recipient=school.owner, kind="review_published").exists()
