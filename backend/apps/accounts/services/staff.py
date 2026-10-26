"""Выдача и отзыв серверных ролей администратором (BR-04, ACC-10, TRUST-06) с журналом аудита."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Account, StaffRole
from apps.common.exceptions import Conflict, DomainError, NotFound


def grant_role(admin, account_email, role, request=None):
    from apps.messaging.models import Notification
    from apps.messaging.services.notify import notify
    from apps.trust.services.audit import record

    if role not in StaffRole.Role.values:
        raise DomainError("role_invalid", "Неизвестная роль.", fields={"role": ["Недопустимое значение."]})
    account = Account.objects.filter(email__iexact=(account_email or "").strip(), is_active=True,
                                     anonymized_at__isnull=True).first()
    if account is None:
        raise NotFound("Аккаунт с таким email не найден.")
    try:
        with transaction.atomic():
            staff_role = StaffRole.objects.create(account=account, role=role, granted_by=admin)
            record(admin, "staff_role.granted", staff_role, after={"account": str(account.pk), "role": role},
                   request=request)
            notify(account, Notification.Kind.SYSTEM, "Вам назначена служебная роль",
                   f"Роль: {StaffRole.Role(role).label}. Для доступа включите двухфакторную аутентификацию.",
                   link="/account/settings", event_id=f"staff_role:{staff_role.pk}", actor=admin)
    except IntegrityError as exc:
        raise Conflict("Эта роль уже выдана аккаунту.", code="role_already_granted") from exc
    return staff_role


def revoke_role(admin, staff_role_id, request=None):
    from apps.trust.services.audit import record

    with transaction.atomic():
        staff_role = StaffRole.objects.select_for_update().filter(pk=staff_role_id, revoked_at__isnull=True).first()
        if staff_role is None:
            raise NotFound("Активная роль не найдена.")
        if staff_role.role == StaffRole.Role.ADMIN:
            if staff_role.account_id == admin.pk:
                raise DomainError("cannot_revoke_self", "Нельзя снять роль администратора с самого себя.")
            remaining = StaffRole.objects.filter(role=StaffRole.Role.ADMIN, revoked_at__isnull=True).exclude(
                pk=staff_role.pk).count()
            if remaining == 0:
                raise DomainError("last_admin", "Нельзя отозвать роль последнего администратора.")
        staff_role.revoked_at = timezone.now()
        staff_role.save(update_fields=["revoked_at"])
        record(admin, "staff_role.revoked", staff_role, before={"account": str(staff_role.account_id),
                                                                "role": staff_role.role}, request=request)
    return staff_role


def find_active_role(account_email, role):
    return StaffRole.objects.filter(account__email__iexact=(account_email or "").strip(), role=role,
                                    revoked_at__isnull=True).first()
