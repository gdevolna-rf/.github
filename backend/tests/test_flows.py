"""Сквозные сценарии ТЗ §31 (F01–F15) на уровне API: один тест — один путь пользователя через несколько приложений.

Данные готовятся фабриками только там, где путь их не создаёт (споты, регионы, модераторы); всё остальное — через
публичный API, как это делает фронтенд. S3 подменён in-memory хранилищем mediafiles (backend/conftest.py), письма —
locmem, Celery — eager. «Прошло время» имитируется сдвигом starts_at в БД (helpers ``_time_passes``).
Приёмочные AT-01…AT-10 покрыты внутри сценариев (ссылки в docstring).
"""
import datetime as dt
import re
import threading
from decimal import Decimal

import pytest
from django.core import mail
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analytics.models import AnalyticsEvent
from apps.boards.models import BoardVariant
from apps.commerce.models import Booking, Inquiry
from apps.community.models import BirthdayGreeting
from apps.community.tasks import send_birthday_greetings
from apps.learning.models import LessonSession
from apps.mediafiles.tests.utils import MP4_BYTES, make_image, upload_ready
from apps.messaging.models import Notification
from apps.organizations.models import Membership, OrganizationInvite
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory, InventoryItemFactory, RegionFactory, SpotFactory, make_moderator

pytestmark = pytest.mark.django_db

K = Notification.Kind
PASSWORD = "Volna-2026-secure"


# --- помощники -----------------------------------------------------------------------------------------------------

def ok(response, status=200):
    assert response.status_code == status, (response.wsgi_request.method, response.wsgi_request.path,
                                            response.content.decode()[:800])
    return response.json() if response.content else None


def results(data):
    return data["results"] if isinstance(data, dict) and "results" in data else data


def register(run_on_commit, email, primary_type="surfer", extra=(), first_name="Иван", last_name="Петров"):
    """POST auth/register (сессия создаётся сразу) + подтверждение email по ссылке из письма."""
    client = APIClient()
    data = ok(run_on_commit(client.post, "/api/v1/auth/register", {
        "email": email, "password": PASSWORD, "first_name": first_name, "last_name": last_name,
        "primary_type": primary_type, "extra_specialties": list(extra), "accept_terms": True, "accept_privacy": True,
    }, format="json"), 201)
    letter = next(m for m in reversed(mail.outbox) if email in m.to)
    token = re.search(r"verify-email\?token=(\S+)", letter.body).group(1)
    ok(client.post("/api/v1/auth/verify-email", {"token": token}, format="json"))
    client.account_id = data["id"]
    client.handle = data["profile"]["handle"]
    return client


def notifications(client, kind=None):
    items = results(ok(client.get("/api/v1/me/notifications?page_size=100")))
    return [n for n in items if kind is None or n["kind"] == kind]


def moderator_client():
    client = APIClient()
    client.force_login(make_moderator(AccountFactory()))
    from apps.accounts.services.roles import OTP_SESSION_KEY

    session = client.session
    session[OTP_SESSION_KEY] = "test"
    session.save()
    return client


def _time_passes(session_id, hours_ago=3):
    """Занятие уже прошло: сдвигаем время занятия и его броней в прошлое (вместо заморозки часов)."""
    start = timezone.now().replace(microsecond=0) - dt.timedelta(hours=hours_ago)
    session = LessonSession.objects.get(pk=session_id)
    duration = session.ends_at - session.starts_at
    LessonSession.objects.filter(pk=session_id).update(starts_at=start, ends_at=start + duration)
    Booking.objects.filter(lesson_session_id=session_id).update(starts_at=start, ends_at=start + duration)


def iso(moment):
    return moment.isoformat()


def next_hour(hours):
    return timezone.now().replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=hours)


def _publish_workshop_with_model(run_on_commit, email, region, *, name="Kamchatka Boards", model_name="Retro Fish",
                                 board_type_id=None, variants=None):
    """Шейпер через API: направление → мастерская → модель с вариантом и обложкой → публикация."""
    shaper = register(run_on_commit, email, first_name="Пётр", last_name="Шейпер")
    ok(shaper.put("/api/v1/me/specialties/shaper"))
    workshop = ok(shaper.put("/api/v1/me/workshop", {"name": name, "region_id": region.pk,
                                                     "specialization": "Фиши и мидлленги"}, format="json"), 201)
    if board_type_id is None:
        types = ok(shaper.get(f"/api/v1/workshops/{workshop['id']}/board-types"))
        board_type_id = next(t["id"] for t in types if t["code"] == "shortboard")
    model = ok(shaper.post(f"/api/v1/workshops/{workshop['id']}/models", {
        "name": model_name, "board_type_id": board_type_id,
        "variants": variants or [{"length_in": "70", "width_in": "21", "thickness_in": "2.6", "volume_l": "38",
                                  "price": "65000"}],
    }, format="json"), 201)
    cover = upload_ready(shaper, run_on_commit, purpose="board_photo")
    ok(shaper.post(f"/api/v1/models/{model['id']}/media", {"media_ids": [str(cover.pk)]}, format="json"), 201)
    ok(shaper.post(f"/api/v1/workshops/{workshop['id']}/publish"))
    ok(shaper.post(f"/api/v1/models/{model['id']}/publish"))
    return shaper, workshop, model


# --- F01 ------------------------------------------------------------------------------------------------------------

