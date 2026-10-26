from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_notification_email(self, notification_id):
    from apps.messaging.models import Notification

    notification = Notification.objects.select_related("recipient").filter(id=notification_id).first()
    if notification is None or notification.email_sent_at:
        return
    link = f"{settings.SITE_URL}{notification.link}" if notification.link else settings.SITE_URL
    send_mail(
        subject=f"ГДеволна: {notification.title}",
        message=f"{notification.body}\n\n{link}".strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[notification.recipient.email],
    )
    Notification.objects.filter(id=notification_id).update(email_sent_at=timezone.now())
