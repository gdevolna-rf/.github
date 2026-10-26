"""Сквозные контракты между приложениями (docs/dev/INTEGRATION_NOTES.md).

Гость → 401; координаты чувствительных спотов вне apps/spots; фото дневника и видимость; отзыв доступа сотрудника
к переписке (AT-09); мастерская из POST organizations; порядок блокировок; уведомления learning через commerce;
скан сертификата через mediafiles; ссылки на аренду организации.
"""
import datetime as dt
import re
import uuid
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone

from apps.accounts.models import Specialty, UserProfile
from apps.boards.models import WorkshopProfile
from apps.boards.tests.helpers import rental_booking, std_type
from apps.club.tests.factories import ClubEventFactory
from apps.commerce.models import Booking
from apps.commerce.tests.helpers import attachment, board_inquiry, requested_rental
from apps.community.models import SurfSession
from apps.community.tests.factories import gg_account
from apps.favorites.models import Favorite
from apps.learning.models import InstructorCertificate
from apps.learning.tests.helpers import booking, certificate, published_instructor, school_session
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import ConversationParticipant, MessageAttachment, Notification
from apps.messaging.services.conversations import send_message
from apps.organizations.models import Membership, Organization
from apps.spots.models import Spot
from tests.factories import (
    AccountFactory,
    InventoryItemFactory,
    MediaAssetFactory,
    OrganizationFactory,
    RegionFactory,
    SpotFactory,
    add_member,
    add_specialty,
)

pytestmark = pytest.mark.django_db


# --- 401 для гостя (ARCHITECTURE §2) ---------------------------------------------------------------------------------

def _api_paths():
    """Все маршруты /api/v1/ с подставленными параметрами."""
    samples = {"uuid": str(uuid.uuid4()), "int": "1", "slug": "unknown-slug", "str": "unknown"}

    def walk(patterns, prefix):
        for entry in patterns:
            route = prefix + str(entry.pattern)
            if isinstance(entry, URLResolver):
                yield from walk(entry.url_patterns, route)
            elif isinstance(entry, URLPattern):
                yield route

    for route in walk(get_resolver().url_patterns, "/"):
        if not route.startswith("/api/v1/") or route.endswith(("schema", "docs")):
            continue
        yield re.sub(r"<(?:(\w+):)?(\w+)>", lambda m: samples[m.group(1) or "str"], route)


def test_guest_never_gets_403_and_401_has_unified_body(api_client):
    """401 — «нужен вход» (WWW-Authenticate), 403 — только вошедшему без прав. Проверяем каждый маршрут API."""
    checked_401 = 0
    for path in _api_paths():
        for method in ("get", "post", "put", "patch", "delete"):
            response = getattr(api_client, method)(path, {}, format="json") if method != "get" else api_client.get(path)
            assert response.status_code != 403, (method, path, response.content)
            if response.status_code == 401:
                checked_401 += 1
                body = response.json()["error"]
                assert body["code"] == "not_authenticated", (method, path, body)
                assert body["message"] and "request_id" in body
                assert response["WWW-Authenticate"] == 'Session realm="api"'
    assert checked_401 > 50


def test_authenticated_without_rights_still_gets_403(make_client):
    response = make_client().get("/api/v1/moderation/cases")
    assert response.status_code == 403
    assert response.json()["error"]["code"] in ("permission_denied", "forbidden")


# --- координаты чувствительных спотов (SPT-12) -----------------------------------------------------------------------

EXACT = ("52.934861", "158.779867")


