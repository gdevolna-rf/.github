"""Кабинет инструктора: профиль, публикация, медиа, сертификаты, предложения (INS-01…12, ACC-15, F03/F04)."""
from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts.services.verification import require_verified_email
from apps.common.exceptions import Conflict, DomainError, Forbidden, NotFound
from apps.learning.models import InstructorCertificate, InstructorMedia, InstructorOffer, InstructorProfile
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services import claim_media
from apps.trust.models import ModerationCase
from apps.trust.services.audit import record
from apps.trust.services.moderation_queue import open_case
from apps.trust.services.restrictions import require_can_publish

MAX_MEDIA_ITEMS = 20
MAX_CERTIFICATES = 10

PROFILE_FIELDS = ("headline", "about", "fun_facts", "surfing_since", "teaching_since", "riding_level", "formats",
                  "student_levels", "board_types", "languages", "price_from", "currency", "contact_note",
                  "allow_overlap")


# --- профиль ---------------------------------------------------------------------------------------------------

def publish_requirements(profile):
    """Обязательные поля публикации (ACC-15). Сертификат и документ о месте работы НЕ требуются (F03, ATX-04, INS-05)."""
    missing = {}
    account_profile = getattr(profile.account, "profile", None)
    if not account_profile or not account_profile.first_name.strip() or not account_profile.last_name.strip():
        missing["name"] = "Укажите имя и фамилию в общем профиле."
    if not (profile.headline or "").strip() and not (profile.about or "").strip():
        missing["headline"] = "Добавьте короткое описание или раздел «О себе»."
    if profile.pk is None or not profile.regions.exists():
        missing["region_slugs"] = "Выберите хотя бы один регион."
    if not profile.formats:
        missing["formats"] = "Укажите хотя бы один формат занятий."
    has_offer = profile.pk is not None and profile.offers.filter(is_active=True).exists()
    if profile.price_from is None and not has_offer:
        missing["price_from"] = "Укажите стоимость «от» или добавьте активное предложение."
    return missing


def _raise_requirements(missing):
    raise DomainError("publish_requirements", "Заполните обязательные поля, чтобы опубликовать карточку.",
                      fields={k: [v] for k, v in missing.items()})


@transaction.atomic
def save_profile(account, data):
    """Создаёт профиль при первом сохранении (PUT) и обновляет поля. Опубликованная карточка остаётся валидной."""
    require_can_publish(account)
    profile, created = InstructorProfile.objects.select_for_update().get_or_create(account=account)
    for field in PROFILE_FIELDS:
        if field in data:
            setattr(profile, field, data[field])
    profile.save()
    if "regions" in data:
        profile.regions.set(data["regions"])
    if "spots" in data:
        profile.spots.set(data["spots"])
    if profile.status == InstructorProfile.Status.PUBLISHED:
        missing = publish_requirements(profile)
        if missing:
            _raise_requirements(missing)  # исключение откатывает транзакцию
    if created:
        record(account, "instructor_profile.created", profile)
    return profile


@transaction.atomic
def publish(account, request=None):
    from apps.learning.services.access import get_own_profile

    profile = get_own_profile(account)
    profile = InstructorProfile.objects.select_for_update().get(pk=profile.pk)
    require_verified_email(account, "публикации карточки инструктора")
    if profile.status == InstructorProfile.Status.HIDDEN:
        raise Forbidden("Карточка скрыта модератором. Обратитесь в поддержку или подайте апелляцию.",
                        code="profile_hidden")
    require_can_publish(account)
    missing = publish_requirements(profile)
    if missing:
        _raise_requirements(missing)
    before = profile.status
    profile.status = InstructorProfile.Status.PUBLISHED
    profile.published_at = profile.published_at or timezone.now()
    profile.save(update_fields=["status", "published_at", "updated_at"])
    record(account, "instructor_profile.published", profile, before={"status": before},
           after={"status": profile.status}, request=request)
    return profile


