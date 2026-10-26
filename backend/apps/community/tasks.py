from celery import shared_task

from apps.community.services.birthdays import send_birthday_greetings as _send


@shared_task(name="community.send_birthday_greetings")
def send_birthday_greetings(today=None):
    """Ежедневно 09:00 (Europe/Moscow): поздравления только при согласии, без раскрытия даты (COM-05, ATX-34)."""
    return _send(today=today)
