"""Построение демо-данных (docs/DEMO_DATA.md, ARCHITECTURE.md §8) и их удаление для --reset.

Никогда не создаёт отзывы, обращения, сообщения, уведомления, события аналитики, проверенные сертификаты и
статистику (TZ 12.2, PL-02, ATX-33). Все созданные записи помечены is_demo=True (где у модели есть такое поле)
или принадлежат демо-аккаунтам.
"""
import datetime as dt
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.hashers import make_password
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import ProtectedError, Q, RestrictedError
from django.utils import timezone

from apps.accounts.models import Account, ConsentRecord, StaffRole, UserProfile, UserSpecialty
from apps.boards.models import BoardMedia, BoardModel, BoardType, BoardVariant, Material, WorkshopProfile
from apps.club.models import ClubAnnouncement, ClubEvent
from apps.common.text import slugify_ru
from apps.community.models import SurfSession
from apps.demo import data as D
from apps.demo.assets import AssetSpec, save_media_assets
from apps.favorites.models import Favorite
from apps.inventory.models import InventoryItem, InventoryItemPhoto
from apps.learning.models import InstructorOffer, InstructorProfile, LessonSession, SchoolProgram
from apps.mediafiles.models import MediaAsset
from apps.organizations.models import Membership, Organization
from apps.shop.models import Product, ProductVariant
from apps.spots.models import Region, Spot, SpotPhoto, SpotSourceRecord

P = MediaAsset.Purpose
SESSION_GAP = dt.timedelta(minutes=30)  # запас между занятиями одного инструктора (дорога между спотами)
SCHOOL_CLOSED_WEEKDAYS = {0}  # школа не работает по понедельникам


def demo_email(local):
    return f"{local}@{D.EMAIL_DOMAIN}"


def has_field(model, name):
    try:
        model._meta.get_field(name)
    except FieldDoesNotExist:
        return False
    return True


def demo_flag(model):
    """{"is_demo": True}, если у модели есть такое поле (часть моделей других приложений его пока не имеет)."""
    return {"is_demo": True} if has_field(model, "is_demo") else {}


def money(value):
    return Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def round_price(value):
    return money(Decimal(value) / 100) * 100


def years_word(n):
    if n % 10 == 1 and n % 100 != 11:
        return "год"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "года"
    return "лет"


def feet_text(length_in):
    feet, inches = divmod(int(length_in), 12)
    return f"{feet}′{inches}″"


def demo_present():
    return Spot.objects.filter(is_demo=True).exists()


def any_demo_data():
    return demo_present() or Account.objects.filter(is_demo=True).exists()


# --- План изображений -----------------------------------------------------------------------------------------------

def _board_media_keys(workshop_slug, model_name):
    slug = slugify_ru(model_name)
    return f"boards/{workshop_slug}/{slug}-1.png", f"boards/{workshop_slug}/{slug}-2.png"


def asset_plan():
    """Все файлы, которые нужны посеву. У каждого использования — свой storage_key, чтобы удаление фото в одном
    объекте (через API) не ломало другой."""
    specs = []
    for spot in D.SPOTS:
        for filename, _caption, alt in spot["photos"]:
            specs.append(AssetSpec(f"spots/{filename}", f"spots/{filename}", P.SPOT_PHOTO, alt))
    for person in D.INSTRUCTORS:
        name = f"{person['first_name']} {person['last_name']}"
        specs.append(AssetSpec(f"avatars/{person['avatar']}", f"avatars/{person['avatar']}", P.AVATAR, name))
    for shaper in D.SHAPERS:
        for m in shaper["models"]:
            type_code = D.SHAPER_TYPE_CODES[m["type"]]
            cover, render = _board_media_keys(shaper["slug"], m["name"])
            specs.append(AssetSpec(cover, f"boards/silhouette-{type_code}.png", P.BOARD_PHOTO, f"{m['name']} — силуэт"))
            specs.append(AssetSpec(render, f"boards/{m['render']}", P.BOARD_PHOTO, f"{m['name']} — доска"))
            if D.AVAILABILITY[m["status"]] == "in_stock":
                specs.append(AssetSpec(f"inventory/{shaper['slug']}-{slugify_ru(m['name'])}.png",
                                       f"boards/silhouette-{type_code}.png", P.ITEM_PHOTO, m["name"]))
    for item in D.RENTAL["items"]:
        specs.append(AssetSpec(f"rentals/rental-{item[1]}.png", f"rentals/rental-{item[1]}.png", P.ITEM_PHOTO, item[2]))
    for event in D.CLUB_EVENTS:
        cover = event[10]
        specs.append(AssetSpec(f"club/{event[0]}.{cover.rsplit('.', 1)[1]}", f"ui/{cover}", P.EVENT_COVER, event[1]))
    for org in (D.SCHOOL, D.RENTAL):
        specs.append(AssetSpec(f"orgs/{org['slug']}-cover.webp", f"ui/{org['cover']}", P.ORG_COVER, org["name"]))
    return specs


