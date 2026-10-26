from celery import shared_task


@shared_task(name="organizations.send_invite_email", autoretry_for=(OSError, ConnectionError), retry_backoff=True,
             max_retries=5)
def send_invite_email(invite_id):
    from django.conf import settings

    from apps.accounts.services.mail import send_templated_mail
    from apps.organizations.models import OrganizationInvite

    invite = OrganizationInvite.objects.select_related("organization", "invited_by__profile").filter(
        pk=invite_id, status=OrganizationInvite.Status.PENDING).first()
    if invite is None:
        return False
    inviter = getattr(invite.invited_by, "profile", None)
    send_templated_mail(invite.email, "organizations/email/invite", {
        "inviter": inviter.display_name if inviter else "Команда",
        "organization": invite.organization.name,
        "kind": invite.organization.get_kind_display(),
        "role": invite.get_role_display(),
        "message": invite.message,
        "email": invite.email,
        "has_account": invite.account_id is not None,
        "expires_at": invite.expires_at,
        "link": f"{settings.SITE_URL}/invites/{invite.token}",
    })
    return True


@shared_task(name="organizations.expire_invites")
def expire_invites():
    """Ежедневно: просроченные приглашения → expired."""
    from apps.organizations.services.invites import expire_invites as run

    return run()