@transaction.atomic
def unpublish(account, request=None):
    from apps.learning.services.access import get_own_profile

    profile = get_own_profile(account)
    profile = InstructorProfile.objects.select_for_update().get(pk=profile.pk)
    if profile.status == InstructorProfile.Status.PUBLISHED:
        profile.status = InstructorProfile.Status.DRAFT
        profile.save(update_fields=["status", "updated_at"])
        record(account, "instructor_profile.unpublished", profile, before={"status": "published"},
               after={"status": profile.status}, request=request)
    return profile


# --- медиа (INS-12) --------------------------------------------------------------------------------------------

@transaction.atomic
def add_media(profile, media_id, account):
    require_can_publish(account)
    profile = InstructorProfile.objects.select_for_update().get(pk=profile.pk)
    asset = claim_media(media_id, account, purposes=[MediaAsset.Purpose.PROFILE_GALLERY],
                        kinds=[MediaAsset.Kind.IMAGE, MediaAsset.Kind.VIDEO])
    if profile.media_items.filter(media=asset).exists():
        raise Conflict("Этот файл уже есть в галерее.", code="media_duplicate")
    if profile.media_items.count() >= MAX_MEDIA_ITEMS:
        raise DomainError("media_limit", f"В галерее может быть не больше {MAX_MEDIA_ITEMS} фото и видео.")
    position = (profile.media_items.aggregate(m=Max("position"))["m"] or 0) + 1
    return InstructorMedia.objects.create(profile=profile, media=asset, position=position)


@transaction.atomic
def reorder_media(profile, ids):
    items = {item.pk: item for item in InstructorMedia.objects.select_for_update().filter(profile=profile)}
    if set(ids) != set(items) or len(ids) != len(items):
        raise DomainError("validation_error", "Передайте все элементы галереи в новом порядке.",
                          fields={"ids": ["Список должен содержать все элементы галереи без повторов."]})
    for position, pk in enumerate(ids, start=1):
        if items[pk].position != position:
            items[pk].position = position
            items[pk].save(update_fields=["position"])
    return list(InstructorMedia.objects.filter(profile=profile).select_related("media"))


@transaction.atomic
def move_media(item, position):
    items = list(InstructorMedia.objects.select_for_update().filter(profile_id=item.profile_id))
    ordered = [i for i in items if i.pk != item.pk]
    position = max(1, min(position, len(items)))
    ordered.insert(position - 1, next(i for i in items if i.pk == item.pk))
    return reorder_media(item.profile, [i.pk for i in ordered])


@transaction.atomic
def remove_media(item):
    profile = item.profile
    item.delete()
    remaining = list(InstructorMedia.objects.filter(profile=profile).order_by("position", "id"))
    for position, media_item in enumerate(remaining, start=1):
        if media_item.position != position:
            media_item.position = position
            media_item.save(update_fields=["position"])


# --- сертификаты (INS-03/04, TRUST-03, BR-07) ------------------------------------------------------------------

@transaction.atomic
def upload_certificate(profile, account, data, request=None):
    profile = InstructorProfile.objects.select_for_update().get(pk=profile.pk)
    document = claim_media(data["document_id"], account, purposes=[MediaAsset.Purpose.CERTIFICATE],
                           kinds=[MediaAsset.Kind.DOCUMENT, MediaAsset.Kind.IMAGE])
    if document.visibility != MediaAsset.Visibility.PRIVATE:
        raise DomainError("certificate_must_be_private", "Скан сертификата должен храниться как закрытый файл.")
    if InstructorCertificate.objects.filter(document=document).exists():
        raise Conflict("Этот файл уже прикреплён к сертификату.", code="certificate_duplicate")
    active = profile.certificates.exclude(status__in=[InstructorCertificate.Status.REJECTED,
                                                      InstructorCertificate.Status.REVOKED]).count()
    if active >= MAX_CERTIFICATES:
        raise DomainError("certificate_limit", f"Можно загрузить не больше {MAX_CERTIFICATES} сертификатов.")
    cert = InstructorCertificate.objects.create(
        instructor=profile, title=data["title"], issuer=data.get("issuer", ""), issued_on=data.get("issued_on"),
        valid_until=data.get("valid_until"), document=document, allow_public_scan=data.get("allow_public_scan", False),
        status=InstructorCertificate.Status.UPLOADED,
    )
    name = account.profile.display_name if hasattr(account, "profile") else account.email
    open_case(ModerationCase.Kind.CERTIFICATE, f"Сертификат «{cert.title}» — {name}", certificate=cert)
    record(account, "certificate.uploaded", cert, after={"title": cert.title, "status": cert.status}, request=request)
    return cert