# --- Удаление (--reset) ---------------------------------------------------------------------------------------------

def _force_delete(queryset, counter, depth=0):
    """Удаляет queryset; если мешают PROTECT/RESTRICT-ссылки (это зависимые от демо записи: брони, обращения и т. п.,
    созданные при ручной проверке), сначала удаляет их. Посевные MediaAsset не трогаем."""
    if depth > 8:
        raise CommandError(f"Слишком глубокая цепочка зависимостей при удалении {queryset.model.__name__}")
    for _attempt in range(10):
        try:
            with transaction.atomic():
                _total, per_model = queryset.delete()
        except ProtectedError as exc:
            blockers = exc.protected_objects
        except RestrictedError as exc:
            blockers = exc.restricted_objects
        else:
            counter.update({label: n for label, n in per_model.items() if n})
            return
        groups = defaultdict(set)
        for obj in blockers:
            groups[obj._meta.model].add(obj.pk)
        for model, pks in groups.items():
            _force_delete(model._base_manager.filter(pk__in=pks), counter, depth + 1)
    raise CommandError(f"Не удалось удалить {queryset.model.__name__}: зависимости не разрешаются")


def reset_demo_data():
    """Удаляет демо-записи и их зависимые объекты в порядке зависимостей. Вызывать внутри transaction.atomic()."""
    from apps.analytics.models import AnalyticsEvent
    from apps.commerce.models import Booking, Inquiry
    from apps.messaging.models import Conversation, ConversationParticipant
    from apps.trust.models import Review

    counter = Counter()
    accounts = list(Account.objects.filter(is_demo=True).values_list("pk", flat=True))
    orgs = list(Organization.objects.filter(Q(is_demo=True) | Q(owner_id__in=accounts)).values_list("pk", flat=True))
    sessions = LessonSession.objects.filter(
        Q(instructor_id__in=accounts) | Q(organization_id__in=orgs) | Q(offer__instructor__account_id__in=accounts)
    )
    items = InventoryItem.objects.filter(
        Q(is_demo=True) | Q(owner_account_id__in=accounts) | Q(owner_organization_id__in=orgs)
    )
    board_models = BoardModel.objects.filter(Q(is_demo=True) | Q(workshop_id__in=orgs))
    steps = [
        Booking.objects.filter(
            Q(customer_id__in=accounts) | Q(provider_account_id__in=accounts) | Q(provider_organization_id__in=orgs)
            | Q(lesson_session__in=sessions.values("pk")) | Q(inventory_item__in=items.values("pk"))
        ),
        Inquiry.objects.filter(
            Q(customer_id__in=accounts) | Q(provider_account_id__in=accounts) | Q(provider_organization_id__in=orgs)
        ),
        Conversation.objects.filter(
            pk__in=ConversationParticipant.objects.filter(account_id__in=accounts).values("conversation_id")
        ),
        Review.objects.filter(author_id__in=accounts),
        LessonSession.objects.filter(pk__in=list(sessions.values_list("pk", flat=True))),
        InventoryItem.objects.filter(pk__in=list(items.values_list("pk", flat=True))),
        BoardVariant.objects.filter(model__in=list(board_models.values_list("pk", flat=True))),
        BoardModel.objects.filter(pk__in=list(board_models.values_list("pk", flat=True))),
        ClubEvent.objects.filter(Q(is_demo=True) | Q(organizer_id__in=accounts)),
        ClubAnnouncement.objects.filter(
            Q(author_id__in=accounts) | (Q(is_demo=True) if has_field(ClubAnnouncement, "is_demo") else Q(pk__in=[]))
        ),
        Product.objects.filter(
            Q(is_demo=True) if has_field(Product, "is_demo") else Q(slug__in=[p["slug"] for p in D.PRODUCTS])
        ),
        AnalyticsEvent.objects.filter(
            Q(actor_id__in=accounts) | Q(owner_account_id__in=accounts) | Q(owner_organization_id__in=orgs)
        ),
        Organization.objects.filter(pk__in=orgs),
        Spot.objects.filter(is_demo=True),
        Account.objects.filter(pk__in=accounts),
    ]
    for queryset in steps:
        _force_delete(queryset, counter)
    return counter


# --- Посев ------------------------------------------------------------------------------------------------------------

