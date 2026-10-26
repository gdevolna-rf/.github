"""Скорость и загрузка модерации (TRUST-04, раздел 10: spot_proposal_reviewed)."""
import datetime as dt
import statistics

from django.db.models import Count
from django.utils import timezone

from apps.analytics.models import AnalyticsEvent
from apps.trust.models import ModerationCase

OPEN = [ModerationCase.Status.OPEN, ModerationCase.Status.IN_REVIEW]


def _by_kind(qs):
    counts = {kind: 0 for kind in ModerationCase.Kind.values}
    for row in qs.values("kind").annotate(n=Count("id")):
        counts[row["kind"]] = row["n"]
    return counts


def moderation_stats(days=30, now=None):
    now = now or timezone.now()
    open_cases = ModerationCase.objects.filter(status__in=OPEN)
    overdue = open_cases.filter(due_at__lt=now)
    since = now - dt.timedelta(days=days)
    events = AnalyticsEvent.objects.filter(name=AnalyticsEvent.Name.SPOT_PROPOSAL_REVIEWED, occurred_at__gte=since)
    hours = [float(e["context"]["hours_from_submitted"]) for e in events.values("context")
             if isinstance(e["context"], dict) and e["context"].get("hours_from_submitted") is not None]
    decisions = {"approved": 0, "rejected": 0}
    for e in events.values("context"):
        decision = (e["context"] or {}).get("decision")
        if decision in decisions:
            decisions[decision] += 1
    open_by_kind, overdue_by_kind = _by_kind(open_cases), _by_kind(overdue)
    oldest = open_cases.order_by("created_at").values_list("created_at", flat=True).first()
    return {
        "generated_at": now,
        "open_cases": {"total": sum(open_by_kind.values()), "by_kind": open_by_kind},
        "overdue_cases": {"total": sum(overdue_by_kind.values()), "by_kind": overdue_by_kind},
        "oldest_open_case_hours": round((now - oldest).total_seconds() / 3600, 1) if oldest else None,
        "spot_proposals": {
            "period_days": days,
            "decided": len(hours),
            "approved": decisions["approved"],
            "rejected": decisions["rejected"],
            "median_hours_to_decision": round(statistics.median(hours), 2) if hours else None,
        },
        "resolved_last_period": ModerationCase.objects.filter(status=ModerationCase.Status.RESOLVED,
                                                              resolved_at__gte=since).count(),
    }