def test_f01_guest_to_registration_inquiry_chat_status_completion_review(api_client, run_on_commit):
    """F01 (+AT-01, AT-04): гость → каталог шейперов → регистрация → заявка → чат → статус → уведомление →
    завершение → отзыв (виден после модерации)."""
    region = RegionFactory()
    shaper, workshop, model = _publish_workshop_with_model(run_on_commit, "shaper-f01@example.com", region)

    shapers = results(ok(api_client.get("/api/v1/shapers")))
    assert workshop["slug"] in {s["slug"] for s in shapers}
    board = ok(api_client.get(f"/api/v1/boards/{model['id']}"))
    assert board["name"] == "Retro Fish" and board["variants"]

    customer = register(run_on_commit, "rider-f01@example.com")
    assert {s["code"] for s in ok(customer.get("/api/v1/me"))["specialties"]} == {"surfer"}  # AT-01: без шейпера
    created = ok(customer.post("/api/v1/inquiries", {"kind": "board_purchase", "target_type": "board_model",
                                                     "target_id": model["id"], "message": "Есть в наличии 5'10?"},
                               format="json"), 201)
    conversation = created["conversation_id"]
    # Чат доступен сразу, до принятия (BR-06); два сообщения → у шейпера непрочитанные (AT-04).
    ok(customer.post(f"/api/v1/conversations/{conversation}/messages", {"body": "И ещё: какой объём?"},
                     format="json"), 201)
    assert ok(shaper.get("/api/v1/me/counters"))["unread_messages"] == 2
    inbox = results(ok(shaper.get("/api/v1/inquiries?box=incoming")))
    assert [i["id"] for i in inbox] == [created["id"]] and inbox[0]["unread_count"] == 2
    assert any(n["kind"] == K.INQUIRY_NEW for n in notifications(shaper))
    ok(shaper.post(f"/api/v1/conversations/{conversation}/read", {}, format="json"))
    assert ok(shaper.get("/api/v1/me/counters"))["unread_messages"] == 0

    assert ok(shaper.post(f"/api/v1/inquiries/{created['id']}/accept", {}, format="json"))["status"] == "in_progress"
    status_note = [n for n in notifications(customer, K.INQUIRY_STATUS) if "/account/inquiries/" in n["link"]]
    assert status_note
    assert ok(customer.get(f"/api/v1/inquiries/{created['id']}"))["status"] == "in_progress"
    done = ok(shaper.post(f"/api/v1/inquiries/{created['id']}/complete",
                          {"agreed_amount": "65000", "amount_confirmed": True}, format="json"))
    assert done["status"] == "completed"
    assert AnalyticsEvent.objects.filter(name="deal_completed").exists()

    review = ok(customer.post("/api/v1/reviews", {"target_type": "organization", "target_id": workshop["id"],
                                                  "rating": 5, "text": "Доска мечты, всё чётко"}, format="json"), 201)
    assert review["status"]["code"] == "pending"
    public = api_client.get(f"/api/v1/reviews?target_type=organization&target_id={workshop['id']}")
    assert results(ok(public)) == []  # до модерации не виден (BR-08)
    ok(moderator_client().post(f"/api/v1/moderation/reviews/{review['id']}/approve", {}, format="json"))
    assert [r["id"] for r in results(ok(api_client.get(
        f"/api/v1/reviews?target_type=organization&target_id={workshop['id']}")))] == [review["id"]]
    profile = ok(api_client.get(f"/api/v1/shapers/{workshop['slug']}"))
    assert Decimal(str(profile["rating_avg"])) == Decimal("5") and profile["rating_count"] == 1


# --- F02 ------------------------------------------------------------------------------------------------------------

def test_f02_surfer_connects_shaper_publishes_fish_model_with_media_and_gets_foreign_order(api_client, run_on_commit):
    """F02 (+AT-02, AT-03): сёрфер → «Мои направления» → шейпер → мастерская → свой тип Fish → модель + 10 фото +
    видео → публичный каталог → чужой клиент заказывает; заказ «к себе» запрещён."""
    region = RegionFactory()
    surfer = register(run_on_commit, "surfer-f02@example.com", first_name="Анна", last_name="Волнова")
    ok(surfer.put("/api/v1/me/specialties/shaper"))
    ok(surfer.put("/api/v1/me/specialties/instructor"))
    me = ok(surfer.get("/api/v1/me"))
    assert me["id"] == surfer.account_id  # AT-02: один account_id, разные инструменты
    assert {s["code"] for s in me["specialties"] if s["status"] == "active"} >= {"surfer", "shaper", "instructor"}

    workshop = ok(surfer.put("/api/v1/me/workshop", {"name": "Volnova Shapes", "region_id": region.pk,
                                                     "specialization": "Фиши"}, format="json"), 201)
    fish = ok(surfer.post(f"/api/v1/workshops/{workshop['id']}/board-types", {"name": "Fish Retro",
                                                                             "silhouette": "fish"}, format="json"), 201)
    assert fish["is_custom"] is True
    model = ok(surfer.post(f"/api/v1/workshops/{workshop['id']}/models", {
        "name": "Twin Fish", "board_type_id": fish["id"], "description": "Для мягких волн",
        "variants": [{"length": "5'8\"", "width": "21", "thickness": "2 1/2", "volume_l": "34", "price": "70000"}],
    }, format="json"), 201)
    photos = [upload_ready(surfer, run_on_commit, make_image(color=color), purpose="board_photo")
              for color in ("red", "blue", "green", "white", "black", "yellow", "gray", "orange", "purple", "pink")]
    gallery = ok(surfer.post(f"/api/v1/models/{model['id']}/media", {"media_ids": [str(p.pk) for p in photos]},
                             format="json"), 201)
    assert len(gallery["photos"]) == 10 and gallery["photos"][0]["is_cover"] is True
    clip = upload_ready(surfer, run_on_commit, MP4_BYTES, kind="video", purpose="board_video",
                        content_type="video/mp4", filename="ride.mp4")
    ok(surfer.put(f"/api/v1/models/{model['id']}/video", {"media_id": str(clip.pk)}, format="json"))
    ok(surfer.post(f"/api/v1/workshops/{workshop['id']}/publish"))
    ok(surfer.post(f"/api/v1/models/{model['id']}/publish"))

    catalog = results(ok(api_client.get(f"/api/v1/boards?shaper={workshop['slug']}")))
    assert [b["id"] for b in catalog] == [model["id"]]
    detail = ok(api_client.get(f"/api/v1/boards/{model['id']}"))
    assert detail["board_type"]["name"] == "Fish Retro" and len(detail["photos"]) == 10 and detail["has_video"]
    assert detail["variants"][0]["sku"].startswith(f"GV-{ok(surfer.get('/api/v1/me/workshop'))['shaper_code']}-")

    own = surfer.post("/api/v1/inquiries", {"kind": "custom_order", "target_type": "board_model",
                                             "target_id": model["id"], "message": "Себе"}, format="json")
    assert own.status_code == 403 and own.json()["error"]["code"] == "self_inquiry"  # AT-03
    client = register(run_on_commit, "client-f02@example.com", first_name="Олег", last_name="Клиент")
    order = ok(client.post("/api/v1/inquiries", {"kind": "custom_order", "target_type": "board_model",
                                                 "target_id": model["id"], "message": "Хочу такую 5'10"},
                           format="json"), 201)
    assert order["status"] == "new"
    assert [i["id"] for i in results(ok(surfer.get("/api/v1/inquiries?box=incoming&role=shaper")))] == [order["id"]]