class DemoSeeder:
    def __init__(self, now=None):
        self.now = now or timezone.now()
        self.password_hash = make_password(D.PASSWORD)
        self.regions = {}
        self.spots = {}
        self.accounts = {}  # handle -> Account
        self.instructor_profiles = {}  # handle -> InstructorProfile
        self.offers = defaultdict(list)  # handle -> [InstructorOffer]
        self.workshops = {}  # slug -> Organization
        self.board_models = {}  # (workshop slug, model name) -> BoardModel
        self.rental_items = {}  # prototypeId -> InventoryItem
        self.busy = defaultdict(list)  # account pk -> [(start, end)]
        self.media = {}

    # -- общие помощники --
    def _local(self, tz_name, day, hhmm):
        hours, minutes = (int(x) for x in hhmm.split(":"))
        return dt.datetime.combine(day, dt.time(hours, minutes), tzinfo=ZoneInfo(tz_name))

    def _today(self, tz_name):
        return self.now.astimezone(ZoneInfo(tz_name)).date()

    def _media(self, key, owner=None, organization=None):
        asset = self.media[key]
        if asset.owner_id != getattr(owner, "pk", None) or asset.organization_id != getattr(organization, "pk", None):
            asset.owner, asset.organization = owner, organization
            asset.save(update_fields=["owner", "organization", "updated_at"])
        return asset

    def _account(self, spec, *, specialties=("surfer",), primary="surfer", region=None, avatar=None, **profile):
        email = demo_email(spec["email"])
        account = Account.objects.filter(email=email).first()
        if account is not None and not account.is_demo:
            raise CommandError(f"{email} уже занят обычным (не демо) аккаунтом — посев остановлен")
        account = account or Account(email=email)
        account.password = self.password_hash
        account.is_demo = True
        account.is_active = True
        account.email_verified_at = account.email_verified_at or self.now
        account.save()
        favorite_spots = profile.pop("favorite_spots", [])
        gg_status = profile.pop("gg_status", None)
        user_profile, _ = UserProfile.objects.update_or_create(
            account=account,
            defaults={"handle": spec["handle"], "first_name": spec["first_name"], "last_name": spec["last_name"],
                      "region": self.regions.get(region), "languages": ["ru"], **profile},
        )
        if gg_status and has_field(UserProfile, "gg_status"):
            user_profile.gg_status = gg_status
            user_profile.save(update_fields=["gg_status"])
        if avatar:
            user_profile.avatar = self._media(avatar, owner=account)
            user_profile.save(update_fields=["avatar"])
        user_profile.favorite_spots.set([self.spots[s] for s in favorite_spots])
        for code in specialties:
            UserSpecialty.objects.update_or_create(
                account=account, specialty_id=code,
                defaults={"status": UserSpecialty.Status.ACTIVE, "is_primary": code == primary, "disabled_at": None},
            )
        kinds = [ConsentRecord.Kind.TERMS, ConsentRecord.Kind.PRIVACY]
        if profile.get("gg_surfer_enabled"):
            kinds.append(ConsentRecord.Kind.GG_SURFER)
        if profile.get("birthday_greetings_consent"):
            kinds.append(ConsentRecord.Kind.BIRTHDAY)
        for kind in kinds:
            if not ConsentRecord.objects.filter(account=account, kind=kind, granted=True).exists():
                ConsentRecord.objects.create(account=account, kind=kind, granted=True, user_agent="seed_demo")
        self.accounts[spec["handle"]] = account
        return account

    def _organization(self, kind, slug, name, owner, **fields):
        org = Organization.objects.create(
            kind=kind, slug=slug, name=name, owner=owner, status=Organization.Status.PUBLISHED,
            published_at=self.now, is_demo=True, **fields,
        )
        Membership.objects.create(organization=org, account=owner, role=Membership.Role.OWNER, title="Владелец")
        return org

    def _is_free(self, account, start, end):
        return all(end + SESSION_GAP <= s or start >= e + SESSION_GAP for s, e in self.busy[account.pk])

    def _session(self, *, instructor, start, minutes, **fields):
        end = start + dt.timedelta(minutes=minutes)
        if instructor is not None:
            if not self._is_free(instructor, start, end):
                return None
            self.busy[instructor.pk].append((start, end))
        return LessonSession.objects.create(
            instructor=instructor, starts_at=start, ends_at=end, status=LessonSession.Status.SCHEDULED, **fields
        )

    # -- справочники и споты --
    def seed_regions(self):
        for order, (slug, name, tz_name, lat, lng, zoom) in enumerate(D.REGIONS, start=1):
            region, _ = Region.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "timezone": tz_name, "center_lat": Decimal(lat), "center_lng": Decimal(lng),
                          "map_zoom": zoom, "sort_order": order},
            )
            self.regions[slug] = region

    def seed_spots(self):
        for spec in D.SPOTS:
            existing = Spot.objects.filter(slug=spec["slug"]).first()
            if existing is not None and not existing.is_demo:
                raise CommandError(f"Спот {spec['slug']} уже есть как обычная запись — посев остановлен")
            conditions = (f"Ветер: {spec['wind_text']}. Свелл: {spec['swell_text']}. "
                          f"Волна: {spec['wave_character'].lower()}. Дно: {spec['bottom_text']}.")
            description = (f"{spec['short_description']}\n\n"
                           f"Особенности места: {', '.join(spec['nature']).lower().capitalize()}.")
            spot, _ = Spot.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"], "region": self.regions[spec["region"]], "status": Spot.Status.PUBLISHED,
                    "lat": Decimal(spec["lat"]), "lng": Decimal(spec["lng"]), "location_precision": spec["precision"],
                    "is_sensitive": False, "short_description": spec["short_description"][:300],
                    "description": description, "difficulty": spec["difficulty"], "bottom_type": spec["bottom_type"],
                    "break_type": spec["break_type"], "wave_character": spec["wave_character"],
                    "season": spec["season"], "best_months": D.SEASON_MONTHS[spec["season"]],
                    "best_wind_directions": spec["wind"], "best_swell_directions": spec["swell"],
                    "typical_conditions": conditions, "hazards": spec["hazards"],
                    "hazard_notes": spec["hazard_notes"], "entry_exit": spec["entry_exit"], "access": spec["access"],
                    "infrastructure": [{"type": t, "name": n, "distance_m": None} for t, n in spec["infrastructure"]],
                    "data_source": D.DATA_SOURCE, "last_confirmed_at": self.now,
                    # BR-08: демо-оценки прототипа не переносятся, рейтинг считается только по реальным отзывам
                    "rating_avg": 0, "rating_count": 0, "is_demo": True,
                },
            )
            spot.photos.all().delete()
            for position, (filename, caption, _alt) in enumerate(spec["photos"]):
                SpotPhoto.objects.create(spot=spot, media=self._media(f"spots/{filename}"), position=position,
                                         caption=caption)
            spot.cover = self.media[f"spots/{spec['photos'][0][0]}"]
            spot.save(update_fields=["cover", "updated_at"])
            spot.sources.all().delete()
            SpotSourceRecord.objects.create(spot=spot, source=D.DATA_SOURCE, note=D.DATA_STATUS_NOTE,
                                            confirmed_at=self.now)
            self.spots[spec["slug"]] = spot

    # -- люди --
    def seed_surfer(self):
        spec = D.SURFER
        surfer = self._account(
            spec, region=spec["region"], city=spec["city"], bio=spec["bio"], riding_level=spec["riding_level"],
            surfing_since=self.now.year - spec["experience_years"], preferred_board_types=spec["board_types"],
            interests=spec["interests"], favorite_spots=spec["favorite_spots"], gg_surfer_enabled=True,
        )
        today = self._today("Asia/Kamchatka")
        for days_ago, spot_slug, minutes, board, conditions, wave, mood, notes, visibility in D.DIARY:
            spot = self.spots[spot_slug]
            SurfSession.objects.create(
                account=surfer, spot=spot, spot_name=spot.name, date=today - dt.timedelta(days=days_ago),
                duration_min=minutes, board_note=board, conditions=conditions, wave_height_m=Decimal(wave),
                mood_rating=mood, notes=notes, visibility=visibility,
            )
        return surfer

    def seed_instructors(self):
        for spec in D.INSTRUCTORS:
            spec = {**spec, "email": spec["handle"].replace("-", ".")}
            exp = spec["experience_years"]
            spots = [self.spots[s] for s in spec["spot_slugs"]]
            account = self._account(
                spec, specialties=("surfer", "instructor"), primary="instructor", region=spec["region"],
                avatar=f"avatars/{spec['avatar']}", city=spec["city"],
                bio=f"Сёрф-инструктор, {exp} {years_word(exp)} в сёрфинге. Катаюсь: {', '.join(spec['spots_text'])}.",
                fun_facts=[spec["fact"]], surfing_since=self.now.year - exp, riding_level=spec["riding_level"],
                preferred_board_types=spec["board_types"], interests=spec["interests"],
                favorite_spots=spec["favorite_spots"], gg_surfer_enabled=spec["gg"], gg_status=spec["gg_status"],
                gg_contact_policy=UserProfile.ContactPolicy.EVERYONE, gg_show_region=True,
                gg_show_age=spec.get("gg_show_age", False),
                birth_date=dt.date.fromisoformat(spec["birth_date"]) if spec.get("birth_date") else None,
                birthday_greetings_consent=spec.get("birthday_greetings_consent", False),
            )
            profile = InstructorProfile.objects.create(
                account=account, status=InstructorProfile.Status.PUBLISHED,
                headline=f"Сёрф-инструктор · {spec['city']}",
                about=(f"Стаж в сёрфинге — {exp} {years_word(exp)}. Провожу занятия на спотах: "
                       f"{', '.join(spec['spots_text'])}. Ученики: {spec['students_text'].lower()}. "
                       f"Доска и гидрокостюм — по договорённости, перенос по погоде бесплатно."),
                # в прототипе одно число «опыт N лет» — им заполняем и стаж катания, и стаж преподавания
                fun_facts=[spec["fact"]], surfing_since=self.now.year - exp, teaching_since=self.now.year - exp,
                riding_level=spec["riding_level"], formats=["individual", "pair", "group"],
                student_levels=spec["student_levels"],
                board_types=spec["board_types"], languages=["ru"], price_from=money(spec["price_from"]),
                contact_note=D.LESSON_PRICE_NOTE, published_at=self.now, is_demo=True,
                # сертификаты прототипа («✓ сертификат · демо») не переносятся — статус «не указан» (BR-07, PL-02)
            )
            profile.regions.set([self.regions[spec["region"]]])
            profile.spots.set(spots)
            level = "" if len(spec["student_levels"]) > 2 else spec["student_levels"][0]
            for kind in spec["offers"]:
                tpl = D.OFFER_TEMPLATES[kind]
                self.offers[spec["handle"]].append(InstructorOffer.objects.create(
                    instructor=profile, title=tpl["title"], description=tpl["text"], format=tpl["format"],
                    level=level, duration_min=90, price=round_price(spec["price_from"] * tpl["price_factor"]),
                    capacity=tpl["capacity"], spot=spots[0], equipment_included=True,
                    equipment_note="Доска и гидрокостюм по размеру",
                    rules="Перенос по погоде — бесплатно. Отмена позднее чем за 12 часов — по договорённости.",
                ))
            self.instructor_profiles[spec["handle"]] = profile

    def seed_staff(self):
        moderator = self._account(D.MODERATOR)
        admin = self._account(D.ADMIN)
        Account.objects.filter(pk=moderator.pk).update(totp_secret=D.TOTP_SECRET, totp_enabled=True)
        Account.objects.filter(pk=admin.pk).update(
            totp_secret=D.TOTP_SECRET, totp_enabled=True, is_staff=True, is_superuser=True
        )
        for account, roles in ((moderator, [StaffRole.Role.MODERATOR]),
                               (admin, [StaffRole.Role.ADMIN, StaffRole.Role.ORGANIZER])):
            for role in roles:
                StaffRole.objects.get_or_create(account=account, role=role, revoked_at=None)
        admin.refresh_from_db()
        return admin

    # -- мастерские и доски --
    def _material(self, org, name):
        return (Material.objects.filter(workshop=None, name=name).first()
                or Material.objects.get_or_create(workshop=org, name=name)[0])

    def _sku(self, shaper_code, board_type, variant, serial):
        """Артикул сервисом boards (BRD-05); без него — {КОД}-{ТИП}-{ДЛИНА}-{ШИРИНА}."""
        try:
            from apps.boards.services import sku as sku_service

            return sku_service.build_sku(
                shaper_code=shaper_code, type_code=sku_service.board_type_sku_code(board_type),
                length_in=variant.length_in, width_in=variant.width_in, serial=serial, suffix=variant.sku_suffix,
                version=variant.version,
            )
        except (ImportError, AttributeError, TypeError):
            feet, inches = divmod(int(variant.length_in), 12)
            type_code = (getattr(board_type, "sku_code", "") or board_type.code[:3]).upper()
            return f"{shaper_code}-{type_code}-{feet}P{inches}-W{int(variant.width_in * 100)}"

    def seed_shapers(self):
        for spec in D.SHAPERS:
            region = self.regions[spec["region"]]
            if isinstance(spec["owner"], str):
                owner = self.accounts[spec["owner"]]
                UserSpecialty.objects.update_or_create(
                    account=owner, specialty_id="shaper",
                    defaults={"status": UserSpecialty.Status.ACTIVE, "is_primary": False, "disabled_at": None},
                )
            else:
                owner = self._account(spec["owner"], specialties=("surfer", "shaper"), primary="shaper",
                                      region=spec["region"])
            prices = [m["price"] for m in spec["models"]]
            delivery = ", ".join(spec["delivery"]).lower()
            org = self._organization(
                Organization.Kind.WORKSHOP, spec["slug"], spec["workshop"], owner, region=region,
                short_description=spec["about"][:300], description=f"{spec['about']}\n\nДоставка: {delivery}.",
                price_from=money(min(prices)),
            )
            services = (["Индивидуальные заказы"] if spec["custom_orders"] else []) + \
                       (["Ремонт досок"] if spec["repair"] else []) + (["Аренда"] if spec["rental"] else [])
            WorkshopProfile.objects.create(
                organization=org, shaper_code=spec["shaper_code"], specialization=", ".join(spec["specialization"]),
                services=services or ["Создание моделей досок"], lead_time=spec["lead_time"],
                does_repair=spec["repair"],
                repair_note="Принимаю доски на ремонт и восстановление" if spec["repair"] else "",
                experience_since=self.now.year - spec["experience_years"] if spec["experience_years"] else None,
            )
            materials = [self._material(org, name) for name in spec["materials"]]
            for code, name, silhouette in spec["custom_types"]:
                extra = {}
                if has_field(BoardType, "sku_code"):
                    try:
                        from apps.boards.services.sku import custom_type_sku_code
                        extra["sku_code"] = custom_type_sku_code(name)
                    except ImportError:
                        extra["sku_code"] = "X" + code[:3].upper()
                BoardType.objects.create(workshop=org, code=code, name=name, silhouette=silhouette, sort_order=200,
                                         **extra)
            for serial, m in enumerate(spec["models"], start=1):
                self._board_model(spec, org, owner, region, materials, serial, m)
            self.workshops[spec["slug"]] = org

    def _board_model(self, spec, org, owner, region, materials, serial, m):
        board_type = BoardType.objects.get(workshop=None, code=D.SHAPER_TYPE_CODES[m["type"]])
        model = BoardModel.objects.create(
            workshop=org, name=m["name"], slug=slugify_ru(m["name"]), board_type=board_type,
            status=BoardModel.Status.PUBLISHED, published_at=self.now, is_demo=True,
            **({"serial": serial} if has_field(BoardModel, "serial") else {}),
        )
        availability = D.AVAILABILITY[m["status"]]
        variant = BoardVariant(
            model=model, length_in=Decimal(m["length"]), width_in=Decimal(m["width"]),
            thickness_in=Decimal(m["thickness"]) if m["thickness"] else None, volume_l=Decimal(m["volume"]),
            material=materials[0], price=money(m["price"]), availability=availability,
            made_to_order_days=spec.get("lead_days") if availability == "made_to_order" else None,
        )
        variant.sku = self._sku(spec["shaper_code"], board_type, variant, serial)
        variant.save()
        cover_key, render_key = _board_media_keys(spec["slug"], m["name"])
        BoardMedia.objects.create(model=model, media=self._media(cover_key, owner, org), position=0, is_cover=True)
        BoardMedia.objects.create(model=model, media=self._media(render_key, owner, org), position=1)
        self.board_models[(spec["slug"], m["name"])] = model
        if availability == "in_stock":
            item = InventoryItem.objects.create(
                owner_organization=org, variant=variant,
                kind=InventoryItem.Kind.SUP if board_type.code == "sup" else InventoryItem.Kind.BOARD,
                purpose=InventoryItem.Purpose.SALE, status=InventoryItem.Status.AVAILABLE,
                title=f"{m['name']} {feet_text(m['length'])}", description=spec["about"],
                size=f"{feet_text(m['length'])} · {m['volume']} л", condition=InventoryItem.Condition.NEW,
                region=region, pickup_location=f"Мастерская {spec['workshop']} · самовывоз",
                sale_price=money(m["price"]), serial_number=f"DEMO-{spec['shaper_code']}-{serial:03d}",
                is_published=True, is_demo=True,
            )
            key = f"inventory/{spec['slug']}-{slugify_ru(m['name'])}.png"
            InventoryItemPhoto.objects.create(item=item, media=self._media(key, owner, org), position=0)

    # -- школа --
    def seed_school(self):
        spec = D.SCHOOL
        owner = self._account(spec["owner"], region=spec["region"], city=spec["city"])
        manager = self._account(spec["manager"], region=spec["region"], city=spec["city"])
        programs_spec = spec["programs"]
        school = self._organization(
            Organization.Kind.SCHOOL, spec["slug"], spec["name"], owner, region=self.regions[spec["region"]],
            city=spec["city"], short_description=spec["short_description"], description=spec["description"],
            email=demo_email(spec["owner"]["email"]), formats=["group", "individual"], languages=["ru"],
            price_from=money(min(p[7] for p in programs_spec)),
        )
        school.cover = self._media(f"orgs/{spec['slug']}-cover.webp", owner, school)
        school.save(update_fields=["cover", "updated_at"])
        school.spots.set([self.spots[s] for s in spec["spots"]])
        Membership.objects.create(organization=school, account=manager, role=Membership.Role.MANAGER,
                                  title="Менеджер школы", invited_by=owner)
        for handle in spec["instructors"]:
            Membership.objects.create(organization=school, account=self.accounts[handle],
                                      role=Membership.Role.INSTRUCTOR, title="Инструктор", invited_by=owner)
        programs = []
        for title, description, level, age, fmt, minutes, count, price, size in programs_spec:
            programs.append(SchoolProgram.objects.create(
                organization=school, title=title, description=description, level=level, age_category=age,
                format=fmt, duration_min=minutes, sessions_count=count, price=money(price), max_group_size=size,
                equipment_included=True,
            ))
        self.school, self.school_owner, self.school_programs = school, owner, programs

    # -- прокат --
    def seed_rental(self):
        spec = D.RENTAL
        owner = self._account(spec["owner"], specialties=("surfer", "rental"), primary="rental", region=spec["region"],
                              city=spec["city"])
        org = self._organization(
            Organization.Kind.RENTAL, spec["slug"], spec["name"], owner, region=self.regions[spec["region"]],
            city=spec["city"], short_description=spec["short_description"], description=spec["description"],
        )
        org.cover = self._media(f"orgs/{spec['slug']}-cover.webp", owner, org)
        org.save(update_fields=["cover", "updated_at"])
        spots = set()
        for proto_id, slug, title, kind, region, town, size, price, handed_by, info in spec["items"]:
            spot = self.spots[spec["region_spots"][region]]
            spots.add(spot)
            item = InventoryItem.objects.create(
                owner_organization=org, kind=kind, purpose=InventoryItem.Purpose.RENTAL,
                status=InventoryItem.Status.AVAILABLE, title=title, description=info, size=size,
                condition=InventoryItem.Condition.GOOD, region=self.regions[region], spot=spot,
                pickup_location=f"{town} · выдаёт {handed_by}", available_hours="По договорённости",
                rental_price_per_day=money(price), min_rental_hours=24, serial_number=f"DEMO-{proto_id.upper()}",
                is_published=True, is_demo=True,
            )
            InventoryItemPhoto.objects.create(item=item, media=self._media(f"rentals/rental-{slug}.png", owner, org),
                                              position=0)
            self.rental_items[proto_id] = item
        org.spots.set(spots)

    # -- расписание (14 дней вперёд) --
    def seed_schedule(self):
        # Частные слоты инструкторов: стандартные 09:00/12:00/15:00 прототипа, Пн и Чт — выходные.
        for idx, spec in enumerate(D.INSTRUCTORS):
            account = self.accounts[spec["handle"]]
            offers = self.offers[spec["handle"]]
            tz_name = offers[0].spot.region.timezone
            today = self._today(tz_name)
            created = 0
            for day_offset in range(1, 15):
                day = today + dt.timedelta(days=day_offset)
                if day.weekday() in D.CLOSED_WEEKDAYS or (day_offset + idx) % 2:
                    continue
                offer = offers[created % len(offers)]
                start = self._local(tz_name, day, D.LESSON_SLOTS[(day_offset + idx) % len(D.LESSON_SLOTS)])
                if self._session(instructor=account, start=start, minutes=offer.duration_min, offer=offer,
                                 spot=offer.spot, title=offer.title, capacity=offer.capacity, price=offer.price,
                                 created_by=account):
                    created += 1
        # Занятия школы: назначены двум инструкторам команды, время подбирается без пересечений с их слотами.
        school, programs = self.school, self.school_programs
        instructors = [self.accounts[h] for h in D.SCHOOL["instructors"]]
        school_spots = [self.spots[s] for s in D.SCHOOL["spots"]]
        tz_name = school.region.timezone
        today = self._today(tz_name)
        k = 0
        for day_offset in range(1, 15):
            day = today + dt.timedelta(days=day_offset)
            if day.weekday() in SCHOOL_CLOSED_WEEKDAYS:
                continue
            program, instructor = programs[k % len(programs)], instructors[k % len(instructors)]
            for hhmm in D.SCHOOL["session_times"]:
                if self._session(
                    instructor=instructor, start=self._local(tz_name, day, hhmm), minutes=program.duration_min,
                    organization=school, program=program, spot=school_spots[k % len(school_spots)],
                    title=program.title, capacity=program.max_group_size,
                    price=program.price if program.sessions_count == 1 else None, created_by=self.school_owner,
                ):
                    break
            k += 1
        # Одно занятие без инструктора — чтобы проверить назначение (SCH-05/06).
        program = programs[0]
        self._session(
            instructor=None, start=self._local(tz_name, today + dt.timedelta(days=5), "18:00"),
            minutes=program.duration_min, organization=school, program=program, spot=school_spots[0],
            title=program.title, capacity=program.max_group_size, price=program.price, created_by=self.school_owner,
            notes="Инструктор ещё не назначен.",
        )

    # -- клуб и магазин --
    def seed_club(self, admin):
        for (slug, title, kind, region, spot, days, hhmm, hours, capacity, place, cover, workshop,
             text) in D.CLUB_EVENTS:
            region_obj = self.regions[region]
            start = self._local(region_obj.timezone, self._today(region_obj.timezone) + dt.timedelta(days=days), hhmm)
            ClubEvent.objects.create(
                slug=slug, title=title, kind=kind, status=ClubEvent.Status.PUBLISHED, description=text,
                spot=self.spots.get(spot), region=region_obj, location_note=place, starts_at=start,
                ends_at=start + dt.timedelta(hours=hours), capacity=capacity, registration_open=True,
                organizer=admin, organizer_organization=self.workshops.get(workshop),
                cover=self._media(f"club/{slug}.{cover.rsplit('.', 1)[1]}", owner=admin), is_demo=True,
            )
        for title, body, pinned, days_ago in D.CLUB_ANNOUNCEMENTS:
            ClubAnnouncement.objects.create(
                title=title, body=body, author=admin, is_pinned=pinned,
                published_at=self.now - dt.timedelta(days=days_ago), **demo_flag(ClubAnnouncement),
            )

    def seed_shop(self):
        extra = demo_flag(Product)
        for spec in D.PRODUCTS:
            defaults = {"title": spec["title"], "category": spec["category"], "status": Product.Status.PREORDER,
                        "description": spec["description"], "specs": spec["specs"], "cover": None,
                        "delivery_note": D.PRODUCT_DELIVERY_NOTE, "returns_note": D.PRODUCT_RETURNS_NOTE, **extra}
            if has_field(Product, "sort_order"):
                defaults["sort_order"] = spec["sort_order"]
            product, _ = Product.objects.update_or_create(slug=spec["slug"], defaults=defaults)
            for position, (sku, name, price) in enumerate(spec["variants"]):
                variant_defaults = {"product": product, "name": name, "price": money(price), "stock": 0}
                if has_field(ProductVariant, "sort_order"):
                    variant_defaults["sort_order"] = position
                ProductVariant.objects.update_or_create(sku=sku, defaults=variant_defaults)

    def seed_favorites(self, surfer):
        F = Favorite.Target
        rows = [
            {"target_type": F.SPOT, "spot": self.spots["khalaktyrskiy-plyazh"]},
            {"target_type": F.INSTRUCTOR, "instructor": self.instructor_profiles["aleksey-morozov"]},
            {"target_type": F.ORGANIZATION, "organization": self.school},
            {"target_type": F.BOARD_MODEL, "board_model": self.board_models[("kamchatka-boards", "Kamchatka Classic")]},
            {"target_type": F.INVENTORY_ITEM, "inventory_item": self.rental_items["r1"]},
        ]
        for row in rows:
            Favorite.objects.create(account=surfer, **row)

    # -- точка входа --
    def build(self, specs, prepared):
        """Создаёт все демо-записи. Вызывать внутри transaction.atomic(); S3 уже заполнен."""
        self.media = save_media_assets(specs, prepared)
        self.seed_regions()
        self.seed_spots()
        surfer = self.seed_surfer()
        self.seed_instructors()
        admin = self.seed_staff()
        self.seed_shapers()
        self.seed_school()
        self.seed_rental()
        self.seed_schedule()
        self.seed_club(admin)
        self.seed_shop()
        self.seed_favorites(surfer)
        return summary_counts()


