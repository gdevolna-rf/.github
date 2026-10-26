"""Организации: создание, редактирование, отправка на проверку (BR-03, ACC-11, SCH-01/02/13)."""
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.common.exceptions import DomainError, Forbidden, NotFound
from apps.common.text import unique_slug
from apps.organizations.models import Membership, Organization
from apps.organizations.services.access import active_membership

KIND_SPECIALTY = {Organization.Kind.WORKSHOP: "shaper", Organization.Kind.RENTAL: "rental"}
KIND_SPECIALTY_MESSAGE = {
    Organization.Kind.WORKSHOP: "Чтобы создать мастерскую, подключите направление «Шейпер» в разделе «Мои направления».",
    Organization.Kind.RENTAL: "Чтобы создать прокат, подключите направление «Прокат» в разделе «Мои направления».",
}
SIMPLE_FIELDS = ("name", "short_description", "description", "city", "address", "phone", "email", "website",
                 "social_links", "formats", "languages", "price_from", "currency")
MAX_GALLERY = 30
EDITABLE_STATUSES = {Organization.Status.DRAFT, Organization.Status.PENDING_REVIEW, Organization.Status.PUBLISHED,
                     Organization.Status.SUSPENDED}


def _snapshot(org, fields):
    out = {}
    for field in fields:
        value = getattr(org, field if field not in ("region", "logo", "cover") else f"{field}_id")
        out[field] = str(value) if value is not None and not isinstance(value, (list, dict, bool, int)) else value
    return out


def _apply_relations(org, account, data):
    """region_id, spot_ids, logo_id, cover_id, gallery_ids — с проверкой медиа через claim_media."""
    from apps.mediafiles.models import MediaAsset
    from apps.mediafiles.services import claim_media
    from apps.spots.models import Region

    changed = []
    saved_org = None if org._state.adding else org
    if "region_id" in data:
        region = None
        if data["region_id"] is not None:
            region = Region.objects.filter(pk=data["region_id"]).first()
            if region is None:
                raise DomainError("region_invalid", "Регион не найден.", fields={"region_id": ["Регион не найден."]})
        if org.region_id != (region.pk if region else None):
            org.region = region
            changed.append("region")
    for field, purpose in (("logo", MediaAsset.Purpose.ORG_LOGO), ("cover", MediaAsset.Purpose.ORG_COVER)):
        key = f"{field}_id"
        if key not in data:
            continue
        value = data[key]
        if value is None:
            if getattr(org, key):
                setattr(org, field, None)
                changed.append(field)
        elif value != getattr(org, key):
            setattr(org, field, claim_media(value, account, purposes=[purpose], kinds=[MediaAsset.Kind.IMAGE],
                                            organization=saved_org))
            changed.append(field)
    return changed


def _apply_m2m(org, account, data):
    from apps.mediafiles.models import MediaAsset
    from apps.mediafiles.services import claim_media
    from apps.spots.models import Spot

    if "spot_ids" in data:
        ids = list(dict.fromkeys(data["spot_ids"]))
        spots = list(Spot.objects.filter(pk__in=ids, status=Spot.Status.PUBLISHED))
        if len(spots) != len(ids):
            raise DomainError("spot_invalid", "Некоторые споты не найдены.",
                              fields={"spot_ids": ["Спот не найден или не опубликован."]})
        org.spots.set(spots)
    if "gallery_ids" in data:
        ids = list(dict.fromkeys(data["gallery_ids"]))
        if len(ids) > MAX_GALLERY:
            raise DomainError("gallery_too_large", f"В галерее не больше {MAX_GALLERY} файлов.",
                              fields={"gallery_ids": [f"Максимум {MAX_GALLERY}."]})
        current = {asset.pk: asset for asset in org.gallery.all()}
        assets = []
        for media_id in ids:
            if media_id in current:  # уже в галерее (мог загрузить другой сотрудник)
                assets.append(current[media_id])
            else:
                assets.append(claim_media(media_id, account, purposes=[MediaAsset.Purpose.ORG_GALLERY],
                                          organization=org))
        org.gallery.set(assets)


