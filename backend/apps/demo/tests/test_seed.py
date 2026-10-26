"""seed_demo: состав демо-данных, идемпотентность, --reset, отсутствие «реальных» записей из демо (PL-02, ATX-33)."""
import datetime as dt
import io
import zoneinfo
from collections import defaultdict

import pytest
from botocore.exceptions import ClientError
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Account, StaffRole
from apps.boards.models import BoardModel, BoardVariant
from apps.club.models import ClubAnnouncement, ClubEvent
from apps.commerce.models import Booking, Inquiry
from apps.demo.seeding import asset_plan
from apps.inventory.models import InventoryItem
from apps.learning.models import InstructorCertificate, InstructorOffer, InstructorProfile, LessonSession
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import Conversation, Message, Notification
from apps.organizations.models import Membership, Organization
from apps.shop.models import Product
from apps.spots.models import Region, Spot
from apps.trust.models import Review
from tests.factories import AccountFactory

pytestmark = pytest.mark.django_db

DEMO_ACCOUNTS = 15  # сёрфер + 6 инструкторов + 3 шейпера + владелец и менеджер школы + прокат + модератор + админ


class FakeS3:
    """Запоминает put_object; head_object отвечает 404 для неизвестных ключей (как MinIO)."""

    def __init__(self):
        self.objects = {}
        self.puts = []

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        obj = self.objects[Key]
        return {"ContentLength": len(obj["Body"]), "ContentType": obj["ContentType"], "Metadata": obj["Metadata"]}

    def put_object(self, **kwargs):
        self.puts.append(kwargs["Key"])
        self.objects[kwargs["Key"]] = kwargs
        return {}


@pytest.fixture
def fake_s3(monkeypatch):
    import apps.common.s3

    fake = FakeS3()
    monkeypatch.setattr(apps.common.s3, "internal_client", lambda: fake)
    return fake


def seed(*args):
    out = io.StringIO()
    call_command("seed_demo", *args, stdout=out, stderr=out)
    return out.getvalue()


def snapshot():
    return {
        "spots": Spot.objects.filter(is_demo=True).count(),
        "accounts": Account.objects.filter(is_demo=True).count(),
        "orgs": Organization.objects.filter(is_demo=True).count(),
        "sessions": LessonSession.objects.count(),
        "models": BoardModel.objects.filter(is_demo=True).count(),
        "items": InventoryItem.objects.filter(is_demo=True).count(),
        "events": ClubEvent.objects.filter(is_demo=True).count(),
        "media": MediaAsset.objects.filter(is_demo=True).count(),
    }


def assert_no_overlaps():
    by_instructor = defaultdict(list)
    for s in LessonSession.objects.filter(instructor__isnull=False, status=LessonSession.Status.SCHEDULED):
        by_instructor[s.instructor_id].append((s.starts_at, s.ends_at))
    assert by_instructor
    for intervals in by_instructor.values():
        intervals.sort()
        for (_s1, e1), (s2, _e2) in zip(intervals, intervals[1:]):
            assert e1 <= s2


