"""Приглашения в организацию (5.3, ACC-11, SCH-09): роль активируется только после принятия адресатом."""
import datetime as dt
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.common.exceptions import Conflict, DomainError, Forbidden, NotFound
from apps.organizations.models import Membership, Organization, OrganizationInvite

R = Membership.Role
OWNER_INVITABLE = (R.MANAGER, R.INSTRUCTOR, R.STAFF)
MANAGER_INVITABLE = (R.INSTRUCTOR, R.STAFF)
ROLE_LABELS = dict(Membership.Role.choices)


def _new_token():
    return secrets.token_urlsafe(32)


def _check_role_allowed(actor_role, role):
    if role == R.OWNER:
        raise DomainError("role_invalid", "Пригласить владельца нельзя — используйте передачу владения.",
                          fields={"role": ["Недопустимое значение."]})
    allowed = OWNER_INVITABLE if actor_role == R.OWNER else MANAGER_INVITABLE if actor_role == R.MANAGER else ()
    if role not in allowed:
        raise Forbidden("Менеджер может приглашать только инструкторов и сотрудников."
                        if actor_role == R.MANAGER else "Недостаточно прав для приглашения.")


def create_invite(org, actor_membership, *, email, role, message="", request=None):
    from apps.accounts.models import Account
    from apps.trust.services.audit import record
    from apps.trust.services.restrictions import require_can_message

    _check_role_allowed(actor_membership.role, role)
    # Приглашение — письмо и уведомление другому человеку с произвольным текстом: как сообщение (TRUST-07).
    require_can_message(actor_membership.account)
    if org.status == Organization.Status.ARCHIVED:
        raise DomainError("organization_archived", "Организация в архиве.")
    email = email.strip().lower()
    account = Account.objects.filter(email__iexact=email, is_active=True, anonymized_at__isnull=True).first()
    if account is not None and Membership.objects.filter(organization=org, account=account,
                                                         status=Membership.Status.ACTIVE).exists():
        raise Conflict("Этот пользователь уже в команде.", code="already_member")
    try:
        with transaction.atomic():
            invite = OrganizationInvite.objects.create(
                organization=org, email=email, account=account, role=role, token=_new_token(),
                message=(message or "")[:2000], invited_by=actor_membership.account,
                expires_at=timezone.now() + dt.timedelta(days=settings.INVITE_TTL_DAYS),
            )
            record(actor_membership.account, "invite.created", invite, organization=org,
                   after={"email": email, "role": role}, request=request)
            if account is not None:
                from apps.messaging.models import Notification
                from apps.messaging.services.notify import notify

                notify(account, Notification.Kind.INVITE, f"Приглашение в «{org.name}»",
                       f"Вас приглашают в команду с ролью «{ROLE_LABELS[role]}».", link="/account/invites",
                       payload={"invite_id": str(invite.pk), "organization_id": str(org.pk)},
                       event_id=f"invite:{invite.pk}", actor=actor_membership.account)
            from apps.organizations.tasks import send_invite_email

            invite_id = str(invite.pk)
            transaction.on_commit(lambda: send_invite_email.delay(invite_id))
    except IntegrityError as exc:
        raise Conflict("Приглашение на этот email уже отправлено и ожидает ответа.", code="invite_exists") from exc
    return invite


def revoke_invite(invite_id, account, request=None):
    from apps.organizations.services.access import active_membership
    from apps.trust.services.audit import record

    with transaction.atomic():
        invite = OrganizationInvite.objects.select_for_update(of=("self",)).select_related("organization").filter(
            pk=invite_id).first()
        membership = active_membership(account, invite.organization) if invite else None
        if invite is None or membership is None:
            raise NotFound("Приглашение не найдено.")
        if membership.role not in (R.OWNER, R.MANAGER):
            raise Forbidden("Недостаточно прав в этой организации.")
        if membership.role == R.MANAGER and invite.role not in MANAGER_INVITABLE:
            raise Forbidden("Менеджер может отзывать только приглашения инструкторов и сотрудников.")
        if invite.status != OrganizationInvite.Status.PENDING:
            raise DomainError("invite_not_pending", "Приглашение уже не активно.")
        invite.status = OrganizationInvite.Status.REVOKED
        invite.responded_at = timezone.now()
        invite.save(update_fields=["status", "responded_at", "updated_at"])
        record(account, "invite.revoked", invite, organization=invite.organization,
               before={"status": "pending"}, after={"status": invite.status}, request=request)
    return invite


