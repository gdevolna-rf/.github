"""Удаление аккаунта с отсрочкой (AT-10, TRUST-09, 6.2).

Анонимизируются личные данные; заказы, обращения, сообщения, отзывы и журналы сохраняются и продолжают
ссылаться на неизменный account.id (публично — «Удалённый пользователь»).
"""
import datetime as dt
import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Account, AccountDeletionRequest, HandleRedirect, StaffRole, UserProfile
from apps.common.exceptions import DomainError, NotFound

logger = logging.getLogger(__name__)


def grace_days():
    return settings.ACCOUNT_DELETION_GRACE_DAYS


def active_request(account):
    return AccountDeletionRequest.objects.filter(account=account, status=AccountDeletionRequest.Status.REQUESTED).first()


def blocking_organizations(account):
    """Организации, где пользователь — владелец, а в команде есть другие активные участники."""
    from apps.organizations.models import Membership, Organization

    owned = Organization.objects.filter(owner=account).exclude(status=Organization.Status.ARCHIVED)
    return [org for org in owned if Membership.objects.filter(
        organization=org, status=Membership.Status.ACTIVE).exclude(account=account).exists()]


def request_deletion(account, reason="", request=None):
    from apps.trust.services.audit import record

    blocking = blocking_organizations(account)
    if blocking:
        names = ", ".join(f"«{org.name}»" for org in blocking)
        raise DomainError("ownership_transfer_required",
                          f"Сначала передайте владение организациями: {names}. Заказы и история организаций "
                          "должны остаться у команды.")
    with transaction.atomic():
        locked = Account.objects.select_for_update().get(pk=account.pk)
        existing = active_request(locked)
        if existing is not None:
            return existing
        now = timezone.now()
        deletion = AccountDeletionRequest.objects.create(
            account=locked, reason=(reason or "")[:2000], scheduled_for=now + dt.timedelta(days=grace_days()),
        )
        locked.deletion_requested_at = now
        locked.save(update_fields=["deletion_requested_at"])
        record(locked, "account.deletion_requested", deletion, after={"scheduled_for": deletion.scheduled_for.isoformat()},
               request=request)
        from apps.accounts.tasks import send_deletion_scheduled_email

        deletion_id = str(deletion.pk)
        transaction.on_commit(lambda: send_deletion_scheduled_email.delay(deletion_id))
    account.deletion_requested_at = locked.deletion_requested_at
    return deletion


def cancel_deletion(account, request=None):
    from apps.trust.services.audit import record

    with transaction.atomic():
        deletion = AccountDeletionRequest.objects.select_for_update().filter(
            account=account, status=AccountDeletionRequest.Status.REQUESTED).first()
        if deletion is None:
            raise NotFound("Запрос на удаление не найден.")
        deletion.status = AccountDeletionRequest.Status.CANCELLED
        deletion.save(update_fields=["status", "updated_at"])
        Account.objects.filter(pk=account.pk).update(deletion_requested_at=None)
        account.deletion_requested_at = None
        record(account, "account.deletion_cancelled", deletion, request=request)
    return deletion


def _clear_profile(account):
    from apps.mediafiles.models import MediaAsset
    from apps.mediafiles.services.uploads import _delete_objects

    profile = UserProfile.objects.filter(account=account).first()
    if profile is None:
        return
    avatar = profile.avatar
    profile.handle = f"deleted-{uuid.uuid4().hex[:12]}"
    profile.first_name = profile.last_name = ""
    profile.avatar = None
    profile.region = None
    profile.city = profile.bio = profile.phone = profile.private_contacts = ""
    profile.fun_facts, profile.preferred_board_types, profile.interests, profile.languages = [], [], [], []
    profile.surfing_since = None
    profile.riding_level = ""
    profile.birth_date = None
    profile.gg_surfer_enabled = False
    profile.gg_contact_policy = UserProfile.ContactPolicy.NOBODY
    profile.gg_show_region = profile.gg_show_age = False
    profile.birthday_greetings_consent = profile.show_birthday = False
    profile.save()
    profile.favorite_spots.clear()
    HandleRedirect.objects.filter(account=account).delete()
    if avatar is not None:
        MediaAsset.objects.filter(pk=avatar.pk).update(status=MediaAsset.Status.DELETED)
        transaction.on_commit(lambda: _delete_objects(avatar))


def _purge_private_media(account):
    """Выгрузки персональных данных удаляются вместе с аккаунтом."""
    from apps.mediafiles.models import MediaAsset
    from apps.mediafiles.services.uploads import _delete_objects

    exports = list(MediaAsset.objects.filter(owner=account, purpose=MediaAsset.Purpose.DATA_EXPORT)
                   .exclude(status=MediaAsset.Status.DELETED))
    MediaAsset.objects.filter(pk__in=[a.pk for a in exports]).update(status=MediaAsset.Status.DELETED)
    for asset in exports:
        transaction.on_commit(lambda asset=asset: _delete_objects(asset))