def test_sensitive_spot_coordinates_never_leak_outside_spots_app(api_client, make_client):
    region = RegionFactory(slug="kamchatka-x", center_lat=Decimal("53.0"), center_lng=Decimal("158.6"))
    spot = SpotFactory(region=region, name="Секретная бухта", slug="secret-bay", lat=Decimal(EXACT[0]),
                       lng=Decimal(EXACT[1]), is_sensitive=True, location_precision=Spot.Precision.EXACT,
                       difficulty="beginner")
    instructor = published_instructor(region=region, spots=[spot], student_levels=["beginner"])
    org = OrganizationFactory(region=region, name="Школа у бухты")
    org.spots.add(spot)
    session = school_session(org, spot=spot)
    item = InventoryItemFactory(region=region, spot=spot, title="Доска у бухты")
    event = ClubEventFactory(spot=spot, region=region)
    surfer = gg_account()
    SurfSession.objects.create(account=surfer, spot=spot, date=timezone.localdate(), visibility="public")
    viewer = make_client()
    Favorite.objects.create(account=viewer.account, target_type="spot", spot=spot)

    responses = [
        api_client.get("/api/v1/spots"), api_client.get(f"/api/v1/spots/{spot.slug}"), api_client.get("/api/v1/spots/map"),
        api_client.get("/api/v1/instructors"), api_client.get(f"/api/v1/instructors/{instructor.account.profile.handle}"),
        api_client.get("/api/v1/organizations"), api_client.get(f"/api/v1/organizations/{org.slug}"),
        api_client.get(f"/api/v1/sessions/{session.pk}"),
        api_client.get("/api/v1/rentals"), api_client.get(f"/api/v1/rentals/{item.pk}"),
        api_client.get("/api/v1/club"), api_client.get("/api/v1/club/events"),
        api_client.get(f"/api/v1/club/events/{event.slug}"),
        api_client.get("/api/v1/search?q=бухт"),
        api_client.post("/api/v1/assistant/recommend", {"region": region.slug, "level": "beginner"}, format="json"),
        api_client.get(f"/api/v1/surfers/{surfer.profile.handle}"),
        api_client.get(f"/api/v1/surfers/{surfer.profile.handle}/diary"),
        viewer.get("/api/v1/me/favorites"),
    ]
    for response in responses:
        assert response.status_code == 200, (response.wsgi_request.path, response.content)
        body = response.content.decode()
        for exact in EXACT:
            assert exact[:-1] not in body, (response.wsgi_request.path, exact)
    detail = api_client.get(f"/api/v1/spots/{spot.slug}").json()
    assert detail["precise"] is False and (detail["lat"], detail["lng"]) == (52.93, 158.78)


# --- фото дневника (COM-04, item 8) ----------------------------------------------------------------------------------

def _diary_photo(owner, visibility):
    asset = MediaAssetFactory(owner=owner, purpose=MediaAsset.Purpose.DIARY_PHOTO,
                              storage_key=f"public/diary_photo/{uuid.uuid4().hex}.jpg")
    entry = SurfSession.objects.create(account=owner, spot_name="Бухта", date=timezone.localdate(),
                                       visibility=visibility)
    entry.photos.add(asset)
    return asset


def test_diary_photos_are_public_assets_but_media_endpoints_follow_entry_visibility(api_client, make_client):
    from apps.mediafiles.policy import visibility_for

    assert visibility_for(MediaAsset.Purpose.DIARY_PHOTO) == MediaAsset.Visibility.PUBLIC
    owner = gg_account()
    public, community, private = (_diary_photo(owner, v) for v in ("public", "community", "private"))
    member, outsider, owner_client = make_client(gg_account()), make_client(), make_client(owner)

    def url(client, asset):
        return client.get(f"/api/v1/media/{asset.pk}/url").status_code

    assert [url(api_client, a) for a in (public, community, private)] == [200, 404, 404]
    assert [url(outsider, a) for a in (public, community, private)] == [200, 404, 404]
    assert [url(member, a) for a in (public, community, private)] == [200, 200, 404]
    assert [url(owner_client, a) for a in (public, community, private)] == [200, 200, 200]
    assert api_client.get(f"/api/v1/media/{public.pk}/url").json()["url"].startswith("/")
    assert api_client.get(f"/api/v1/media/{private.pk}").status_code == 404
    # Публичный дневник отдаёт ссылки на фото без отдельного запроса.
    diary = api_client.get(f"/api/v1/surfers/{owner.profile.handle}/diary").json()["results"]
    assert [p["id"] for p in diary[0]["photos"]] == [str(public.pk)] and diary[0]["photos"][0]["url"]
    # Владелец скрыл GG Surfer — фото его записей недоступны другим.
    UserProfile.objects.filter(account=owner).update(gg_surfer_enabled=False)
    assert url(api_client, public) == 404