# --- F03 ------------------------------------------------------------------------------------------------------------

def test_f03_instructor_without_certificate_publishes_and_gets_booked(api_client, run_on_commit):
    """F03: инструктор без сертификата → регистрация → публикация после базовых полей → карточка без бейджа →
    клиент бронирует занятие, инструктор подтверждает."""
    region = RegionFactory()
    coach = register(run_on_commit, "coach-f03@example.com", primary_type="instructor", first_name="Илья",
                     last_name="Тренер")
    missing = coach.post("/api/v1/me/instructor/publish")
    assert missing.status_code in (400, 404)
    ok(coach.put("/api/v1/me/instructor", {"headline": "Учу вставать на доску за 1 день", "region_slugs": [region.slug],
                                           "formats": ["individual"], "price_from": "4000",
                                           "student_levels": ["beginner"]}, format="json"))
    assert ok(coach.post("/api/v1/me/instructor/publish"))["status"] == "published"
    card = next(c for c in results(ok(api_client.get("/api/v1/instructors"))) if c["handle"] == coach.handle)
    assert card["certificate_status"] == "none"

    offer = ok(coach.post("/api/v1/me/instructor/offers", {"title": "Индивидуальный урок", "price": "4500",
                                                           "format": "individual"}, format="json"), 201)
    slot = ok(coach.post("/api/v1/me/instructor/sessions", {"offer_id": offer["id"],
                                                            "starts_at": iso(next_hour(30))}, format="json"), 201)
    detail = ok(api_client.get(f"/api/v1/instructors/{coach.handle}"))
    assert slot["id"] in {s["id"] for s in detail["upcoming_slots"]}
    assert detail["certificate_status"] == "none" and detail["certificates"] == []

    client = register(run_on_commit, "client-f03@example.com", first_name="Ольга", last_name="Ученица")
    booking = ok(client.post("/api/v1/bookings", {"lesson_session_id": slot["id"]}, format="json"), 201)
    assert booking["status"] == "requested" and booking["price_amount"] == "4500.00"
    assert any(n["kind"] == K.BOOKING_NEW for n in notifications(coach))
    assert ok(coach.post(f"/api/v1/bookings/{booking['id']}/confirm", {}, format="json"))["status"] == "confirmed"
    assert any(n["kind"] == K.BOOKING_STATUS for n in notifications(client))
    schedule = results(ok(coach.get("/api/v1/me/schedule")))
    assert slot["id"] in {item["id"] for item in schedule}


# --- F04 ------------------------------------------------------------------------------------------------------------

def test_f04_certificate_moderation_sets_verified_badge(api_client, run_on_commit):
    """F04 (BR-07, ATX-05): сертификат → модерация → «Проверен» на публичной карточке только после решения."""
    region = RegionFactory()
    coach = register(run_on_commit, "coach-f04@example.com", primary_type="instructor", first_name="Вера",
                     last_name="Сертификатова")
    ok(coach.put("/api/v1/me/instructor", {"headline": "ISA", "region_slugs": [region.slug], "formats": ["group"],
                                           "price_from": "3000"}, format="json"))
    ok(coach.post("/api/v1/me/instructor/publish"))
    scan = upload_ready(coach, run_on_commit, b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n", kind="document",
                        purpose="certificate", content_type="application/pdf", filename="isa.pdf")
    cert = ok(coach.post("/api/v1/me/instructor/certificates", {"title": "ISA Level 1", "document_id": str(scan.pk),
                                                                "allow_public_scan": True}, format="json"), 201)

    def badge():
        return ok(api_client.get(f"/api/v1/instructors/{coach.handle}"))["certificate_status"]

    assert badge() == "uploaded"
    assert api_client.get(f"/api/v1/certificates/{cert['id']}/scan").status_code == 404  # ещё не проверен
    moderator = moderator_client()
    cases = results(ok(moderator.get("/api/v1/moderation/cases?kind=certificate")))
    assert any(c["target_id"] == cert["id"] for c in cases)
    ok(moderator.post(f"/api/v1/moderation/certificates/{cert['id']}/approve", {"note": "Сверено"}, format="json"))
    assert badge() == "verified"
    assert ok(api_client.get(f"/api/v1/certificates/{cert['id']}/scan"))["url"]
    assert any(n["kind"] == K.CERTIFICATE_DECISION for n in notifications(coach))
    assert AuditEvent.objects.filter(action="certificate.verified", object_id=cert["id"]).exists()


# --- F05 ------------------------------------------------------------------------------------------------------------