def _successor(org, account):
    from apps.organizations.models import Membership

    members = Membership.objects.filter(organization=org, status=Membership.Status.ACTIVE).exclude(account=account)
    return (members.filter(role=Membership.Role.MANAGER).order_by("joined_at").first()
            or members.order_by("joined_at").first())


def _detach_memberships(account, now):
    from apps.learning.models import InstructorProfile
    from apps.organizations.models import Membership, Organization
    from apps.trust.services.audit import record

    # Команда сохраняет организацию: владение переходит к самому давнему менеджеру (или участнику).
    # Организации без других участников архивируются; заказы и история остаются.
    for org in Organization.objects.select_for_update().filter(owner=account).exclude(
            status=Organization.Status.ARCHIVED):
        successor = _successor(org, account)
        if successor is None:
            org.status = Organization.Status.ARCHIVED
            org.save(update_fields=["status", "updated_at"])
            record(None, "organization.archived", org, organization=org, metadata={"reason": "owner_deleted"})
            continue
        successor.role = Membership.Role.OWNER
        successor.save(update_fields=["role", "updated_at"])
        org.owner_id = successor.account_id
        org.save(update_fields=["owner", "updated_at"])
        record(None, "organization.ownership_transferred", org, organization=org,
               before={"owner": str(account.pk)}, after={"owner": str(successor.account_id)},
               metadata={"reason": "owner_deleted"})
    Membership.objects.filter(account=account, status=Membership.Status.ACTIVE).update(
        status=Membership.Status.LEFT, revoked_at=now)
    InstructorProfile.objects.filter(account=account).exclude(status=InstructorProfile.Status.HIDDEN).update(
        status=InstructorProfile.Status.HIDDEN)
    StaffRole.objects.filter(account=account, revoked_at__isnull=True).update(revoked_at=now)

    from apps.organizations.models import OrganizationInvite

    OrganizationInvite.objects.filter(account=account, status=OrganizationInvite.Status.PENDING).update(
        status=OrganizationInvite.Status.REVOKED)


def _release_commitments(account, now):
    """Будущие обязательства удалённого аккаунта освобождаются (брони, слоты, места на событиях), личные
    материалы (дневник, подписки) удаляются. Сами заказы, обращения, сообщения и журналы остаются."""
    from apps.club.services.events import release_deleted_account
    from apps.commerce.services.bookings import cancel_for_deleted_account
    from apps.community.services.diary import purge_account_diary
    from apps.learning.services.sessions import release_deleted_instructor
    from apps.shop.models import ProductInterest

    cancel_for_deleted_account(account, now)
    release_deleted_instructor(account, now)
    release_deleted_account(account)
    purge_account_diary(account)
    ProductInterest.objects.filter(account=account).delete()


def anonymize_account(account, deletion=None):
    """Необратимая анонимизация. Записи заказов/сообщений/аудита остаются (AT-10)."""
    from apps.trust.services.audit import record

    now = timezone.now()
    with transaction.atomic():
        account = Account.objects.select_for_update().get(pk=account.pk)
        if account.anonymized_at:
            return account
        account.email = f"deleted-{uuid.uuid4().hex}@deleted.local"
        account.set_unusable_password()
        account.is_active = False
        account.is_staff = False
        account.is_superuser = False
        account.totp_enabled = False
        account.totp_secret = ""
        account.email_verified_at = None
        account.anonymized_at = now
        account.save()
        _clear_profile(account)
        _purge_private_media(account)
        _release_commitments(account, now)
        _detach_memberships(account, now)
        if deletion is not None:
            deletion.status = AccountDeletionRequest.Status.COMPLETED
            deletion.completed_at = now
            deletion.save(update_fields=["status", "completed_at", "updated_at"])
        record(None, "account.anonymized", account, metadata={"deletion_request": str(deletion.pk) if deletion else None})
    return account


def process_due_requests(now=None):
    """Celery beat (ежедневно 03:00): анонимизация после истечения отсрочки."""
    now = now or timezone.now()
    done = 0
    due = AccountDeletionRequest.objects.filter(status=AccountDeletionRequest.Status.REQUESTED, scheduled_for__lte=now)
    for deletion in due.select_related("account"):
        try:
            anonymize_account(deletion.account, deletion)
            done += 1
        except Exception:  # одна ошибка не должна останавливать остальные удаления
            logger.exception("account anonymization failed request=%s", deletion.pk)
    return done
