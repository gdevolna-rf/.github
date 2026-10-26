"""Мастерская шейпера = Organization(kind=workshop) + WorkshopProfile (SHP-01..05, 7.1).

Публикация мастерской (решение для M1, см. отчёт): владелец/менеджер с подтверждённым email публикует сам, если
заполнены название, регион и специализация; модерация организаций (organizations/{id}/submit → trust) остаётся
дополнительным путём. Ограниченную модератором (suspended) мастерскую самостоятельно опубликовать нельзя.
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Specialty
from apps.accounts.services.specialties import require_specialty
from apps.accounts.services.verification import require_verified_email
from apps.boards.models import BoardVariant, WorkshopProfile
from apps.boards.services.sku import SHAPER_CODE_RE, derive_shaper_code
from apps.common.exceptions import Conflict, DomainError
from apps.common.text import unique_slug
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services import claim_media
from apps.organizations.models import Membership, Organization
from apps.trust.services.audit import record
from apps.trust.services.restrictions import require_can_publish

ORG_FIELDS = ["name", "short_description", "description", "region", "city", "address", "phone", "email", "website",
              "social_links"]
PROFILE_FIELDS = ["specialization", "services", "lead_time", "does_repair", "repair_note", "experience_since"]


def _code_exists(code, exclude_org_id=None):
    qs = WorkshopProfile.objects.filter(shaper_code=code)
    if exclude_org_id:
        qs = qs.exclude(organization_id=exclude_org_id)
    return qs.exists()


def ensure_workshop_profile(workshop):
    """Профиль мастерской создаётся лениво, если организация kind=workshop создана в другом месте (POST organizations)."""
    profile = getattr(workshop, "_workshop_profile_cache", None)
    if profile is not None:
        return profile
    for _attempt in range(5):
        profile = WorkshopProfile.objects.filter(organization=workshop).first()
        if profile is not None:
            break
        try:
            with transaction.atomic():
                profile = WorkshopProfile.objects.create(
                    organization=workshop, shaper_code=derive_shaper_code(workshop.name, _code_exists))
            break
        except IntegrityError:  # гонка: профиль создан параллельно или код занят — перечитываем/подбираем заново
            continue
    else:  # pragma: no cover - защитный путь
        raise Conflict("Не удалось создать профиль мастерской, повторите попытку.", code="workshop_profile_race")
    workshop._workshop_profile_cache = profile
    return profile


def _apply_media(account, target, field, media_id, purposes, kinds):
    if media_id is None:
        setattr(target, field, None)
        return
    setattr(target, field, claim_media(media_id, account, purposes=purposes, kinds=kinds))


def _validate_shaper_code(code, workshop=None):
    code = (code or "").strip().upper()
    if not SHAPER_CODE_RE.match(code):
        raise DomainError("shaper_code_invalid", "Код шейпера — 2–6 заглавных латинских букв или цифр.",
                          fields={"shaper_code": ["2–6 символов A–Z, 0–9."]})
    if _code_exists(code, exclude_org_id=workshop.pk if workshop else None):
        raise Conflict("Такой код шейпера уже занят.", code="shaper_code_taken",
                       fields={"shaper_code": ["Код занят другой мастерской."]})
    return code


@transaction.atomic
def save_workshop(account, data, workshop=None, request=None):
    """Создаёт мастерскую (workshop=None) или обновляет её. Возвращает (workshop, created)."""
    require_can_publish(account)
    if workshop is None:
        # Двойной клик «Зарегистрироваться как шейпер»: сериализуем создание по аккаунту и перепроверяем членство.
        from apps.accounts.models import Account
        from apps.boards.services.access import my_workshop_membership, require_workshop_manager

        Account.objects.select_for_update().filter(pk=account.pk).first()
        existing = my_workshop_membership(account)
        if existing is not None:
            workshop = existing.organization
            require_workshop_manager(account, workshop)
    created = workshop is None
    if created:
        require_specialty(account, Specialty.SHAPER,
                          "Подключите направление «Шейпер» в разделе «Мои направления», чтобы создать мастерскую.")
        name = (data.get("name") or "").strip()
        if not name:
            raise DomainError("validation_error", "Укажите название мастерской.",
                              fields={"name": ["Обязательное поле."]})
        workshop = Organization(kind=Organization.Kind.WORKSHOP, owner=account, name=name,
                                slug=unique_slug(Organization, name), status=Organization.Status.DRAFT)
        before = None
    else:
        workshop = Organization.objects.select_for_update().get(pk=workshop.pk)
        before = snapshot(workshop)

    for field in ORG_FIELDS:
        if field in data:
            value = data[field]
            setattr(workshop, field, value.strip() if isinstance(value, str) else value)
    if "logo_id" in data:
        _apply_media(account, workshop, "logo", data["logo_id"], [MediaAsset.Purpose.ORG_LOGO, MediaAsset.Purpose.AVATAR],
                     [MediaAsset.Kind.IMAGE])
    if "cover_id" in data:
        _apply_media(account, workshop, "cover", data["cover_id"], [MediaAsset.Purpose.ORG_COVER],
                     [MediaAsset.Kind.IMAGE])
    workshop.save()

    if created:
        Membership.objects.create(organization=workshop, account=account, role=Membership.Role.OWNER)
        code = data.get("shaper_code")
        code = _validate_shaper_code(code) if code else derive_shaper_code(workshop.name, _code_exists)
        profile = WorkshopProfile(organization=workshop, shaper_code=code)
    else:
        profile = WorkshopProfile.objects.select_for_update().filter(organization=workshop).first()
        if profile is None:
            profile = ensure_workshop_profile(workshop)
        code = data.get("shaper_code")
        if code and code.strip().upper() != profile.shaper_code:
            if BoardVariant.objects.filter(model__workshop=workshop).exists():
                raise Conflict("Код шейпера уже используется в артикулах ваших досок и не может быть изменён.",
                               code="shaper_code_locked", fields={"shaper_code": ["Код закреплён за артикулами."]})
            profile.shaper_code = _validate_shaper_code(code, workshop)

    for field in PROFILE_FIELDS:
        if field in data:
            value = data[field]
            setattr(profile, field, value.strip() if isinstance(value, str) else value)
    if "promo_video_id" in data:
        _apply_media(account, profile, "promo_video", data["promo_video_id"], [MediaAsset.Purpose.PROMO_VIDEO],
                     [MediaAsset.Kind.VIDEO])
    try:
        with transaction.atomic():
            profile.save()
    except IntegrityError as exc:
        raise Conflict("Такой код шейпера уже занят.", code="shaper_code_taken",
                       fields={"shaper_code": ["Код занят другой мастерской."]}) from exc
    workshop._workshop_profile_cache = profile

    record(account, "workshop.created" if created else "workshop.updated", workshop, before=before,
           after=snapshot(workshop), organization=workshop, request=request)
    return workshop, created


def snapshot(workshop):
    data = {f: getattr(workshop, f) for f in ["name", "short_description", "city", "status"]}
    data["region_id"] = workshop.region_id
    profile = WorkshopProfile.objects.filter(organization=workshop).first()
    if profile:
        data.update({f: getattr(profile, f) for f in ["shaper_code", "specialization", "lead_time", "does_repair"]})
    return data


def publish_requirements(workshop, account=None):
    """Чек-лист публикации мастерской для UI: [{code, label, ok}]."""
    profile = WorkshopProfile.objects.filter(organization=workshop).first()
    items = [
        ("name", "Название мастерской", bool(workshop.name.strip())),
        ("region", "Регион", workshop.region_id is not None),
        ("specialization", "Специализация", bool(profile and profile.specialization.strip())),
    ]
    if account is not None:
        items.append(("email_verified", "Подтверждённый email", account.is_email_verified))
    return [{"code": code, "label": label, "ok": ok} for code, label, ok in items]


@transaction.atomic
def publish_workshop(account, workshop, request=None):
    workshop = Organization.objects.select_for_update().get(pk=workshop.pk)
    if workshop.status == Organization.Status.SUSPENDED:
        raise Conflict("Мастерская ограничена модератором. Обратитесь в поддержку.", code="workshop_suspended")
    if workshop.status == Organization.Status.ARCHIVED:
        raise Conflict("Мастерская в архиве.", code="workshop_archived")
    require_verified_email(account, "публикации мастерской")
    require_can_publish(account)
    missing = [item for item in publish_requirements(workshop) if not item["ok"]]
    if missing:
        raise DomainError("workshop_incomplete", "Заполните обязательные поля: " + ", ".join(m["label"] for m in missing) + ".",
                          fields={m["code"]: ["Обязательное поле."] for m in missing})
    if workshop.status != Organization.Status.PUBLISHED:
        before = workshop.status
        workshop.status = Organization.Status.PUBLISHED
        workshop.published_at = workshop.published_at or timezone.now()
        workshop.save(update_fields=["status", "published_at", "updated_at"])
        record(account, "workshop.published", workshop, before={"status": before}, after={"status": workshop.status},
               organization=workshop, request=request)
    return workshop


@transaction.atomic
def unpublish_workshop(account, workshop, request=None):
    workshop = Organization.objects.select_for_update().get(pk=workshop.pk)
    if workshop.status in (Organization.Status.PUBLISHED, Organization.Status.PENDING_REVIEW):
        before = workshop.status
        workshop.status = Organization.Status.DRAFT
        workshop.save(update_fields=["status", "updated_at"])
        record(account, "workshop.unpublished", workshop, before={"status": before}, after={"status": workshop.status},
               organization=workshop, request=request)
    elif workshop.status == Organization.Status.SUSPENDED:
        raise Conflict("Мастерская ограничена модератором.", code="workshop_suspended")
    return workshop