def test_seed_creates_demo_dataset(fake_s3):
    output = seed()
    assert "демо-данные загружены" in output
    assert "surfer@demo.gdevolna.local" in output

    # справочники и споты
    assert Region.objects.get(slug="kamchatskiy-kray").timezone == "Asia/Kamchatka"
    assert Region.objects.get(slug="kaliningradskaya-oblast").timezone == "Europe/Kaliningrad"
    spots = Spot.objects.filter(is_demo=True)
    assert spots.count() == 6
    for spot in spots:
        assert spot.cover is not None and spot.photos.exists()
        assert spot.rating_count == 0 and spot.rating_avg == 0  # BR-08: демо-оценки не переносятся
        assert spot.data_source == "Прототип ГДеволна v14 (посевные данные)" and spot.last_confirmed_at
    english = Spot.objects.get(slug="zaliv-anglichanka")
    assert english.best_wind_directions == ["NW"] and english.best_swell_directions == ["SE"]
    assert english.difficulty == "beginner" and english.hazards == ["rocks"]

    # изображения: S3 + MediaAsset + миниатюры, без фото с брендами MAERSK
    specs = asset_plan()
    assert MediaAsset.objects.filter(is_demo=True, status="ready", visibility="public").count() == len(specs)
    assert len(fake_s3.puts) == 2 * len(specs)
    assert all(key.startswith("public/seed/") for key in fake_s3.puts)
    assert sum(key.endswith(".thumb.webp") for key in fake_s3.puts) == len(specs)
    assert not any("sakhalina-1" in key for key in fake_s3.puts)
    asset = MediaAsset.objects.get(storage_key="public/seed/spots/spot-khalaktyrskiy-plyazh-1.webp")
    assert (asset.width, asset.height, asset.content_type) == (1280, 854, "image/webp")
    assert asset.thumbnail_key == asset.storage_key + ".thumb.webp"

    # аккаунты и роли
    assert Account.objects.filter(is_demo=True).count() == DEMO_ACCOUNTS
    assert not Account.objects.filter(is_demo=True, email_verified_at__isnull=True).exists()
    surfer = Account.objects.get(email="surfer@demo.gdevolna.local")
    assert surfer.check_password("Demo-2026!") and surfer.profile.gg_surfer_enabled
    assert surfer.surf_sessions.count() >= 3 and surfer.favorites.count() == 5
    moderator = Account.objects.get(email="moderator@demo.gdevolna.local")
    assert moderator.totp_enabled and moderator.totp_secret == "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
    assert moderator.staff_roles.filter(role=StaffRole.Role.MODERATOR).exists()
    admin = Account.objects.get(email="admin@demo.gdevolna.local")
    assert admin.is_superuser and admin.is_staff and admin.totp_enabled
    assert set(admin.staff_roles.values_list("role", flat=True)) == {"admin", "organizer"}

    # инструкторы: опубликованы, без сертификатов, 1–2 предложения
    assert InstructorProfile.objects.filter(is_demo=True, status="published").count() == 6
    assert InstructorCertificate.objects.count() == 0
    for profile in InstructorProfile.objects.filter(is_demo=True):
        assert 1 <= profile.offers.count() <= 2 and profile.certificate_status == "none"
        assert profile.rating_count == 0
    ivan = Account.objects.get(email="ivan.petrov@demo.gdevolna.local")
    assert set(ivan.specialties.values_list("specialty_id", flat=True)) == {"surfer", "instructor", "shaper"}

    # организации
    school = Organization.objects.get(slug="kamchatka-surf-school", kind="school", status="published")
    assert school.programs.count() == 4
    roles = dict(school.memberships.values_list("account__email", "role"))
    assert roles["school@demo.gdevolna.local"] == "owner" and roles["manager@demo.gdevolna.local"] == "manager"
    assert sorted(r for r in roles.values() if r == "instructor") == ["instructor", "instructor"]
    assert Organization.objects.filter(is_demo=True, kind="workshop", status="published").count() == 4
    rental = Organization.objects.get(slug="prokat-volna-ryadom", kind="rental")
    assert rental.inventory_items.filter(purpose="rental").count() == 8
    assert not rental.inventory_items.filter(photos__isnull=True).exists()

    # доски: серверный формат артикула, модели опубликованы, экземпляры для «в наличии»
    assert BoardModel.objects.filter(is_demo=True, status="published").count() == 9
    sku = BoardVariant.objects.get(model__name="Kamchatka Classic").sku
    assert "KBA01-LNG-9P2-W2200" in sku
    in_stock = BoardVariant.objects.filter(model__is_demo=True, availability="in_stock")
    assert InventoryItem.objects.filter(purpose="sale", variant__in=in_stock).count() == in_stock.count() == 5

    # расписание: частные слоты через предложения + занятия школы, в пределах 14 дней, без пересечений
    now = timezone.now()
    private = LessonSession.objects.filter(offer__isnull=False)
    school_sessions = LessonSession.objects.filter(organization=school)
    assert private.count() >= 6 * 3 and school_sessions.count() >= 10
    for session in private:
        assert session.instructor_id == session.offer.instructor.account_id
        local = session.starts_at.astimezone(zoneinfo.ZoneInfo(session.spot.region.timezone))
        assert local.strftime("%H:%M") in {"09:00", "12:00", "15:00"} and local.weekday() not in (0, 3)
    team = set(school.memberships.filter(role="instructor", status="active").values_list("account_id", flat=True))
    assert {s.instructor_id for s in school_sessions if s.instructor_id} == team
    assert LessonSession.objects.filter(status="scheduled").count() == LessonSession.objects.count()
    assert all(now < s.starts_at < now + dt.timedelta(days=15) for s in LessonSession.objects.all())
    assert_no_overlaps()

    # клуб и магазин
    events = ClubEvent.objects.filter(is_demo=True, status="published")
    assert events.count() == 5 and all(e.organizer == admin for e in events)
    assert all(now + dt.timedelta(days=6) < e.starts_at < now + dt.timedelta(weeks=6) for e in events)
    assert ClubAnnouncement.objects.filter(author=admin).count() == 4
    products = Product.objects.filter(slug__startswith="termos-gdevolna")
    assert products.count() == 2 and set(products.values_list("status", flat=True)) == {"preorder"}
    assert not Product.objects.filter(cover__isnull=False).exists()

    # демо-отзывы, обращения, сообщения, уведомления, аналитика — не создаются (TZ 12.2, PL-02, ATX-33)
    from apps.analytics.models import AnalyticsEvent

    for model in (Review, Inquiry, Conversation, Message, Notification, AnalyticsEvent, Booking):
        assert model.objects.count() == 0, model.__name__