def test_f05_school_program_invite_session_booking_schedule_completion_metrics(api_client, run_on_commit):
    """F05 (+AT-06): школа → программа → приглашение инструктора → принятие → занятие → запись ученика →
    расписание инструктора → проведение → аналитика."""
    region = RegionFactory()
    spot = SpotFactory(region=region)
    owner = register(run_on_commit, "school-f05@example.com", primary_type="school", first_name="Мария",
                     last_name="Директор")
    school = ok(owner.post("/api/v1/organizations", {"kind": "school", "name": "Сёрф-школа Прибой",
                                                     "description": "Учим с нуля", "region_id": region.pk,
                                                     "spot_ids": [str(spot.pk)]}, format="json"), 201)
    ok(owner.post(f"/api/v1/organizations/{school['id']}/submit"))
    ok(moderator_client().post(f"/api/v1/moderation/organizations/{school['id']}/approve", {}, format="json"))
    program = ok(owner.post(f"/api/v1/organizations/{school['id']}/programs", {
        "title": "Новички", "price": "3500", "max_group_size": 6, "duration_min": 120}, format="json"), 201)

    coach = register(run_on_commit, "coach-f05@example.com", primary_type="instructor", first_name="Глеб",
                     last_name="Инструктор")
    ok(run_on_commit(owner.post, f"/api/v1/organizations/{school['id']}/invites",
                     {"email": "coach-f05@example.com", "role": "instructor"}, format="json"), 201)
    assert any(n["kind"] == K.INVITE for n in notifications(coach))
    token = OrganizationInvite.objects.get(email="coach-f05@example.com").token
    ok(coach.post(f"/api/v1/invites/{token}/accept", {}, format="json"))
    assert Membership.objects.filter(organization_id=school["id"], account_id=coach.account_id,
                                     status="active").exists()

    start = next_hour(26)
    session = ok(owner.post(f"/api/v1/organizations/{school['id']}/sessions", {
        "program_id": program["id"], "starts_at": iso(start), "instructor_id": coach.account_id,
        "spot_slug": spot.slug, "capacity": 4}, format="json"), 201)
    assert any(n["kind"] == K.LESSON_ASSIGNED for n in notifications(coach))
    # AT-06: конфликтующее второе занятие того же инструктора блокируется.
    clash = owner.post(f"/api/v1/organizations/{school['id']}/sessions", {
        "program_id": program["id"], "starts_at": iso(start + dt.timedelta(minutes=30)),
        "instructor_id": coach.account_id}, format="json")
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "instructor_busy"

    public = ok(api_client.get(f"/api/v1/organizations/{school['slug']}"))
    assert session["id"] in {s["id"] for s in public["upcoming_sessions"]}
    student = register(run_on_commit, "student-f05@example.com", first_name="Лиза", last_name="Ученица")
    booking = ok(student.post("/api/v1/bookings", {"lesson_session_id": session["id"]}, format="json"), 201)
    ok(owner.post(f"/api/v1/bookings/{booking['id']}/confirm", {}, format="json"))
    schedule = results(ok(coach.get("/api/v1/me/schedule")))
    item = next(i for i in schedule if i["id"] == session["id"])
    assert item["seats_taken"] == 1 and item["organization"]["id"] == school["id"]

    _time_passes(session["id"])
    completed = ok(coach.post(f"/api/v1/sessions/{session['id']}/complete", {}, format="json"))  # инструктор
    assert completed["session"]["status"] == "completed" and completed["completed_booking_ids"] == [booking["id"]]
    assert ok(student.get(f"/api/v1/bookings/{booking['id']}"))["status"] == "completed"
    assert AnalyticsEvent.objects.filter(name="session_completed", subject_id=booking["id"]).exists()
    metrics = ok(owner.get("/api/v1/me/metrics", {"scope": "school", "organization_id": school["id"]}))
    values = {m["key"]: m["value"] for m in metrics["metrics"]}
    assert values["sessions_completed"] == 1 and values["unique_students"] == 1 and values["fill_rate"] == 25.0


# --- F06 ------------------------------------------------------------------------------------------------------------

def test_f06_spot_conditions_instructor_on_spot_lesson_and_rental_linked(api_client, run_on_commit, make_client):
    """F06: спот → условия → инструктор на этом споте → занятие → аренда доски → две связанные брони подтверждены."""
    region = RegionFactory()
    spot = SpotFactory(region=region, slug="halaktyr-f06", typical_conditions="Волна 1–2 м, оффшор с утра")
    detail = ok(api_client.get(f"/api/v1/spots/{spot.slug}"))
    assert detail["typical_conditions"] == "Волна 1–2 м, оффшор с утра"  # типичные условия отдельно от прогноза
    assert ok(api_client.get(f"/api/v1/spots/{spot.slug}/forecast"))["provider"] is None  # GEO-04: без провайдера

    coach = register(run_on_commit, "coach-f06@example.com", primary_type="instructor", first_name="Тимур",
                     last_name="Споттов")
    ok(coach.put("/api/v1/me/instructor", {"headline": "Халактыр каждый день", "region_slugs": [region.slug],
                                           "spot_slugs": [spot.slug], "formats": ["individual"], "price_from": "4000"},
                 format="json"))
    ok(coach.post("/api/v1/me/instructor/publish"))
    found = results(ok(api_client.get("/api/v1/instructors", {"spot": spot.slug})))
    assert [c["handle"] for c in found] == [coach.handle]
    offer = ok(coach.post("/api/v1/me/instructor/offers", {"title": "Урок на Халактыре", "price": "4000",
                                                           "format": "individual", "spot_slug": spot.slug},
                          format="json"), 201)
    start = next_hour(40)
    slot = ok(coach.post("/api/v1/me/instructor/sessions", {"offer_id": offer["id"], "starts_at": iso(start)},
                         format="json"), 201)

    renter = AccountFactory()
    board = InventoryItemFactory(owner_account=renter, region=region, spot=spot, title="Софттоп 8'0",
                                 rental_price_per_day=Decimal("2500"))
    rentals = results(ok(api_client.get("/api/v1/rentals", {"spot": spot.slug, "from": iso(start),
                                                            "to": iso(start + dt.timedelta(hours=2))})))
    assert [r["id"] for r in rentals] == [str(board.pk)]

    client = register(run_on_commit, "client-f06@example.com", first_name="Пётр", last_name="Клиент")
    lesson = ok(client.post("/api/v1/bookings", {"lesson_session_id": slot["id"]}, format="json"), 201)
    rental = ok(client.post("/api/v1/bookings", {"inventory_item_id": str(board.pk), "starts_at": iso(start),
                                                 "ends_at": iso(start + dt.timedelta(hours=3)),
                                                 "group_with": lesson["id"]}, format="json"), 201)
    assert [g["id"] for g in ok(client.get(f"/api/v1/bookings/{lesson['id']}"))["group"]] == [rental["id"]]
    ok(coach.post(f"/api/v1/bookings/{lesson['id']}/confirm", {}, format="json"))
    ok(make_client(renter).post(f"/api/v1/bookings/{rental['id']}/confirm", {}, format="json"))
    mine = results(ok(client.get("/api/v1/bookings?box=mine")))
    assert {b["id"]: b["status"] for b in mine} == {lesson["id"]: "confirmed", rental["id"]: "confirmed"}