def summary_counts():
    demo_accounts = Account.objects.filter(is_demo=True)
    demo_orgs = Organization.objects.filter(is_demo=True)
    return {
        "Регионы": Region.objects.filter(slug__in=[r[0] for r in D.REGIONS]).count(),
        "Споты": Spot.objects.filter(is_demo=True).count(),
        "Фото спотов": SpotPhoto.objects.filter(spot__is_demo=True).count(),
        "Медиафайлы (seed)": MediaAsset.objects.filter(is_demo=True, storage_key__startswith="public/seed/").count(),
        "Аккаунты": demo_accounts.count(),
        "Профили инструкторов": InstructorProfile.objects.filter(is_demo=True).count(),
        "Предложения инструкторов": InstructorOffer.objects.filter(instructor__is_demo=True).count(),
        "Участники GG Surfer": UserProfile.objects.filter(account__is_demo=True, gg_surfer_enabled=True).count(),
        "Записи дневника": SurfSession.objects.filter(account__in=demo_accounts).count(),
        "Организации": demo_orgs.count(),
        "Программы школы": SchoolProgram.objects.filter(organization__in=demo_orgs).count(),
        "Частные слоты": LessonSession.objects.filter(offer__instructor__is_demo=True).count(),
        "Занятия школы": LessonSession.objects.filter(organization__in=demo_orgs).count(),
        "Модели досок": BoardModel.objects.filter(is_demo=True).count(),
        "Варианты досок": BoardVariant.objects.filter(model__is_demo=True).count(),
        "Инвентарь: продажа": InventoryItem.objects.filter(is_demo=True, purpose=InventoryItem.Purpose.SALE).count(),
        "Инвентарь: аренда": InventoryItem.objects.filter(is_demo=True, purpose=InventoryItem.Purpose.RENTAL).count(),
        "События клуба": ClubEvent.objects.filter(is_demo=True).count(),
        "Анонсы клуба": ClubAnnouncement.objects.filter(author__in=demo_accounts).count(),
        "Товары": Product.objects.filter(slug__in=[p["slug"] for p in D.PRODUCTS]).count(),
        "Избранное": Favorite.objects.filter(account__in=demo_accounts).count(),
    }


DEMO_LOGINS = [
    ("surfer", "сёрфер, GG Surfer, дневник, избранное"),
    ("aleksey.morozov", "инструктор (Камчатка), команда Kamchatka Surf School"),
    ("ivan.petrov", "инструктор + шейпер (Kamchatka Boards), команда школы"),
    ("mariya.volkova", "инструктор (Ладога)"),
    ("dmitriy.kovalev", "инструктор (Крым)"),
    ("ekaterina.sokolova", "инструктор (Сахалин)"),
    ("anna.lebedeva", "инструктор (Крым), без GG Surfer"),
    ("andrey.volkov", "шейпер — Volna Craft"),
    ("evgeniya.sergeeva", "шейпер — Baltic Surf Lab"),
    ("mikhail.kim", "шейпер — Сахалинские доски"),
    ("school", "владелец Kamchatka Surf School"),
    ("manager", "менеджер Kamchatka Surf School"),
    ("rental", "прокат «Волна рядом»"),
    ("moderator", f"модератор, TOTP {D.TOTP_SECRET}"),
    ("admin", f"администратор + организатор клуба, TOTP {D.TOTP_SECRET}"),
]
