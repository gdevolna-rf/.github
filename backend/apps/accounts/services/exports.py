"""Выгрузка персональных данных (ACC-13, TRUST-09): JSON в закрытом хранилище + уведомление со ссылкой."""
import datetime as dt
import json
import logging

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import DataExportRequest
from apps.common.exceptions import Conflict

logger = logging.getLogger(__name__)

# Повторный запрос не чаще, чем раз в REQUEST_COOLDOWN, пока предыдущий готовится.
REQUEST_COOLDOWN = dt.timedelta(minutes=10)
EXPORT_FORMAT_VERSION = 1


def request_export(account):
    from apps.accounts.tasks import build_data_export

    with transaction.atomic():
        recent = DataExportRequest.objects.select_for_update().filter(
            account=account, status=DataExportRequest.Status.PENDING,
            created_at__gt=timezone.now() - REQUEST_COOLDOWN,
        ).first()
        if recent is not None:
            raise Conflict("Выгрузка уже готовится. Мы пришлём уведомление, когда файл будет готов.",
                           code="export_in_progress")
        export = DataExportRequest.objects.create(account=account)
        export_id = str(export.pk)
        transaction.on_commit(lambda: build_data_export.delay(export_id))
    return export


def _values(qs, *fields):
    return [dict(row) for row in qs.values(*fields)]


def collect_account_data(account):
    """Все данные, которые пользователь создал или которые описывают его (без чужих персональных данных)."""
    from apps.commerce.models import Booking, Inquiry
    from apps.community.models import SurfSession
    from apps.favorites.models import Favorite
    from apps.messaging.models import Message
    from apps.organizations.models import Membership
    from apps.trust.models import Review

    profile = getattr(account, "profile", None)
    profile_data = None
    if profile is not None:
        profile_data = {
            "handle": profile.handle, "first_name": profile.first_name, "last_name": profile.last_name,
            "region": profile.region.name if profile.region_id else None, "city": profile.city, "bio": profile.bio,
            "fun_facts": profile.fun_facts, "surfing_since": profile.surfing_since,
            "riding_level": profile.riding_level, "preferred_board_types": profile.preferred_board_types,
            "favorite_spots": list(profile.favorite_spots.values_list("name", flat=True)),
            "interests": profile.interests, "languages": profile.languages, "phone": profile.phone,
            "birth_date": profile.birth_date, "private_contacts": profile.private_contacts,
            "avatar_media_id": profile.avatar_id,
            "gg_surfer_enabled": profile.gg_surfer_enabled, "gg_contact_policy": profile.gg_contact_policy,
            "gg_show_region": profile.gg_show_region, "gg_show_age": profile.gg_show_age,
            "birthday_greetings_consent": profile.birthday_greetings_consent, "show_birthday": profile.show_birthday,
        }
    inquiries = _values(
        Inquiry.objects.filter(customer=account).order_by("created_at"),
        "id", "kind", "status", "subject", "message", "details", "provider_account_id", "provider_organization_id",
        "agreed_amount", "currency", "created_at", "closed_at",
    )
    messages = _values(
        Message.objects.filter(sender=account).order_by("created_at"),
        "id", "conversation_id", "conversation__inquiry_id", "kind", "body", "created_at", "edited_at",
    )
    return {
        "format_version": EXPORT_FORMAT_VERSION,
        "generated_at": timezone.now(),
        "account": {
            "id": account.pk, "email": account.email, "date_joined": account.date_joined,
            "email_verified_at": account.email_verified_at, "two_factor_enabled": account.totp_enabled,
            "deletion_requested_at": account.deletion_requested_at,
        },
        "profile": profile_data,
        "specialties": _values(account.specialties.order_by("created_at"), "specialty_id", "status", "is_primary",
                               "activated_at", "disabled_at"),
        "staff_roles": _values(account.staff_roles.order_by("granted_at"), "role", "granted_at", "revoked_at"),
        "memberships": _values(
            Membership.objects.filter(account=account).order_by("joined_at"),
            "organization_id", "organization__name", "organization__kind", "role", "status", "title", "joined_at",
            "revoked_at",
        ),
        "inquiries": inquiries,
        "messages": messages,
        "bookings": _values(
            Booking.objects.filter(customer=account).order_by("starts_at"),
            "id", "kind", "status", "lesson_session_id", "inventory_item_id", "starts_at", "ends_at", "seats",
            "participant_name", "participant_is_minor", "price_amount", "currency", "customer_note",
            "cancel_reason", "created_at",
        ),
        "reviews": _values(
            Review.objects.filter(author=account).order_by("created_at"),
            "id", "target_type", "spot_id", "instructor_id", "organization_id", "rating", "text", "status",
            "created_at", "published_at",
        ),
        "favorites": _values(
            Favorite.objects.filter(account=account).order_by("created_at"),
            "target_type", "spot_id", "instructor_id", "organization_id", "board_model_id", "inventory_item_id",
            "created_at",
        ),
        "diary": _values(
            SurfSession.objects.filter(account=account).order_by("date"),
            "id", "spot_id", "spot_name", "date", "duration_min", "board_note", "conditions", "wave_height_m",
            "mood_rating", "notes", "visibility", "created_at",
        ),
        "consents": _values(account.consents.order_by("created_at"), "kind", "granted", "ip", "user_agent",
                            "created_at"),
    }


def build_export(export_id):
    """Celery: собирает JSON, кладёт в private/data_export/…, создаёт MediaAsset и уведомляет владельца."""
    from apps.mediafiles import policy
    from apps.mediafiles.models import MediaAsset
    from apps.mediafiles.storage import get_storage
    from apps.messaging.models import Notification
    from apps.messaging.services.notify import notify

    export = DataExportRequest.objects.select_related("account").filter(pk=export_id).first()
    if export is None or export.status != DataExportRequest.Status.PENDING:
        return None
    account = export.account
    try:
        payload = json.dumps(collect_account_data(account), cls=DjangoJSONEncoder, ensure_ascii=False,
                             indent=2).encode("utf-8")
        purpose = MediaAsset.Purpose.DATA_EXPORT
        key = policy.build_key(purpose, "application/json", MediaAsset.Visibility.PRIVATE)
        get_storage().write(key, payload, "application/json")
    except Exception:
        logger.exception("data export failed id=%s", export_id)
        DataExportRequest.objects.filter(pk=export.pk).update(status=DataExportRequest.Status.FAILED,
                                                              completed_at=timezone.now())
        raise

    now = timezone.now()
    with transaction.atomic():
        asset = MediaAsset.objects.create(
            owner=account, kind=MediaAsset.Kind.DOCUMENT, purpose=purpose, visibility=MediaAsset.Visibility.PRIVATE,
            status=MediaAsset.Status.READY, storage_key=key, content_type="application/json",
            size_bytes=len(payload), original_filename=f"gdevolna-data-{now:%Y-%m-%d}.json", processed_at=now,
        )
        export.status = DataExportRequest.Status.READY
        export.file = asset
        export.completed_at = now
        export.save(update_fields=["status", "file", "completed_at", "updated_at"])
        notify(account, Notification.Kind.SYSTEM, "Выгрузка данных готова",
               "Файл с вашими данными можно скачать в настройках аккаунта.", link="/account/settings",
               payload={"export_id": str(export.pk), "media_id": str(asset.pk)}, event_id=f"data_export:{export.pk}")
    return str(asset.pk)