# --- AT-09: отзыв доступа сотрудника к переписке ---------------------------------------------------------------------

def test_revoked_manager_loses_conversations_messages_and_attachments_immediately(make_client):
    school = OrganizationFactory()
    manager = AccountFactory()
    add_member(school, manager, role=Membership.Role.MANAGER)
    customer = make_client()
    created = customer.post("/api/v1/inquiries", {"kind": "general", "provider_organization_id": str(school.pk),
                                                 "message": "Здравствуйте"}, format="json")
    assert created.status_code == 201, created.content
    inquiry_id, conversation_id = created.json()["id"], created.json()["conversation_id"]
    photo = attachment(customer.account)
    customer.post(f"/api/v1/conversations/{conversation_id}/messages",
                  {"body": "Фото", "attachment_ids": [str(photo.pk)]}, format="json")
    staff = make_client(manager)
    assert staff.get(f"/api/v1/conversations/{conversation_id}/messages").status_code == 200
    assert staff.get(f"/api/v1/media/{photo.pk}/url").status_code == 200
    assert ConversationParticipant.objects.filter(conversation_id=conversation_id, account=manager).exists()

    owner = make_client(school.owner)
    membership = Membership.objects.get(organization=school, account=manager)
    assert owner.delete(f"/api/v1/organizations/{school.pk}/members/{membership.pk}").status_code in (200, 204)

    # Строка участника осталась (история), но доступа больше нет — ни к диалогу, ни к вложениям, ни к inbox.
    assert ConversationParticipant.objects.filter(conversation_id=conversation_id, account=manager).exists()
    assert staff.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
    assert staff.get(f"/api/v1/conversations/{conversation_id}/messages").status_code == 404
    assert staff.post(f"/api/v1/conversations/{conversation_id}/messages", {"body": "Я ещё тут"},
                      format="json").status_code == 404
    assert staff.get(f"/api/v1/inquiries/{inquiry_id}").status_code == 404
    assert staff.get("/api/v1/inquiries?box=incoming").json()["count"] == 0
    assert staff.get(f"/api/v1/media/{photo.pk}/url").status_code == 404
    assert staff.get(f"/api/v1/media/{photo.pk}").status_code == 404
    assert staff.get("/api/v1/me/counters").json()["unread_messages"] == 0
    # Остальные участники и история не пострадали.
    assert owner.get(f"/api/v1/media/{photo.pk}/url").status_code == 200
    assert len(customer.get(f"/api/v1/conversations/{conversation_id}/messages").json()["results"]) >= 2


def test_demoted_manager_of_school_loses_attachment_access(make_client):
    """Роль instructor в школе не даёт доступ к обращениям — и к их вложениям тоже (одно правило для всего)."""
    inquiry, customer, _ = board_inquiry(workshop=OrganizationFactory(kind=Organization.Kind.RENTAL))
    org = inquiry.provider_organization
    manager = AccountFactory()
    membership = add_member(org, manager, role=Membership.Role.MANAGER)
    photo = attachment(customer)
    send_message(inquiry.conversation, customer, body="Фото", attachment_ids=[str(photo.pk)])
    assert MessageAttachment.objects.filter(media=photo).exists()
    client = make_client(manager)
    assert client.get(f"/api/v1/media/{photo.pk}/url").status_code == 200
    membership.role = Membership.Role.INSTRUCTOR
    membership.save()
    assert client.get(f"/api/v1/media/{photo.pk}/url").status_code == 404


# --- мастерская, созданная через POST organizations (SHP-01) ---------------------------------------------------------

