"""Поздравления с днём рождения от имени проекта (COM-05, F12, ATX-34).

Только при согласии birthday_greetings_consent; один раз в год (BirthdayGreeting уникален по аккаунту и году);
текст не содержит ни даты рождения, ни возраста. «Сегодня» — по Москве (TIME_ZONE); родившимся 29 февраля
в невисокосный год поздравление приходит 28 февраля.
"""
import calendar
import datetime as dt
import logging

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.community.models import BirthdayGreeting
from apps.messaging.models import Notification
from apps.messaging.services.notify import notify

logger = logging.getLogger(__name__)

TITLE = "С днём рождения от ГДеволна!"
BODY = ("Команда ГДеволна поздравляет вас с днём рождения! Пусть в новом году будет больше хороших волн, "
        "тёплой воды и своих людей на берегу.")
LINK = "/account"


def _birthday_q(today):
    q = Q(birth_date__month=today.month, birth_date__day=today.day)
    if today.month == 2 and today.day == 28 and not calendar.isleap(today.year):
        q |= Q(birth_date__month=2, birth_date__day=29)
    return q


def due_profiles(today):
    return (UserProfile.objects
            .filter(birthday_greetings_consent=True, birth_date__isnull=False,
                    account__is_active=True, account__anonymized_at__isnull=True)
            .filter(_birthday_q(today))
            .exclude(account__in=BirthdayGreeting.objects.filter(year=today.year).values("account"))
            .select_related("account"))


def send_birthday_greetings(today=None):
    """Возвращает число отправленных поздравлений. Повторный запуск в тот же год ничего не дублирует."""
    today = today or timezone.localdate()
    if isinstance(today, str):
        today = dt.date.fromisoformat(today)
    sent = 0
    for profile in due_profiles(today):
        account = profile.account
        try:
            with transaction.atomic():
                BirthdayGreeting.objects.create(account=account, year=today.year)
                notify(account, Notification.Kind.BIRTHDAY, TITLE, body=BODY, link=LINK,
                       event_id=f"birthday:{today.year}")
        except IntegrityError:
            continue  # уже поздравили (параллельный запуск)
        sent += 1
    logger.info("birthday greetings sent: %s", sent)
    return sent
