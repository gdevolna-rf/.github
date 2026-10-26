"""Регистрирует периодические задачи в django-celery-beat (docs/ARCHITECTURE.md §5). Идемпотентна."""
import json

from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask

# (имя задачи Celery, тип, параметры расписания). Задачи объявляются с явным name="<app>.<task>".
SCHEDULE = [
    ("mediafiles.cleanup_expired_uploads", "interval", {"every": 1, "period": IntervalSchedule.HOURS}),
    ("commerce.expire_stale_booking_requests", "interval", {"every": 15, "period": IntervalSchedule.MINUTES}),
    ("commerce.mark_overdue_rentals", "interval", {"every": 15, "period": IntervalSchedule.MINUTES}),
    ("learning.send_lesson_reminders", "interval", {"every": 1, "period": IntervalSchedule.HOURS}),
    ("club.send_event_reminders", "interval", {"every": 1, "period": IntervalSchedule.HOURS}),
    ("community.send_birthday_greetings", "crontab", {"minute": "0", "hour": "9"}),
    ("accounts.process_deletion_requests", "crontab", {"minute": "0", "hour": "3"}),
    ("organizations.expire_invites", "crontab", {"minute": "30", "hour": "3"}),
    ("trust.recalculate_ratings", "crontab", {"minute": "0", "hour": "4"}),
    ("spots.refresh_forecasts", "interval", {"every": 3, "period": IntervalSchedule.HOURS}),
]


class Command(BaseCommand):
    help = "Создаёт/обновляет расписания периодических задач."

    def handle(self, *args, **options):
        for task, kind, params in SCHEDULE:
            defaults = {"task": task, "kwargs": json.dumps({}), "enabled": True, "interval": None, "crontab": None}
            if kind == "interval":
                defaults["interval"], _ = IntervalSchedule.objects.get_or_create(**params)
            else:
                defaults["crontab"], _ = CrontabSchedule.objects.get_or_create(
                    day_of_week="*", day_of_month="*", month_of_year="*", timezone="Europe/Moscow", **params
                )
            PeriodicTask.objects.update_or_create(name=task, defaults=defaults)
        self.stdout.write(self.style.SUCCESS(f"periodic tasks: {len(SCHEDULE)}"))