def test_workshop_created_via_organizations_gets_profile_and_works_in_boards(make_client):
    client = make_client()
    add_specialty(client.account, Specialty.SHAPER)
    response = client.post("/api/v1/organizations", {"kind": "workshop", "name": "Kamchatka Boards"}, format="json")
    assert response.status_code == 201, response.content
    org_id = response.json()["id"]
    profile = WorkshopProfile.objects.get(organization_id=org_id)
    assert re.fullmatch(r"[A-Z]{3}\d{2,3}", profile.shaper_code)
    me = client.get("/api/v1/me/workshop")
    assert me.status_code == 200 and me.json()["id"] == org_id
    assert me.json()["shaper_code"] == profile.shaper_code
    model = client.post(f"/api/v1/workshops/{org_id}/models", {
        "name": "Fish", "board_type_id": std_type("fish").pk,
        "variants": [{"length_in": "70", "width_in": "21", "price": "60000"}]}, format="json")
    assert model.status_code == 201, model.content
    assert model.json()["variants"][0]["sku"].startswith(f"GV-{profile.shaper_code}-FSH-")


# --- порядок блокировок: экземпляр → бронь (item 11) -----------------------------------------------------------------

def _lock_positions(queries):
    item = booking_ = None
    for index, query in enumerate(queries):
        sql = query["sql"]
        if "FOR UPDATE" not in sql:
            continue
        if 'FROM "inventory_inventoryitem"' in sql and item is None:
            item = index
        if 'FROM "commerce_booking"' in sql and booking_ is None:
            booking_ = index
    return item, booking_


def test_handover_and_confirm_lock_item_before_booking(make_client):
    item = InventoryItemFactory()
    issued = rental_booking(item, status=Booking.Status.CONFIRMED,
                            start=timezone.now().replace(microsecond=0) + dt.timedelta(days=3))
    pending = requested_rental(item)
    owner = make_client(item.owner_account)
    with CaptureQueriesContext(connection) as ctx:
        response = owner.post(f"/api/v1/bookings/{issued.pk}/handover", {"kind": "issue", "condition": "good"},
                              format="json")
    assert response.status_code in (200, 201), response.content
    item_lock, booking_lock = _lock_positions(ctx.captured_queries)
    assert item_lock is not None and booking_lock is not None and item_lock < booking_lock
    with CaptureQueriesContext(connection) as ctx:
        owner.post(f"/api/v1/bookings/{pending.pk}/confirm", {}, format="json")
    item_lock, booking_lock = _lock_positions(ctx.captured_queries)
    assert item_lock is not None and booking_lock is not None and item_lock < booking_lock


# --- learning → уведомления через commerce.notify_booking_status (item 12) -------------------------------------------

def test_session_cancel_complete_reschedule_notify_customers_as_booking_status(make_client):
    org = OrganizationFactory()
    owner = make_client(org.owner)
    upcoming = school_session(org)
    moved = booking(upcoming)
    start = upcoming.starts_at + dt.timedelta(days=1)
    response = owner.post(f"/api/v1/sessions/{upcoming.pk}/reschedule",
                          {"starts_at": start.isoformat(), "ends_at": (start + dt.timedelta(hours=2)).isoformat(),
                           "reason": "Шторм"}, format="json")
    assert response.status_code == 200, response.content
    note = Notification.objects.get(recipient=moved.customer, title="Занятие перенесено")
    assert note.kind == Notification.Kind.BOOKING_STATUS and note.link == f"/account/bookings/{moved.pk}"
    assert {"booking_id", "status", "kind", "session_id"} <= set(note.payload)

    assert owner.post(f"/api/v1/sessions/{upcoming.pk}/cancel", {"reason": "Нет волн"}, format="json").status_code == 200
    cancelled = Notification.objects.get(recipient=moved.customer, title="Занятие отменено")
    assert cancelled.payload["status"] == Booking.Status.CANCELLED and "Нет волн" in cancelled.body

    past = school_session(org, start=timezone.now().replace(microsecond=0) - dt.timedelta(hours=3))
    came, missed = booking(past), booking(past)
    response = owner.post(f"/api/v1/sessions/{past.pk}/complete", {"no_show_booking_ids": [str(missed.pk)]},
                          format="json")
    assert response.status_code == 200, response.content
    done = Notification.objects.get(recipient=came.customer, kind=Notification.Kind.BOOKING_STATUS)
    assert done.title == "Занятие проведено" and done.payload["status"] == Booking.Status.COMPLETED
    no_show = Notification.objects.get(recipient=missed.customer, kind=Notification.Kind.BOOKING_STATUS)
    assert no_show.payload["status"] == Booking.Status.NO_SHOW


