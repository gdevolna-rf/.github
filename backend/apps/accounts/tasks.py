from celery import shared_task

RETRY = dict(autoretry_for=(OSError, ConnectionError), retry_backoff=True, max_retries=5)


def _account(account_id):
    from apps.accounts.models import Account

    return Account.objects.select_related("profile").filter(pk=account_id, is_active=True,
                                                             anonymized_at__isnull=True).first()


def _name(account):
    profile = getattr(account, "profile", None)
    return profile.first_name if profile else ""


@shared_task(name="accounts.send_verification_email", **RETRY)
def send_verification_email(account_id):
    from apps.accounts.services.mail import send_templated_mail
    from apps.accounts.services.tokens import email_verification_ttl, verification_link

    account = _account(account_id)
    if account is None or account.is_email_verified:
        return False
    send_templated_mail(account.email, "accounts/email/verify_email", {
        "name": _name(account), "email": account.email, "link": verification_link(account),
        "ttl_hours": email_verification_ttl() // 3600,
    })
    return True


@shared_task(name="accounts.send_password_reset_email", **RETRY)
def send_password_reset_email(account_id):
    from apps.accounts.services.mail import send_templated_mail
    from apps.accounts.services.tokens import password_reset_link

    account = _account(account_id)
    if account is None:
        return False
    send_templated_mail(account.email, "accounts/email/password_reset", {
        "name": _name(account), "email": account.email, "link": password_reset_link(account),
    })
    return True


@shared_task(name="accounts.send_deletion_scheduled_email", **RETRY)
def send_deletion_scheduled_email(deletion_id):
    from apps.accounts.models import AccountDeletionRequest
    from apps.accounts.services.mail import send_templated_mail

    deletion = AccountDeletionRequest.objects.select_related("account__profile").filter(
        pk=deletion_id, status=AccountDeletionRequest.Status.REQUESTED).first()
    if deletion is None:
        return False
    send_templated_mail(deletion.account.email, "accounts/email/deletion_scheduled", {
        "name": _name(deletion.account), "scheduled_for": deletion.scheduled_for,
    })
    return True


@shared_task(name="accounts.build_data_export")
def build_data_export(export_id):
    from apps.accounts.services.exports import build_export

    return build_export(export_id)


@shared_task(name="accounts.process_deletion_requests")
def process_deletion_requests():
    """Ежедневно 03:00: анонимизация аккаунтов, у которых истекла отсрочка удаления (AT-10)."""
    from apps.accounts.services.deletion import process_due_requests

    return process_due_requests()