def create_organization(account, data, request=None):
    """Создатель становится owner. Мастерская требует направление «Шейпер», прокат — «Прокат»."""
    from apps.accounts.services.specialties import require_specialty
    from apps.trust.services.audit import record
    from apps.trust.services.restrictions import require_can_publish

    require_can_publish(account)
    kind = data["kind"]
    if kind in KIND_SPECIALTY:
        require_specialty(account, KIND_SPECIALTY[kind], KIND_SPECIALTY_MESSAGE[kind])
    for attempt in range(3):
        try:
            with transaction.atomic():
                org = Organization(kind=kind, owner=account, status=Organization.Status.DRAFT,
                                   slug=unique_slug(Organization, data["name"], max_length=80))
                for field in SIMPLE_FIELDS:
                    if field in data:
                        setattr(org, field, data[field])
                _apply_relations(org, account, data)
                org.save()
                Membership.objects.create(organization=org, account=account, role=Membership.Role.OWNER)
                if kind == Organization.Kind.WORKSHOP:
                    # Мастерская = Organization + WorkshopProfile (код шейпера для артикулов, SHP-01/BRD-05).
                    from apps.boards.services.workshops import ensure_workshop_profile

                    ensure_workshop_profile(org)
                _apply_m2m(org, account, data)
                for asset in (org.logo, org.cover):
                    if asset is not None and asset.organization_id is None:
                        asset.organization = org
                        asset.save(update_fields=["organization", "updated_at"])
                record(account, "organization.created", org, organization=org,
                       after={"kind": kind, "name": org.name, "slug": org.slug}, request=request)
                return org
        except IntegrityError:
            if attempt == 2:  # гонка за slug
                raise
    return None  # pragma: no cover


def get_for_member(org_id, account, roles=None):
    """Организация для закрытых эндпоинтов: не участник → 404, недостаточная роль → 403."""
    org = Organization.objects.filter(pk=org_id).first()
    membership = active_membership(account, org) if org else None
    if org is None or membership is None:
        raise NotFound("Организация не найдена.")
    if roles and membership.role not in roles:
        raise Forbidden("Недостаточно прав в этой организации.")
    return org, membership


def update_organization(org, account, data, request=None):
    from apps.trust.services.audit import record
    from apps.trust.services.restrictions import require_can_publish

    require_can_publish(account)

    if org.status not in EDITABLE_STATUSES:
        raise DomainError("organization_archived", "Организация в архиве и не редактируется.")
    tracked = list(SIMPLE_FIELDS) + ["region", "logo", "cover"]
    with transaction.atomic():
        org = Organization.objects.select_for_update().get(pk=org.pk)
        before = _snapshot(org, tracked)
        changed = [f for f in SIMPLE_FIELDS if f in data and getattr(org, f) != data[f]]
        for field in changed:
            setattr(org, field, data[field])
        changed += _apply_relations(org, account, data)
        if changed:
            org.save()
        _apply_m2m(org, account, data)
        after = _snapshot(org, tracked)
        diff_before = {k: v for k, v in before.items() if before[k] != after[k]}
        diff_after = {k: after[k] for k in diff_before}
        if diff_before or "spot_ids" in data or "gallery_ids" in data:
            record(account, "organization.updated", org, organization=org, before=diff_before, after=diff_after,
                   metadata={"spots": "spot_ids" in data, "gallery": "gallery_ids" in data}, request=request)
    return org


def missing_fields(org):
    """Обязательные для публикации поля (SCH-13, ACC-15)."""
    missing = []
    if not (org.name or "").strip():
        missing.append("name")
    if not (org.description or "").strip():
        missing.append("description")
    if org.region_id is None:
        missing.append("region")
    if not org.spots.exists() and not (org.address or "").strip():
        missing.append("spots_or_address")
    return missing


MISSING_LABELS = {
    "name": "название", "description": "описание", "region": "регион",
    "spots_or_address": "хотя бы один спот или адрес",
}