# --- F07 ------------------------------------------------------------------------------------------------------------

def test_f07_two_clients_race_for_last_board_only_one_confirmed(transactional_db, make_client):
    """F07 (AT-05, ATX-16): два клиента в один интервал на последнюю доску — подтверждается одна бронь.
    Реальные параллельные транзакции (как apps/commerce/tests/test_booking_concurrency.py)."""
    renter = AccountFactory()
    board = InventoryItemFactory(owner_account=renter, rental_price_per_day=Decimal("2500"))
    start = next_hour(50)
    bookings = []
    for _ in range(2):
        client = make_client()
        bookings.append(ok(client.post("/api/v1/bookings", {
            "inventory_item_id": str(board.pk), "starts_at": iso(start), "ends_at": iso(start + dt.timedelta(hours=4)),
        }, format="json"), 201)["id"])

    barrier = threading.Barrier(2)
    codes = []

    def confirm(booking_id):
        try:
            client = make_client(renter)
            barrier.wait(timeout=10)
            response = client.post(f"/api/v1/bookings/{booking_id}/confirm", {}, format="json")
            codes.append((response.status_code, response.json()))
        finally:
            connection.close()

    threads = [threading.Thread(target=confirm, args=(b,)) for b in bookings]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sorted(code for code, _ in codes) == [200, 409], codes
    assert next(body for code, body in codes if code == 409)["error"]["code"] == "resource_taken"
    assert Booking.objects.filter(inventory_item=board, status="confirmed").count() == 1


# --- F08 ------------------------------------------------------------------------------------------------------------

def test_f08_wind_direction_proposal_diff_approve_card_audit_notification(api_client, run_on_commit):
    """F08 (AT-07): правка направления ветра → модератор видит diff → одобряет → карточка, журнал, уведомление."""
    spot = SpotFactory(best_wind_directions=["N", "NW"])
    author = register(run_on_commit, "local-f08@example.com", first_name="Местный", last_name="Житель")
    proposal = ok(author.post(f"/api/v1/spots/{spot.pk}/proposals", {
        "changes": {"best_wind_directions": ["W", "SW"]}, "comment": "Работает при западном", "source": "Наблюдения"},
        format="json"), 201)
    winds = [d["code"] for d in ok(api_client.get(f"/api/v1/spots/{spot.slug}"))["best_wind_directions"]]
    assert winds == ["N", "NW"]  # до approve карточка прежняя

    moderator = moderator_client()
    case = next(c for c in results(ok(moderator.get("/api/v1/moderation/cases?kind=spot_change")))
                if c["target_id"] == proposal["id"])
    target = ok(moderator.get(f"/api/v1/moderation/cases/{case['id']}"))["target"]
    diff = {d["field"]: d for d in target["diff"]}
    assert diff["best_wind_directions"]["old"] == ["N", "NW"]
    assert set(diff["best_wind_directions"]["new"]) == {"W", "SW"}
    ok(moderator.post(f"/api/v1/moderation/proposals/{proposal['id']}/approve", {"comment": "Подтверждено"},
                      format="json"))

    winds = [d["code"] for d in ok(api_client.get(f"/api/v1/spots/{spot.slug}"))["best_wind_directions"]]
    assert set(winds) == {"W", "SW"}
    audit = AuditEvent.objects.get(action="spot.change_approved", object_id=str(spot.pk))
    assert audit.before["best_wind_directions"] == ["N", "NW"] and audit.metadata["proposal_id"] == proposal["id"]
    assert any(n["kind"] == K.MODERATION_DECISION and n["link"] == f"/spots/{spot.slug}" for n in notifications(author))
    audit_api = results(ok(moderator.get(f"/api/v1/moderation/audit?object_id={spot.pk}")))
    assert any(e["action"] == "spot.change_approved" for e in audit_api)


# --- F09 ------------------------------------------------------------------------------------------------------------

def test_f09_four_star_spot_review_with_photo_changes_only_that_spot(api_client, run_on_commit):
    """F09 (AT-08): 4★ споту с фото автора → после модерации среднее и число голосов; соседние споты без изменений."""
    region = RegionFactory()
    spot, neighbour = SpotFactory(region=region), SpotFactory(region=region)
    author = register(run_on_commit, "reviewer-f09@example.com")
    photo = upload_ready(author, run_on_commit, purpose="review_photo")
    review = ok(author.post("/api/v1/reviews", {"target_type": "spot", "target_id": str(spot.pk), "rating": 4,
                                                "text": "Хорошая волна, но людно", "photo_ids": [str(photo.pk)]},
                            format="json"), 201)
    assert ok(api_client.get(f"/api/v1/spots/{spot.slug}"))["rating_count"] == 0
    ok(moderator_client().post(f"/api/v1/moderation/reviews/{review['id']}/approve", {}, format="json"))
    card = ok(api_client.get(f"/api/v1/spots/{spot.slug}"))
    assert Decimal(str(card["rating_avg"])) == Decimal("4") and card["rating_count"] == 1
    other = ok(api_client.get(f"/api/v1/spots/{neighbour.slug}"))
    assert Decimal(str(other["rating_avg"])) == Decimal("0") and other["rating_count"] == 0
    public = results(ok(api_client.get(f"/api/v1/reviews?target_type=spot&target_id={spot.pk}")))
    assert public[0]["rating"] == 4 and [p["id"] for p in public[0]["photos"]] == [str(photo.pk)]


# --- F10 ------------------------------------------------------------------------------------------------------------