# --- скан сертификата и media/{id}/url — одни правила (item 13) ------------------------------------------------------

def test_certificate_scan_and_media_url_share_public_rules(api_client, make_client):
    profile = published_instructor()
    cert = certificate(profile, status=InstructorCertificate.Status.VERIFIED, allow_public_scan=True)
    scan = api_client.get(f"/api/v1/certificates/{cert.pk}/scan")
    media = api_client.get(f"/api/v1/media/{cert.document_id}/url")
    assert scan.status_code == media.status_code == 200
    assert scan.json()["url"].split("?")[0] == media.json()["url"].split("?")[0]
    cert.valid_until = timezone.localdate() - dt.timedelta(days=1)
    cert.save()
    assert api_client.get(f"/api/v1/certificates/{cert.pk}/scan").status_code == 404
    assert api_client.get(f"/api/v1/media/{cert.document_id}/url").status_code == 404
    owner = make_client(profile.account)
    assert owner.get(f"/api/v1/certificates/{cert.pk}/scan").status_code == 200


# --- ссылка «Аренда организации» (item 7) ----------------------------------------------------------------------------

def test_rentals_link_of_rental_organization_filters_by_slug(api_client):
    """Ссылка на прокат-организацию (поиск, избранное, клуб) ведёт в каталог аренды с фильтром по slug."""
    from apps.search.services.catalog import organization_url

    rental = OrganizationFactory(kind=Organization.Kind.RENTAL, slug="volna-rent")
    own = InventoryItemFactory(owner_account=None, owner_organization=rental)
    InventoryItemFactory()
    link = organization_url(rental)
    assert link == "/rentals?organization=volna-rent"
    response = api_client.get("/api/v1" + link)
    assert {r["id"] for r in response.json()["results"]} == {str(own.pk)}
    assert api_client.get("/api/v1/rentals?organization=unknown-org").json()["results"] == []


# --- AT-10: удалённый инструктор ------------------------------------------------------------------------------------

def test_deleted_instructor_private_bookings_cancelled_and_school_assignment_released(make_client, run_on_commit):
    from apps.accounts.services.deletion import anonymize_account
    from apps.learning.models import LessonSession
    from apps.learning.tests.helpers import private_session, school_instructor

    profile = published_instructor()
    coach = profile.account
    slot = private_session(profile, hours=40)
    student = AccountFactory()
    private_booking = booking(slot, customer=student)
    org = OrganizationFactory()
    manager = AccountFactory()
    add_member(org, manager, role=Membership.Role.MANAGER)
    school_instructor(org, coach)
    group = school_session(org, instructor=coach, hours=60)
    pupil_booking = booking(group)

    run_on_commit(anonymize_account, coach)

    private_booking.refresh_from_db()
    assert private_booking.status == Booking.Status.CANCELLED and private_booking.cancelled_side == "system"
    assert Notification.objects.filter(recipient=student, kind=Notification.Kind.BOOKING_STATUS).exists()
    assert LessonSession.objects.get(pk=slot.pk).status == LessonSession.Status.CANCELLED
    group.refresh_from_db()
    assert group.instructor_id is None and group.status == LessonSession.Status.SCHEDULED
    pupil_booking.refresh_from_db()
    assert pupil_booking.status == Booking.Status.CONFIRMED  # запись ученика школы сохраняется
    assert Notification.objects.filter(recipient=manager, kind=Notification.Kind.LESSON_ASSIGNED,
                                       payload__session_id=str(group.pk)).exists()


# --- ограничение профиля (suspended) одинаково во всех каталогах ------------------------------------------------------