def addressed_to(account):
    """Q-фильтр приглашений, адресованных аккаунту (по ссылке на аккаунт или по email)."""
    return Q(account=account) | Q(account__isnull=True, email__iexact=account.email)


def my_invites(account):
    now = timezone.now()
    return (OrganizationInvite.objects.filter(addressed_to(account), status=OrganizationInvite.Status.PENDING,
                                              expires_at__gt=now)
            .select_related("organization__logo", "invited_by__profile__avatar").order_by("-created_at"))


def _get_addressed(token, account):
    invite = OrganizationInvite.objects.select_for_update(of=("self",)).select_related("organization", "invited_by").filter(
        token=token).first()
    if invite is None:
        raise NotFound("Приглашение не найдено.")
    if not (invite.account_id == account.pk or (invite.account_id is None
                                                and invite.email.lower() == account.email.lower())):
        raise Forbidden("Приглашение адресовано другому аккаунту. Войдите под email, на который оно отправлено.",
                        code="invite_wrong_account")
    from apps.accounts.services.verification import require_verified_email

    require_verified_email(account, "ответа на приглашение")
    if invite.status == OrganizationInvite.Status.PENDING and invite.expires_at <= timezone.now():
        invite.status = OrganizationInvite.Status.EXPIRED
        invite.save(update_fields=["status", "updated_at"])
        return invite, "expired"
    if invite.status != OrganizationInvite.Status.PENDING:
        return invite, invite.status
    return invite, None


def _inviter_notify(invite, account, accepted):
    from apps.messaging.models import Notification
    from apps.messaging.services.notify import notify

    name = getattr(getattr(account, "profile", None), "display_name", account.email)
    org = invite.organization
    title = f"Приглашение в «{org.name}» {'принято' if accepted else 'отклонено'}"
    body = f"{name} {'присоединился к команде' if accepted else 'отклонил приглашение'}" \
           f" (роль «{ROLE_LABELS[invite.role]}»)."
    notify(invite.invited_by, Notification.Kind.MEMBERSHIP if accepted else Notification.Kind.INVITE, title, body,
           link=f"/account/orgs/{org.pk}/team", payload={"invite_id": str(invite.pk), "organization_id": str(org.pk)},
           event_id=f"invite_response:{invite.pk}", actor=account)


def _respond(token, account, accept, request=None):
    """Принять/отклонить. Просроченное приглашение помечается expired (фиксируется) и даёт ошибку."""
    from apps.trust.services.audit import record

    with transaction.atomic():
        invite, problem = _get_addressed(token, account)
        if problem is None:
            org = Organization.objects.select_for_update().get(pk=invite.organization_id)
            now = timezone.now()
            if not accept:
                invite.status = OrganizationInvite.Status.DECLINED
                invite.account = account
                invite.responded_at = now
                invite.save(update_fields=["status", "account", "responded_at", "updated_at"])
                record(account, "invite.declined", invite, organization=org, request=request)
                _inviter_notify(invite, account, accepted=False)
                return invite
            if org.status == Organization.Status.ARCHIVED:
                raise DomainError("organization_archived", "Организация в архиве.")
            if Membership.objects.filter(organization=org, account=account,
                                         status=Membership.Status.ACTIVE).exists():
                raise Conflict("Вы уже в команде этой организации.", code="already_member")
            membership = Membership.objects.create(organization=org, account=account, role=invite.role,
                                                   invited_by=invite.invited_by)
            invite.status = OrganizationInvite.Status.ACCEPTED
            invite.account = account
            invite.responded_at = now
            invite.save(update_fields=["status", "account", "responded_at", "updated_at"])
            record(account, "invite.accepted", invite, organization=org,
                   after={"membership": str(membership.pk), "role": invite.role}, request=request)
            _inviter_notify(invite, account, accepted=True)
            return membership
    if problem == "expired":
        raise DomainError("invite_expired", "Срок действия приглашения истёк. Попросите отправить новое.")
    raise DomainError("invite_not_pending", "Приглашение уже не активно.")


def accept_invite(token, account, request=None):
    """Возвращает созданное членство."""
    return _respond(token, account, accept=True, request=request)


def decline_invite(token, account, request=None):
    return _respond(token, account, accept=False, request=request)


def expire_invites(now=None):
    """Celery (ежедневно): просроченные pending → expired."""
    now = now or timezone.now()
    return OrganizationInvite.objects.filter(status=OrganizationInvite.Status.PENDING, expires_at__lte=now).update(
        status=OrganizationInvite.Status.EXPIRED, updated_at=now)
