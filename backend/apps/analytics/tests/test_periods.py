"""Периоды отчётов (MET-08): даты включительно, ISO datetime, часовые пояса."""
import datetime as dt

import pytest
from zoneinfo import ZoneInfo

from apps.analytics.services.periods import resolve_period
from apps.common.exceptions import DomainError


def test_dates_are_inclusive_in_given_timezone():
    period = resolve_period({"from": "2026-10-01", "to": "2026-10-03", "tz": "Asia/Kamchatka"})
    tz = ZoneInfo("Asia/Kamchatka")
    assert period.start == dt.datetime(2026, 10, 1, tzinfo=tz)
    assert period.end == dt.datetime(2026, 10, 4, tzinfo=tz)
    assert period.as_dict()["to"] == "2026-10-03" and period.as_dict()["timezone"] == "Asia/Kamchatka"


def test_iso_datetime_with_offset_even_if_plus_was_lost_in_query_string():
    period = resolve_period({"from": "2026-10-01T10:00:00 03:00", "to": "2026-10-01T12:00:00+03:00"})
    assert period.start.utcoffset() == dt.timedelta(hours=3)
    assert (period.end - period.start) == dt.timedelta(hours=2)


def test_future_default_and_limits():
    period = resolve_period({}, future_days=30)
    assert round(period.days) == 30
    with pytest.raises(DomainError):
        resolve_period({"from": "2026-01-01", "to": "2026-06-01"}, max_days=93)
    with pytest.raises(DomainError):
        resolve_period({"from": "yesterday"})