def submit_for_review(org, account, request=None):
    from apps.accounts.services.verification import require_verified_email
    from apps.trust.models import ModerationCase
    from apps.trust.services.audit import record
    from apps.trust.services.moderation_queue import open_case

    from apps.trust.services.restrictions import require_can_publish

    require_verified_email(account, "публикации организации")
    require_can_publish(account)
    with transaction.atomic():
        org = Organization.objects.select_for_update().get(pk=org.pk)
        if org.status == Organization.Status.PENDING_REVIEW:
            raise DomainError("already_pending", "Организация уже на проверке.")
        if org.status == Organization.Status.PUBLISHED:
            raise DomainError("already_published", "Организация уже опубликована.")
        if org.status != Organization.Status.DRAFT:
            raise DomainError("status_invalid", "Отправить на проверку можно только черновик. "
                                                "Если организация ограничена — обратитесь к модератору.")
        missing = missing_fields(org)
        if missing:
            labels = ", ".join(MISSING_LABELS[m] for m in missing)
            raise DomainError("organization_incomplete", f"Заполните перед публикацией: {labels}.",
                              fields={m: ["Обязательное поле."] for m in missing})
        org.status = Organization.Status.PENDING_REVIEW
        org.moderation_note = ""
        if org.verification_status in (Organization.Verification.NONE, Organization.Verification.REJECTED):
            org.verification_status = Organization.Verification.PENDING
        org.save(update_fields=["status", "moderation_note", "verification_status", "updated_at"])
        case = open_case(ModerationCase.Kind.ORGANIZATION,
                         f"Публикация: {org.get_kind_display()} «{org.name}»", organization=org)
        record(account, "organization.submitted", org, organization=org, before={"status": "draft"},
               after={"status": org.status}, metadata={"case": str(case.pk)}, request=request)
    return org


# --- публичные выборки ----------------------------------------------------------------------------------------

def public_queryset(params=None):
    params = params or {}
    qs = Organization.objects.filter(status=Organization.Status.PUBLISHED).select_related(
        "region", "logo", "cover")
    kind = params.get("kind")
    if kind:
        qs = qs.filter(kind=kind)
    region = params.get("region")
    if region:
        qs = qs.filter(region_id=int(region)) if str(region).isdigit() else qs.filter(region__slug=region)
    spot = params.get("spot")
    if spot:
        qs = qs.filter(spots__slug=spot) if not _looks_like_uuid(spot) else qs.filter(spots__id=spot)
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(short_description__icontains=q) | Q(city__icontains=q))
    return qs.distinct().order_by("-rating_avg", "-rating_count", "name")


def _looks_like_uuid(value):
    import uuid

    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


def team(org):
    """Активные участники; один человек — один account.id (ATX-35)."""
    from apps.learning.models import InstructorProfile

    memberships = list(Membership.objects.filter(organization=org, status=Membership.Status.ACTIVE)
                       .select_related("account__profile__avatar").order_by("joined_at"))
    account_ids = [m.account_id for m in memberships]
    published = dict(InstructorProfile.objects.filter(
        account_id__in=account_ids, status=InstructorProfile.Status.PUBLISHED).values_list("account_id", "id"))
    role_order = {Membership.Role.OWNER: 0, Membership.Role.MANAGER: 1, Membership.Role.INSTRUCTOR: 2,
                  Membership.Role.STAFF: 3}
    seen, result = set(), []
    for m in sorted(memberships, key=lambda m: (role_order.get(m.role, 9), m.joined_at)):
        if m.account_id in seen or m.account.anonymized_at:
            continue
        seen.add(m.account_id)
        profile = getattr(m.account, "profile", None)
        result.append({
            "account": m.account,
            "role": m.role,
            "title": m.title,
            "instructor_profile": ({"id": published[m.account_id], "handle": profile.handle}
                                   if m.account_id in published and profile else None),
        })
    return result


def upcoming_sessions(org, limit=20):
    """Ближайшие занятия школы со свободными местами = вместимость − подтверждённые места."""
    from apps.commerce.models import ACTIVE_BOOKING_STATUSES
    from apps.learning.models import LessonSession

    sessions = (LessonSession.objects.filter(organization=org, status=LessonSession.Status.SCHEDULED,
                                             starts_at__gt=timezone.now())
                .select_related("spot", "instructor__profile__avatar", "program")
                .annotate(taken=Sum("bookings__seats", filter=Q(bookings__status__in=ACTIVE_BOOKING_STATUSES)))
                .order_by("starts_at")[:limit])
    result = []
    for session in sessions:
        session.free_seats = max(session.capacity - (session.taken or 0), 0)
        result.append(session)
    return result


def active_programs(org):
    from apps.learning.models import SchoolProgram

    return SchoolProgram.objects.filter(organization=org, is_active=True).order_by("price", "title")
