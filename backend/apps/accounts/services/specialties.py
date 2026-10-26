"""Подключаемые направления (7.1, BR-02, BR-11, ACC-12): один account.id, история не удаляется."""
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Specialty, StaffRole, UserSpecialty
from apps.common.exceptions import DomainError, Forbidden, NotFound

SCHOOL = "school"


def has_specialty(account, code):
    if not account or not account.is_authenticated:
        return False
    return UserSpecialty.objects.filter(account=account, specialty_id=code, status=UserSpecialty.Status.ACTIVE).exists()


def require_specialty(account, code, message=None):
    if not has_specialty(account, code):
        raise Forbidden(message or "Подключите направление в разделе «Мои направления».", code="specialty_required")


def active_codes(account):
    return list(UserSpecialty.objects.filter(account=account, status=UserSpecialty.Status.ACTIVE)
                .order_by("specialty__sort_order").values_list("specialty_id", flat=True))


def _resolve(code):
    code = (code or "").strip().lower()
    if code in StaffRole.Role.values:
        raise Forbidden("Роли модератора и администратора назначаются только администрацией платформы.",
                        code="staff_role_not_toggleable")
    if code == SCHOOL:
        raise DomainError(
            "school_is_organization",
            "Сёрф-школа подключается как организация: создайте школу в разделе «Организации» "
            "или примите приглашение от владельца школы.",
        )
    specialty = Specialty.objects.filter(code=code).first()
    if specialty is None:
        raise NotFound("Направление не найдено.")
    return specialty


def grant_specialty(account, code, *, primary=False):
    """Создать или активировать направление без аудита (используется при регистрации)."""
    obj, created = UserSpecialty.objects.get_or_create(
        account=account, specialty_id=code, defaults={"is_primary": primary, "status": UserSpecialty.Status.ACTIVE}
    )
    if not created:
        changed = []
        if obj.status != UserSpecialty.Status.ACTIVE:
            obj.status, obj.activated_at, obj.disabled_at = UserSpecialty.Status.ACTIVE, timezone.now(), None
            changed += ["status", "activated_at", "disabled_at"]
        if primary and not obj.is_primary:
            obj.is_primary = True
            changed.append("is_primary")
        if changed:
            obj.save(update_fields=changed + ["updated_at"])
    return obj


def _next_step(account, code):
    if code == Specialty.INSTRUCTOR:
        from apps.learning.models import InstructorProfile

        profile = InstructorProfile.objects.filter(account=account).first()
        if profile is None or profile.status != InstructorProfile.Status.PUBLISHED:
            return "instructor_profile"
    if code == Specialty.SHAPER:
        from apps.organizations.models import Membership, Organization

        has_workshop = Membership.objects.filter(
            account=account, status=Membership.Status.ACTIVE, organization__kind=Organization.Kind.WORKSHOP
        ).exists()
        if not has_workshop:
            return "create_workshop"
    return None


def activate_specialty(account, code, request=None):
    from apps.trust.services.audit import record

    specialty = _resolve(code)
    with transaction.atomic():
        existing = UserSpecialty.objects.select_for_update().filter(account=account, specialty=specialty).first()
        was_active = existing is not None and existing.status == UserSpecialty.Status.ACTIVE
        obj = grant_specialty(account, specialty.code)
        if not was_active:
            record(account, "specialty.activated", obj, after={"code": specialty.code}, request=request)
    return obj, _next_step(account, specialty.code)


# --- отключение -----------------------------------------------------------------------------------------------

def _warning(code, message, count=None):
    return {"code": code, "message": message, "count": count}


def _instructor_warnings(account, unpublish):
    from apps.commerce.models import Booking, Inquiry
    from apps.learning.models import InstructorProfile, LessonSession

    warnings, unpublished = [], []
    profile = InstructorProfile.objects.filter(account=account).first()
    if profile is not None and profile.status == InstructorProfile.Status.PUBLISHED:
        if unpublish:
            profile.status = InstructorProfile.Status.HIDDEN
            profile.save(update_fields=["status", "updated_at"])
            unpublished.append({"type": "instructor_profile", "id": str(profile.id)})
            warnings.append(_warning("instructor_profile_hidden",
                                     "Публичная карточка инструктора скрыта. Её можно снова опубликовать."))
        else:
            warnings.append(_warning(
                "instructor_profile_published",
                "Карточка инструктора остаётся опубликованной. Скройте её, если не принимаете новые заявки."))
    bookings = Booking.objects.filter(
        provider_account=account, kind=Booking.Kind.LESSON,
        status__in=[Booking.Status.REQUESTED, Booking.Status.CONFIRMED, Booking.Status.IN_PROGRESS],
    ).count()
    if bookings:
        warnings.append(_warning("active_bookings",
                                 f"Активные бронирования занятий: {bookings}. Они сохраняются — завершите или "
                                 "отмените их в разделе «Бронирования».", bookings))
    inquiries = Inquiry.objects.filter(
        provider_account=account, status__in=[Inquiry.Status.NEW, Inquiry.Status.IN_PROGRESS],
        kind__in=[Inquiry.Kind.LESSON, Inquiry.Kind.GENERAL],
    ).count()
    if inquiries:
        warnings.append(_warning("open_inquiries",
                                 f"Открытые обращения: {inquiries}. Переписка и история сохраняются.", inquiries))
    sessions = LessonSession.objects.filter(
        instructor=account, status=LessonSession.Status.SCHEDULED, starts_at__gt=timezone.now()
    ).count()
    if sessions:
        warnings.append(_warning("upcoming_sessions",
                                 f"Назначенные занятия: {sessions}. Они остаются в расписании школ.", sessions))
    return warnings, unpublished