def test_f10_variant_size_change_versions_sku_and_keeps_order_snapshot(api_client, run_on_commit):
    """F10: шейпер меняет размеры после заказа → новая версия с новым SKU; заказ хранит ссылку и снимок."""
    region = RegionFactory()
    shaper, workshop, model = _publish_workshop_with_model(run_on_commit, "shaper-f10@example.com", region,
                                                           name="Sizes Lab")
    variant = ok(api_client.get(f"/api/v1/boards/{model['id']}"))["variants"][0]
    client = register(run_on_commit, "client-f10@example.com")
    order = ok(client.post("/api/v1/inquiries", {"kind": "board_purchase", "target_type": "board_variant",
                                                 "target_id": variant["id"], "message": "Беру этот размер"},
                           format="json"), 201)
    changed = ok(shaper.patch(f"/api/v1/models/{model['id']}/variants/{variant['id']}", {"length_in": "72"},
                              format="json"))
    assert changed["versioned"] is True and changed["id"] != variant["id"] and changed["sku"] != variant["sku"]
    assert changed["previous_version_id"] == variant["id"]
    detail = ok(client.get(f"/api/v1/inquiries/{order['id']}"))
    assert detail["snapshot"]["sku"] == variant["sku"]
    inquiry = Inquiry.objects.get(pk=order["id"])
    assert str(inquiry.board_variant_id) == variant["id"]
    old = BoardVariant.objects.get(pk=variant["id"])
    assert old.is_active is False and old.length_in == Decimal("70")
    public = ok(api_client.get(f"/api/v1/boards/{model['id']}"))["variants"]
    assert [v["id"] for v in public] == [changed["id"]]


# --- F11 ------------------------------------------------------------------------------------------------------------

def test_f11_private_lesson_and_school_assignment_conflict_is_409(run_on_commit, make_client):
    """F11 (ATX-15): частный урок и назначение школы на одно время — конфликт 409 в обе стороны."""
    region = RegionFactory()
    coach = register(run_on_commit, "coach-f11@example.com", primary_type="instructor", first_name="Ян",
                     last_name="Занятой")
    ok(coach.put("/api/v1/me/instructor", {"headline": "Частные уроки", "region_slugs": [region.slug],
                                           "formats": ["individual"], "price_from": "4000"}, format="json"))
    ok(coach.post("/api/v1/me/instructor/publish"))
    offer = ok(coach.post("/api/v1/me/instructor/offers", {"title": "Урок", "price": "4000",
                                                           "format": "individual"}, format="json"), 201)
    start = next_hour(28)
    private = ok(coach.post("/api/v1/me/instructor/sessions", {"offer_id": offer["id"], "starts_at": iso(start)},
                            format="json"), 201)
    booking = ok(make_client().post("/api/v1/bookings", {"lesson_session_id": private["id"]}, format="json"), 201)
    ok(coach.post(f"/api/v1/bookings/{booking['id']}/confirm", {}, format="json"))

    owner = register(run_on_commit, "school-f11@example.com", primary_type="school")
    school = ok(owner.post("/api/v1/organizations", {"kind": "school", "name": "Школа F11"}, format="json"), 201)
    ok(run_on_commit(owner.post, f"/api/v1/organizations/{school['id']}/invites",
                     {"email": "coach-f11@example.com", "role": "instructor"}, format="json"), 201)
    ok(coach.post(f"/api/v1/invites/{OrganizationInvite.objects.get(email='coach-f11@example.com').token}/accept",
                  {}, format="json"))
    clash = owner.post(f"/api/v1/organizations/{school['id']}/sessions", {
        "title": "Группа", "starts_at": iso(start + dt.timedelta(minutes=30)), "instructor_id": coach.account_id},
        format="json")
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "instructor_busy"
    # Без инструктора занятие создаётся; назначить занятого инструктора нельзя.
    lesson = ok(owner.post(f"/api/v1/organizations/{school['id']}/sessions", {
        "title": "Группа", "starts_at": iso(start + dt.timedelta(minutes=30))}, format="json"), 201)
    assign = owner.post(f"/api/v1/sessions/{lesson['id']}/assign", {"instructor_id": coach.account_id}, format="json")
    assert assign.status_code == 409 and assign.json()["error"]["code"] == "instructor_busy"
    # И наоборот: новый частный слот поверх школьного урока.
    later = ok(owner.post(f"/api/v1/organizations/{school['id']}/sessions", {
        "title": "Вечер", "starts_at": iso(start + dt.timedelta(hours=6)), "instructor_id": coach.account_id},
        format="json"), 201)
    overlap = coach.post("/api/v1/me/instructor/sessions", {
        "offer_id": offer["id"], "starts_at": iso(start + dt.timedelta(hours=6, minutes=30))}, format="json")
    assert overlap.status_code == 409 and overlap.json()["error"]["code"] == "instructor_busy"
    assert later["id"]


# --- F12 ------------------------------------------------------------------------------------------------------------

def test_f12_gg_surfer_diary_hidden_visibility_birthday_only_with_consent(api_client, run_on_commit):
    """F12 (COM-05, ATX-34): GG Surfer по согласию, дневник, скрытие видимости, поздравление только с согласием."""
    surfer = register(run_on_commit, "gg-f12@example.com", first_name="Кира", last_name="Волна")
    assert api_client.get(f"/api/v1/surfers/{surfer.handle}").status_code == 404  # без согласия анкеты нет
    today = timezone.localdate()
    birthday = today.replace(year=1995) if (today.month, today.day) != (2, 29) else dt.date(1996, 2, 29)
    ok(surfer.patch("/api/v1/me", {"profile": {"birth_date": birthday.isoformat()}}, format="json"))
    ok(surfer.post("/api/v1/me/consents", {"kind": "gg_surfer", "granted": True}, format="json"), 201)
    card = ok(api_client.get(f"/api/v1/surfers/{surfer.handle}"))
    assert "birth_date" not in card and card.get("age") is None  # возраст только при gg_show_age

    spot = SpotFactory()
    entry = ok(surfer.post("/api/v1/me/diary", {"spot_id": str(spot.pk), "date": today.isoformat(),
                                                "duration_min": 90, "visibility": "public"}, format="json"), 201)
    assert ok(api_client.get(f"/api/v1/surfers/{surfer.handle}/diary"))["count"] == 1
    ok(surfer.patch(f"/api/v1/me/diary/{entry['id']}", {"visibility": "private"}, format="json"))
    assert ok(api_client.get(f"/api/v1/surfers/{surfer.handle}/diary"))["count"] == 0
    assert ok(api_client.get(f"/api/v1/surfers/{surfer.handle}"))["diary"]["ride_days"] == 0
    assert ok(surfer.get("/api/v1/me/diary/stats"))["ride_days"] == 1

    assert send_birthday_greetings(today.isoformat()) == 0  # согласия на поздравления нет
    ok(surfer.post("/api/v1/me/consents", {"kind": "birthday_greetings", "granted": True}, format="json"), 201)
    if (today.month, today.day) != (2, 29):
        assert send_birthday_greetings(today.isoformat()) == 1
        greeting = notifications(surfer, K.BIRTHDAY)
        assert len(greeting) == 1 and str(birthday.year) not in greeting[0]["body"]
        assert BirthdayGreeting.objects.filter(account_id=surfer.account_id).exists()