def test_if_empty_is_noop_on_second_run(fake_s3):
    seed()
    before = snapshot()
    ids = set(Account.objects.filter(is_demo=True).values_list("pk", flat=True))
    puts = len(fake_s3.puts)

    output = seed("--if-empty")

    assert "пропускаю" in output
    assert snapshot() == before
    assert set(Account.objects.filter(is_demo=True).values_list("pk", flat=True)) == ids
    assert len(fake_s3.puts) == puts  # S3 не трогаем
    # запуск без флагов при существующих данных тоже ничего не меняет
    assert "--reset" in seed()
    assert snapshot() == before


def test_reset_recreates_data_and_reuses_assets(fake_s3):
    seed()
    before = snapshot()
    media_ids = dict(MediaAsset.objects.filter(is_demo=True).values_list("storage_key", "pk"))
    old_surfer = Account.objects.get(email="surfer@demo.gdevolna.local").pk
    # бронь обычного пользователя на демо-занятие — зависимая запись (PROTECT), должна удалиться вместе с демо
    session = LessonSession.objects.filter(organization__slug="kamchatka-surf-school").first()
    customer = AccountFactory()
    Booking.objects.create(kind="lesson", customer=customer, provider_organization=session.organization,
                           lesson_session=session, starts_at=session.starts_at, ends_at=session.ends_at)
    puts = len(fake_s3.puts)

    output = seed("--reset")

    assert "удалено записей" in output
    assert snapshot() == before
    assert Account.objects.get(email="surfer@demo.gdevolna.local").pk != old_surfer
    assert dict(MediaAsset.objects.filter(is_demo=True).values_list("storage_key", "pk")) == media_ids
    assert len(fake_s3.puts) == puts  # те же файлы — без повторной загрузки
    assert Booking.objects.count() == 0
    assert Account.objects.filter(pk=customer.pk).exists()  # обычный аккаунт не тронут
    assert Membership.objects.filter(account__is_demo=False).count() == 0
    assert_no_overlaps()
    assert InstructorOffer.objects.filter(instructor__account__email="anna.lebedeva@demo.gdevolna.local").count() == 1


def test_if_empty_does_not_crash_startup_on_storage_error(monkeypatch):
    import apps.common.s3

    class BrokenS3(FakeS3):
        def put_object(self, **kwargs):
            raise ClientError({"Error": {"Code": "500", "Message": "boom"}}, "PutObject")

    monkeypatch.setattr(apps.common.s3, "internal_client", lambda: BrokenS3())
    output = seed("--if-empty")
    assert "не загружены" in output
    assert not Spot.objects.filter(is_demo=True).exists()