def test_suspended_account_is_hidden_from_every_catalog_and_cannot_be_booked(api_client, make_client):
    """F14: «профиль ограничен» — карточка инструктора, личные объявления и слоты не видны ни в каталогах,
    ни в поиске/избранном/помощнике, и забронировать их по прямой ссылке нельзя."""
    from apps.learning.tests.helpers import private_session
    from apps.trust.models import AccountRestriction

    region = RegionFactory(slug="suspended-region")
    profile = published_instructor(region=region, student_levels=["beginner"], headline="Подозрительный инструктор")
    profile.account.profile.first_name = "Подозрительный"
    profile.account.profile.save()
    slot = private_session(profile, hours=30)
    item = InventoryItemFactory(owner_account=profile.account, region=region, title="Подозрительная доска")
    viewer = make_client()
    Favorite.objects.create(account=viewer.account, target_type="instructor", instructor=profile)
    AccountRestriction.objects.create(account=profile.account, kind="suspended", reason="Мошенничество")

    handle = profile.account.profile.handle
    assert api_client.get(f"/api/v1/instructors/{handle}").status_code == 404
    assert str(profile.pk) not in {i["id"] for i in api_client.get("/api/v1/instructors").json()["results"]}
    search = api_client.get("/api/v1/search?q=Подозрительн").json()
    found = {r["id"] for group in search["groups"] for r in group["results"]}
    assert str(profile.pk) not in found and str(item.pk) not in found
    recommend = api_client.post("/api/v1/assistant/recommend", {"region": region.slug, "level": "beginner"},
                                format="json").json()
    assert str(profile.pk) not in {i["id"] for i in recommend["instructors"]}
    assert str(item.pk) not in {i["id"] for i in recommend["rentals"]}
    assert str(item.pk) not in {r["id"] for r in api_client.get("/api/v1/rentals").json()["results"]}
    assert api_client.get(f"/api/v1/rentals/{item.pk}").status_code == 404
    assert viewer.get("/api/v1/me/favorites").json()["results"] == [] or all(
        f["target_id"] != str(profile.pk) for f in viewer.get("/api/v1/me/favorites").json()["results"])
    customer = make_client()
    assert customer.post("/api/v1/bookings", {"lesson_session_id": str(slot.pk)}, format="json").status_code == 404
    start = timezone.now().replace(microsecond=0) + dt.timedelta(days=2)
    assert customer.post("/api/v1/bookings", {"inventory_item_id": str(item.pk), "starts_at": start.isoformat(),
                                              "ends_at": (start + dt.timedelta(hours=4)).isoformat()},
                         format="json").status_code == 404
    # Обращение по прямому id тоже не создаётся — объект скрыт из каталога.
    for payload in ({"kind": "lesson", "target_type": "instructor_offer", "target_id": str(slot.offer_id)},
                    {"kind": "lesson", "target_type": "lesson_session", "target_id": str(slot.pk)},
                    {"kind": "rental", "target_type": "inventory_item", "target_id": str(item.pk)},
                    {"kind": "general", "provider_account_id": str(profile.account_id)}):
        response = customer.post("/api/v1/inquiries", {**payload, "message": "Здравствуйте"}, format="json")
        assert response.status_code == 404, (payload, response.content)


def test_spot_hidden_by_moderation_disappears_from_other_apps_cards(api_client):
    region = RegionFactory()
    spot = SpotFactory(region=region, name="Скрытая бухта")
    org = OrganizationFactory(region=region)
    org.spots.add(spot)
    session = school_session(org, spot=spot)
    item = InventoryItemFactory(region=region, spot=spot)
    assert api_client.get(f"/api/v1/sessions/{session.pk}").json()["spot"]["slug"] == spot.slug
    Spot.objects.filter(pk=spot.pk).update(status=Spot.Status.HIDDEN)
    for path in (f"/api/v1/sessions/{session.pk}", f"/api/v1/rentals/{item.pk}", f"/api/v1/organizations/{org.slug}"):
        body = api_client.get(path)
        assert body.status_code == 200 and "Скрытая бухта" not in body.content.decode(), path
    assert api_client.get(f"/api/v1/sessions/{session.pk}").json()["spot"] is None