# --- F13 ------------------------------------------------------------------------------------------------------------

def test_f13_cancel_booking_releases_resource_notifies_parties_and_counts_in_stats(run_on_commit, make_client):
    """F13: клиент отменяет бронь → ресурс свободен, исполнитель уведомлён, событие в аналитике и статистике."""
    renter = AccountFactory()
    from apps.accounts.models import Specialty
    from tests.factories import add_specialty

    add_specialty(renter, Specialty.RENTAL)
    board = InventoryItemFactory(owner_account=renter, rental_price_per_day=Decimal("2500"))
    provider = make_client(renter)
    start = next_hour(60)
    window = {"inventory_item_id": str(board.pk), "starts_at": iso(start), "ends_at": iso(start + dt.timedelta(hours=4))}
    client = register(run_on_commit, "client-f13@example.com")
    booking = ok(client.post("/api/v1/bookings", window, format="json"), 201)
    second = make_client()
    waiting = ok(second.post("/api/v1/bookings", window, format="json"), 201)  # ещё не подтверждено — можно
    ok(provider.post(f"/api/v1/bookings/{booking['id']}/confirm", {}, format="json"))
    taken = provider.post(f"/api/v1/bookings/{waiting['id']}/confirm", {}, format="json")
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "resource_taken"
    assert make_client().post("/api/v1/bookings", window, format="json").status_code == 409  # интервал занят

    cancelled = ok(client.post(f"/api/v1/bookings/{booking['id']}/cancel", {"reason": "Заболел"}, format="json"))
    assert cancelled["status"] == "cancelled" and cancelled["cancelled_side"] == "customer"
    provider_notes = [n for n in notifications(provider, K.BOOKING_STATUS) if n["link"].endswith(booking["id"])]
    assert provider_notes and "Заболел" in provider_notes[0]["body"]
    event = AnalyticsEvent.objects.get(name="booking_cancelled", subject_id=booking["id"])
    assert event.context["side"] == "customer" and event.context["reason"] == "Заболел"
    # Ресурс освобождён: вторую бронь на тот же интервал теперь можно подтвердить.
    ok(provider.post(f"/api/v1/bookings/{waiting['id']}/confirm", {}, format="json"))
    assert any(n["kind"] == K.BOOKING_STATUS for n in notifications(second))
    period = {"scope": "rental", "from": timezone.localdate().isoformat(),
              "to": (timezone.localdate() + dt.timedelta(days=7)).isoformat()}
    metrics = {m["key"]: m["value"] for m in ok(provider.get("/api/v1/me/metrics", period))["metrics"]}
    assert metrics["cancellation_share"] == 50.0  # 1 отмена из 2 броней с началом в периоде


# --- F14 ------------------------------------------------------------------------------------------------------------

def test_f14_complaint_hides_listing_with_reason_and_audit(api_client, run_on_commit, make_client):
    """F14 (TRUST-07): жалоба → модератор скрывает объявление, причина и действие в журнале, автору — решение."""
    owner = AccountFactory()
    listing = InventoryItemFactory(owner_account=owner, title="Подозрительно дешёвая доска")
    assert str(listing.pk) in {r["id"] for r in results(ok(api_client.get("/api/v1/rentals")))}
    reporter = register(run_on_commit, "reporter-f14@example.com")
    complaint = ok(reporter.post("/api/v1/complaints", {"target_type": "inventory_item", "target_id": str(listing.pk),
                                                        "reason": "fraud", "text": "Просят предоплату на карту"},
                                 format="json"), 201)
    moderator = moderator_client()
    case = next(c for c in results(ok(moderator.get("/api/v1/moderation/cases?kind=complaint")))
                if c["target_id"] == complaint["id"])
    ok(moderator.post(f"/api/v1/moderation/complaints/{complaint['id']}/resolve",
                      {"action": "hidden", "note": "Мошенническое объявление"}, format="json"))
    assert str(listing.pk) not in {r["id"] for r in results(ok(api_client.get("/api/v1/rentals")))}
    assert api_client.get(f"/api/v1/rentals/{listing.pk}").status_code == 404
    audit = AuditEvent.objects.get(action="complaint.resolved", object_id=complaint["id"])
    assert audit.metadata["action"] == "hidden" and audit.metadata["note"] == "Мошенническое объявление"
    assert audit.before == {"is_published": True} and audit.after == {"is_published": False}
    assert ok(moderator.get(f"/api/v1/moderation/cases/{case['id']}"))["status"]["code"] == "resolved"
    assert any(n["kind"] == K.COMPLAINT for n in notifications(reporter))
    owner_notes = Notification.objects.filter(recipient=owner, kind=K.MODERATION_DECISION)
    assert owner_notes.exists() and owner_notes.first().payload["can_appeal"] is True


# --- F15 ------------------------------------------------------------------------------------------------------------