@transaction.atomic
def update_certificate(cert, account, data, request=None):
    if "allow_public_scan" in data and data["allow_public_scan"] != cert.allow_public_scan:
        before = cert.allow_public_scan
        cert.allow_public_scan = data["allow_public_scan"]
        cert.save(update_fields=["allow_public_scan", "updated_at"])
        record(account, "certificate.scan_visibility_changed", cert, before={"allow_public_scan": before},
               after={"allow_public_scan": cert.allow_public_scan}, request=request)
    return cert


@transaction.atomic
def delete_certificate(cert, account, request=None):
    from apps.trust.services.moderation_queue import close_cases

    close_cases("withdrawn", None, "Сертификат удалён владельцем.", certificate=cert)
    record(account, "certificate.deleted", cert, before={"title": cert.title, "status": cert.status}, request=request)
    cert.delete()


def is_scan_public(cert):
    """Скан виден всем: проверен, не истёк, владелец разрешил показ, карточка опубликована, аккаунт активен."""
    profile = cert.instructor
    owner = profile.account
    return (cert.status == InstructorCertificate.Status.VERIFIED and cert.allow_public_scan
            and (cert.valid_until is None or cert.valid_until >= timezone.localdate())
            and profile.status == InstructorProfile.Status.PUBLISHED and owner.is_active
            and owner.anonymized_at is None)


def scan_access(cert, request):
    """Кто может получить скан: всем — если is_scan_public; иначе владелец или модератор с 2FA.
    Остальным 404 (ATX-23)."""
    from apps.accounts.services.roles import has_verified_staff_role

    user = request.user
    owner = cert.instructor.account
    if user.is_authenticated and user.pk == owner.pk:
        return "owner"
    if has_verified_staff_role(request, "moderator"):
        return "moderator"
    return "public" if is_scan_public(cert) else None


def scan_url(cert_id, request):
    """Ссылка на скан — через apps.mediafiles.services.access.access_url (тот же presigned GET, что у media/{id}/url)."""
    from apps.mediafiles.services.access import access_url

    cert = (InstructorCertificate.objects.select_related("instructor__account", "document")
            .filter(pk=cert_id).first())
    if cert is None:
        raise NotFound("Документ не найден.")
    access = scan_access(cert, request)
    document = cert.document
    if access is None or document.status not in (MediaAsset.Status.READY, MediaAsset.Status.PROCESSING):
        raise NotFound("Документ не найден.")
    link = access_url(document, request, allow_processing=True)
    if access == "moderator":
        record(request.user, "certificate.scan_viewed", cert, metadata={"access": access}, request=request)
    return {"url": link["url"], "expires_in": settings.MEDIA_PRIVATE_URL_TTL, "content_type": document.content_type}


# --- предложения (INS-08) --------------------------------------------------------------------------------------

@transaction.atomic
def delete_offer(offer, account, request=None):
    """Предложение с занятиями архивируется (история броней сохраняется), без занятий — удаляется."""
    if offer.sessions.exists():
        if offer.is_active:
            offer.is_active = False
            offer.save(update_fields=["is_active", "updated_at"])
        record(account, "instructor_offer.archived", offer, request=request)
        return "archived"
    record(account, "instructor_offer.deleted", offer, before={"title": offer.title}, request=request)
    offer.delete()
    return "deleted"


def ensure_offer_owned(offer_id, profile):
    offer = InstructorOffer.objects.filter(pk=offer_id, instructor=profile).select_related("spot").first()
    if offer is None:
        raise NotFound("Предложение не найдено.")
    return offer