def _shaper_warnings(account):
    from apps.boards.models import BoardModel
    from apps.commerce.models import Inquiry
    from apps.organizations.models import Membership, Organization

    warnings = []
    workshop_ids = list(Membership.objects.filter(
        account=account, status=Membership.Status.ACTIVE, role__in=[Membership.Role.OWNER, Membership.Role.MANAGER],
        organization__kind=Organization.Kind.WORKSHOP,
    ).values_list("organization_id", flat=True))
    published = Organization.objects.filter(id__in=workshop_ids, status=Organization.Status.PUBLISHED)
    for org in published:
        warnings.append(_warning("workshop_published",
                                 f"Мастерская «{org.name}» остаётся опубликованной. Скрыть её можно в кабинете "
                                 "мастерской; модели и заказы сохраняются."))
    models_count = BoardModel.objects.filter(workshop_id__in=workshop_ids, status=BoardModel.Status.PUBLISHED).count()
    if models_count:
        warnings.append(_warning("published_board_models",
                                 f"Опубликованные модели досок: {models_count}.", models_count))
    shaper_kinds = [Inquiry.Kind.BOARD_PURCHASE, Inquiry.Kind.CUSTOM_ORDER, Inquiry.Kind.REPAIR]
    open_statuses = [Inquiry.Status.NEW, Inquiry.Status.IN_PROGRESS]
    inquiries = (
        Inquiry.objects.filter(provider_organization_id__in=workshop_ids, status__in=open_statuses).count()
        + Inquiry.objects.filter(provider_account=account, kind__in=shaper_kinds, status__in=open_statuses).count()
    )
    if inquiries:
        warnings.append(_warning("open_inquiries",
                                 f"Открытые заявки и заказы: {inquiries}. История и переписка сохраняются.",
                                 inquiries))
    return warnings


def _rental_warnings(account):
    from apps.commerce.models import Booking, Inquiry
    from apps.inventory.models import InventoryItem

    warnings = []
    items = InventoryItem.objects.filter(owner_account=account, is_published=True).exclude(
        status__in=[InventoryItem.Status.RETIRED, InventoryItem.Status.SOLD]).count()
    if items:
        warnings.append(_warning("published_inventory",
                                 f"Опубликованные объявления проката: {items}. Снимите их с публикации в разделе "
                                 "«Инвентарь», если больше не сдаёте снаряжение.", items))
    bookings = Booking.objects.filter(
        provider_account=account, kind=Booking.Kind.RENTAL,
        status__in=[Booking.Status.REQUESTED, Booking.Status.CONFIRMED, Booking.Status.IN_PROGRESS],
    ).count()
    if bookings:
        warnings.append(_warning("active_bookings",
                                 f"Активные бронирования аренды: {bookings}. Они сохраняются.", bookings))
    inquiries = Inquiry.objects.filter(
        provider_account=account, kind=Inquiry.Kind.RENTAL, status__in=[Inquiry.Status.NEW, Inquiry.Status.IN_PROGRESS]
    ).count()
    if inquiries:
        warnings.append(_warning("open_inquiries", f"Открытые обращения по аренде: {inquiries}.", inquiries))
    return warnings


def deactivate_specialty(account, code, *, unpublish=False, request=None):
    """Отключает направление: инструменты скрываются, история/заказы/документы остаются (BR-11, ATX-17)."""
    from apps.trust.services.audit import record

    specialty = _resolve(code)
    if specialty.code == Specialty.SURFER:
        raise DomainError("surfer_required",
                          "Профиль сёрфера — основа аккаунта и не отключается. Скрыть себя из GG Surfer можно "
                          "в настройках приватности.")
    with transaction.atomic():
        obj = UserSpecialty.objects.select_for_update().filter(account=account, specialty=specialty).first()
        if obj is None:
            raise NotFound("Направление не подключено.")
        unpublished = []
        if specialty.code == Specialty.INSTRUCTOR:
            warnings, unpublished = _instructor_warnings(account, unpublish)
        elif specialty.code == Specialty.SHAPER:
            warnings = _shaper_warnings(account)
        elif specialty.code == Specialty.RENTAL:
            warnings = _rental_warnings(account)
        else:
            warnings = []
        if obj.status == UserSpecialty.Status.ACTIVE:
            was_primary = obj.is_primary
            obj.status, obj.disabled_at, obj.is_primary = UserSpecialty.Status.DISABLED, timezone.now(), False
            obj.save(update_fields=["status", "disabled_at", "is_primary", "updated_at"])
            if was_primary and not UserSpecialty.objects.filter(
                    account=account, status=UserSpecialty.Status.ACTIVE, is_primary=True).exists():
                UserSpecialty.objects.filter(account=account, specialty_id=Specialty.SURFER).update(is_primary=True)
            record(account, "specialty.disabled", obj, before={"code": specialty.code, "status": "active"},
                   after={"code": specialty.code, "status": "disabled"},
                   metadata={"unpublished": unpublished, "warnings": [w["code"] for w in warnings]}, request=request)
    return obj, warnings, unpublished