def test_f15_revoked_manager_loses_school_management_history_kept(run_on_commit, make_client):
    """F15 (AT-09, ATX-18): школа снимает права менеджера → управление недоступно сразу; занятия и журнал целы."""
    owner = register(run_on_commit, "school-f15@example.com", primary_type="school")
    school = ok(owner.post("/api/v1/organizations", {"kind": "school", "name": "Школа F15"}, format="json"), 201)
    manager = register(run_on_commit, "manager-f15@example.com", first_name="Макс", last_name="Менеджер")
    ok(run_on_commit(owner.post, f"/api/v1/organizations/{school['id']}/invites",
                     {"email": "manager-f15@example.com", "role": "manager"}, format="json"), 201)
    ok(manager.post(f"/api/v1/invites/{OrganizationInvite.objects.get(email='manager-f15@example.com').token}/accept",
                    {}, format="json"))
    program = ok(manager.post(f"/api/v1/organizations/{school['id']}/programs", {"title": "Группа", "price": "3000"},
                              format="json"), 201)
    session = ok(manager.post(f"/api/v1/organizations/{school['id']}/sessions", {
        "program_id": program["id"], "starts_at": iso(next_hour(30))}, format="json"), 201)
    assert ok(manager.get(f"/api/v1/organizations/{school['id']}/manage"))["id"] == school["id"]

    membership = Membership.objects.get(organization_id=school["id"], account_id=manager.account_id)
    revoked = owner.delete(f"/api/v1/organizations/{school['id']}/members/{membership.pk}")
    assert revoked.status_code in (200, 204)
    assert any(n["kind"] == K.MEMBERSHIP for n in notifications(manager))

    for response in (manager.get(f"/api/v1/organizations/{school['id']}/manage"),
                     manager.patch(f"/api/v1/organizations/{school['id']}/manage", {"name": "Чужая"}, format="json"),
                     manager.post(f"/api/v1/organizations/{school['id']}/programs", {"title": "X", "price": "1"},
                                  format="json"),
                     manager.get(f"/api/v1/organizations/{school['id']}/sessions"),
                     manager.post(f"/api/v1/sessions/{session['id']}/cancel", {"reason": "x"}, format="json")):
        assert response.status_code in (403, 404), (response.wsgi_request.path, response.status_code)
    assert school["id"] not in {m["organization"]["id"] for m in ok(manager.get("/api/v1/me/organizations"))}
    # История на месте: занятие, программа и журнал действий менеджера.
    assert LessonSession.objects.filter(pk=session["id"], status="scheduled").exists()
    sessions = results(ok(owner.get(f"/api/v1/organizations/{school['id']}/sessions")))
    assert session["id"] in {s["id"] for s in sessions}
    assert AuditEvent.objects.filter(actor_id=manager.account_id, action="lesson_session.created").exists()
    assert AuditEvent.objects.filter(action="membership.revoked", object_id=str(membership.pk)).exists()
    team = ok(owner.get(f"/api/v1/organizations/{school['id']}/members"))
    assert manager.account_id not in {m["account"]["id"] for m in results(team)}
    history = ok(owner.get(f"/api/v1/organizations/{school['id']}/members?status=all"))
    assert {"revoked"} == {m["status"] for m in results(history) if m["account"]["id"] == manager.account_id}


# --- AT-10 ----------------------------------------------------------------------------------------------------------

def test_at10_account_deletion_keeps_records_releases_resources_and_hides_personal_data(api_client, run_on_commit,
                                                                                         make_client):
    """AT-10: удаление аккаунта сохраняет заказы/переписку/журналы, но освобождает занятые ресурсы (брони,
    места на событиях) и убирает личные материалы (дневник с фото) из публичного доступа."""
    from apps.accounts.models import AccountDeletionRequest
    from apps.accounts.tasks import process_deletion_requests
    from apps.club.models import EventRegistration
    from apps.club.tests.factories import ClubEventFactory
    from apps.community.models import SurfSession

    renter = AccountFactory()
    board = InventoryItemFactory(owner_account=renter, rental_price_per_day=Decimal("2500"))
    provider = make_client(renter)
    leaving = register(run_on_commit, "leaving-at10@example.com", first_name="Уходящий", last_name="Клиент")
    start = next_hour(72)
    window = {"inventory_item_id": str(board.pk), "starts_at": iso(start), "ends_at": iso(start + dt.timedelta(hours=4))}
    booking = ok(leaving.post("/api/v1/bookings", window, format="json"), 201)
    ok(provider.post(f"/api/v1/bookings/{booking['id']}/confirm", {}, format="json"))
    inquiry = ok(leaving.post("/api/v1/inquiries", {"kind": "rental", "target_type": "inventory_item",
                                                    "target_id": str(board.pk), "message": "Можно с плавниками?"},
                              format="json"), 201)
    event = ClubEventFactory(capacity=1)
    ok(leaving.post(f"/api/v1/club/events/{event.pk}/registration", {}, format="json"), 201)
    waiting = make_client()
    waiting.post(f"/api/v1/club/events/{event.pk}/registration", {}, format="json")
    ok(leaving.post("/api/v1/me/consents", {"kind": "gg_surfer", "granted": True}, format="json"), 201)
    photo = upload_ready(leaving, run_on_commit, purpose="diary_photo")
    ok(leaving.post("/api/v1/me/diary", {"spot_name": "Бухта", "date": timezone.localdate().isoformat(),
                                         "visibility": "public", "photo_ids": [str(photo.pk)]}, format="json"), 201)
    assert ok(api_client.get(f"/api/v1/media/{photo.pk}/url"))["url"]

    ok(leaving.post("/api/v1/me/deletion", {}, format="json"), 202)
    AccountDeletionRequest.objects.update(scheduled_for=timezone.now() - dt.timedelta(minutes=1))
    assert run_on_commit(process_deletion_requests) == 1

    # Записи сохранены и видны второй стороне (без личных данных).
    detail = ok(provider.get(f"/api/v1/inquiries/{inquiry['id']}"))
    assert detail["counterpart"]["name"] == "Удалённый пользователь" and detail["counterpart"]["url"] is None
    cancelled = ok(provider.get(f"/api/v1/bookings/{booking['id']}"))
    assert cancelled["status"] == "cancelled" and cancelled["cancelled_side"] == "system"
    assert any(n["kind"] == K.BOOKING_STATUS and n["link"].endswith(booking["id"]) for n in notifications(provider))
    # Ресурсы освобождены: интервал аренды и место на событии.
    assert ok(make_client().post("/api/v1/bookings", window, format="json"), 201)["status"] == "requested"
    assert EventRegistration.objects.get(event=event, account_id=waiting.account.pk).status == "registered"
    # Личные материалы недоступны.
    assert not SurfSession.objects.filter(account_id=leaving.account_id).exists()
    assert api_client.get(f"/api/v1/media/{photo.pk}/url").status_code == 404
    from apps.mediafiles.storage import get_storage

    assert get_storage().head(photo.storage_key) is None
