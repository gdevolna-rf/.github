from celery import shared_task

from apps.club.services.reminders import send_due_reminders


@shared_task(name="club.send_event_reminders")
def send_event_reminders():
    """Каждый час: напоминание за 24 ч до события — один раз на регистрацию; прошедшие события → «Прошло»."""
    return send_due_reminders()
