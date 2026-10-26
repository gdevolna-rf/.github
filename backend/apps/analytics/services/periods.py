"""Периоды отчётов и расписаний (MET-08): границы в часовом поясе, даты включительно, ISO 8601 с timezone."""
import datetime as dt
import re
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apps.common.exceptions import DomainError

_PLUS_LOST = re.compile(r"(T[\d:.]+) (\d{2}:?\d{2})$")


@dataclass(frozen=True)
class Period:
    start: dt.datetime  # включительно
    end: dt.datetime  # не включительно
    tz: ZoneInfo

    @property
    def date_from(self):
        return self.start.astimezone(self.tz).date()

    @property
    def date_to(self):
        """Последний день периода (включительно)."""
        return (self.end - dt.timedelta(microseconds=1)).astimezone(self.tz).date()

    @property
    def days(self):
        return max((self.end - self.start).total_seconds() / 86400, 0)

    def as_dict(self):
        return {
            "from": self.date_from.isoformat(),
            "to": self.date_to.isoformat(),
            "timezone": str(self.tz.key),
            "starts_at": self.start.astimezone(self.tz).isoformat(),
            "ends_at": self.end.astimezone(self.tz).isoformat(),
        }


def get_tz(name=None, field="tz"):
    try:
        return ZoneInfo(name or settings.TIME_ZONE)
    except (ZoneInfoNotFoundError, ValueError):
        raise DomainError("validation_error", "Неизвестный часовой пояс.",
                          fields={field: ["Укажите IANA-зону, например Europe/Moscow."]}) from None


def parse_bound(value, field, tz, *, end=False):
    """Дата YYYY-MM-DD (для конца — включительно, т.е. до начала следующего дня) или ISO datetime."""
    value = (value or "").strip()
    if not value:
        return None
    error = DomainError("validation_error", "Неверный формат даты.",
                        fields={field: ["Ожидается дата YYYY-MM-DD или дата-время ISO 8601."]})
    try:
        if len(value) == 10:
            day = parse_date(value)
            if day is None:
                raise error
            start = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
            return start + dt.timedelta(days=1) if end else start
        # «+03:00» в query string без кодирования превращается в пробел.
        moment = parse_datetime(_PLUS_LOST.sub(r"\1+\2", value))
    except ValueError:
        raise error from None
    if moment is None:
        raise error
    if timezone.is_naive(moment):
        moment = moment.replace(tzinfo=tz)
    return moment


def resolve_period(params, *, past_days=None, future_days=None, max_days=366, tz=None, from_key="from", to_key="to"):
    """Период из query-параметров. По умолчанию: past_days дней до конца сегодняшнего дня либо
    future_days дней с начала сегодняшнего дня."""
    tz = tz or get_tz(params.get("tz"))
    start = parse_bound(params.get(from_key), from_key, tz)
    end = parse_bound(params.get(to_key), to_key, tz, end=True)
    today_start = dt.datetime.combine(timezone.now().astimezone(tz).date(), dt.time.min, tzinfo=tz)
    span = dt.timedelta(days=past_days or future_days or 30)
    if start is None and end is None:
        if future_days:
            start, end = today_start, today_start + span
        else:
            end = today_start + dt.timedelta(days=1)
            start = end - span
    elif start is None:
        start = end - span
    elif end is None:
        end = start + span
    if end <= start:
        raise DomainError("validation_error", "Конец периода должен быть позже начала.",
                          fields={to_key: ["Конец периода раньше начала."]})
    if (end - start) > dt.timedelta(days=max_days):
        raise DomainError("validation_error", f"Период не может быть длиннее {max_days} дней.",
                          fields={to_key: [f"Максимум {max_days} дней."]})
    return Period(start=start, end=end, tz=tz)
