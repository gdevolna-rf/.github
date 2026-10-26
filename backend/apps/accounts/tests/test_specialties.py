"""«Мои направления» (7.1, BR-02, BR-04, BR-11, ACC-10, ACC-12, ATX-17)."""
import pytest

from apps.accounts.models import UserSpecialty
from apps.boards.models import BoardModel
from apps.commerce.models import Booking, Inquiry
from apps.learning.models import InstructorProfile
from apps.trust.models import AuditEvent
from tests.factories import (
    AccountFactory,
    BoardModelFactory,
    InstructorProfileFactory,
    LessonSessionFactory,
    WorkshopFactory,
    add_specialty,
)

pytestmark = pytest.mark.django_db


def url(code):
    return f"/api/v1/me/specialties/{code}"


def test_activate_instructor_keeps_same_account_id(auth_client):
    """AT-02: подключение направления не создаёт новую идентичность."""
    account_id = auth_client.get("/api/v1/me").json()["id"]
    response = auth_client.put(url("instructor"))
    assert response.status_code == 200
    body = response.json()
    assert body["specialty"]["code"] == "instructor" and body["specialty"]["status"] == "active"
    assert body["next_step"] == "instructor_profile"
    me = auth_client.get("/api/v1/me").json()
    assert me["id"] == account_id
    assert {s["code"] for s in me["specialties"] if s["status"] == "active"} == {"surfer", "instructor"}
    assert AuditEvent.objects.filter(action="specialty.activated").count() == 1


def test_activate_shaper_suggests_workshop(auth_client):
    assert auth_client.put(url("shaper")).json()["next_step"] == "create_workshop"


def test_activate_twice_is_idempotent(auth_client):
    auth_client.put(url("rental"))
    auth_client.put(url("rental"))
    assert UserSpecialty.objects.filter(account=auth_client.account, specialty_id="rental").count() == 1
    assert AuditEvent.objects.filter(action="specialty.activated").count() == 1


def test_school_is_not_a_specialty(auth_client):
    response = auth_client.put(url("school"))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "school_is_organization"


@pytest.mark.parametrize("code", ["admin", "moderator", "organizer"])
def test_staff_roles_cannot_be_toggled(auth_client, code):
    """BR-04, ACC-10."""
    assert auth_client.put(url(code)).status_code == 403
    assert auth_client.delete(url(code)).status_code == 403
    assert auth_client.get("/api/v1/me").json()["staff_roles"] == []


def test_unknown_specialty_is_404(auth_client):
    assert auth_client.put(url("astronaut")).status_code == 404


def test_guest_cannot_toggle(api_client):
    assert api_client.put(url("instructor")).status_code == 401


def test_surfer_cannot_be_disabled(auth_client):
    response = auth_client.delete(url("surfer"))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "surfer_required"


def test_disable_instructor_warns_and_keeps_history(make_client):
    """BR-11 / 7.1 п.5: активные брони не уничтожаются, система предупреждает."""
    instructor = InstructorProfileFactory()
    account = instructor.account
    client = make_client(account)
    session = LessonSessionFactory(instructor=account)
    customer = AccountFactory()
    booking = Booking.objects.create(kind=Booking.Kind.LESSON, customer=customer, provider_account=account,
                                     lesson_session=session, starts_at=session.starts_at, ends_at=session.ends_at,
                                     status=Booking.Status.CONFIRMED)
    Inquiry.objects.create(kind=Inquiry.Kind.LESSON, customer=customer, provider_account=account, subject="Урок")
    response = client.delete(url("instructor"))
    assert response.status_code == 200
    body = response.json()
    assert body["specialty"]["status"] == "disabled"
    codes = {w["code"] for w in body["warnings"]}
    assert codes == {"instructor_profile_published", "active_bookings", "open_inquiries", "upcoming_sessions"}
    assert body["unpublished"] == []
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED
    instructor.refresh_from_db()
    assert instructor.status == InstructorProfile.Status.PUBLISHED
    row = UserSpecialty.objects.get(account=account, specialty_id="instructor")
    assert row.disabled_at is not None


def test_disable_instructor_with_unpublish_hides_card(make_client):
    instructor = InstructorProfileFactory()
    response = make_client(instructor.account).delete(url("instructor") + "?unpublish=true")
    body = response.json()
    assert body["unpublished"] == [{"type": "instructor_profile", "id": str(instructor.pk)}]
    assert "instructor_profile_hidden" in {w["code"] for w in body["warnings"]}
    instructor.refresh_from_db()
    assert instructor.status == InstructorProfile.Status.HIDDEN


def test_disable_shaper_keeps_workshop_models_and_orders(make_client):
    """ATX-17: прошлые заказы и история не исчезают."""
    model = BoardModelFactory()
    workshop = model.workshop
    owner = workshop.owner
    inquiry = Inquiry.objects.create(kind=Inquiry.Kind.BOARD_PURCHASE, customer=AccountFactory(),
                                     provider_organization=workshop, board_model=model, subject="Доска")
    response = make_client(owner).delete(url("shaper") + "?unpublish=true")
    assert response.status_code == 200
    codes = {w["code"] for w in response.json()["warnings"]}
    assert {"workshop_published", "published_board_models", "open_inquiries"} <= codes
    assert response.json()["unpublished"] == []  # мастерская — организация: только предупреждение
    assert BoardModel.objects.get(pk=model.pk).status == BoardModel.Status.PUBLISHED
    assert Inquiry.objects.filter(pk=inquiry.pk).exists()
    workshop.refresh_from_db()
    assert workshop.status == "published"


def test_reactivation_restores_same_row(make_client):
    account = AccountFactory()
    row = add_specialty(account, "rental")
    client = make_client(account)
    client.delete(url("rental"))
    client.put(url("rental"))
    row.refresh_from_db()
    assert row.status == "active" and row.disabled_at is None
    assert UserSpecialty.objects.filter(account=account, specialty_id="rental").count() == 1


def test_disabling_primary_falls_back_to_surfer(make_client):
    account = AccountFactory()
    UserSpecialty.objects.filter(account=account, specialty_id="surfer").update(is_primary=False)
    UserSpecialty.objects.create(account=account, specialty_id="instructor", is_primary=True)
    make_client(account).delete(url("instructor"))
    assert UserSpecialty.objects.get(account=account, specialty_id="surfer").is_primary
    assert not UserSpecialty.objects.get(account=account, specialty_id="instructor").is_primary


def test_disable_not_connected_specialty_is_404(auth_client):
    assert auth_client.delete(url("shaper")).status_code == 404


def test_workshop_factory_owner_gets_warning_only_for_own_workshops(make_client):
    WorkshopFactory()  # чужая мастерская
    account = AccountFactory()
    add_specialty(account, "shaper")
    response = make_client(account).delete(url("shaper"))
    assert response.json()["warnings"] == []
