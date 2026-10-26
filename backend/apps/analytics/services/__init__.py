"""Запись событий аналитики (раздел 10). Бизнес-факты пишутся из завершённых транзакций, а не из кликов."""
import re

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.analytics.models import RULE_VERSION, AnalyticsEvent

_BOT_RE = re.compile(r"bot|crawl|spider|slurp|headless|lighthouse|preview", re.I)


def is_bot(request):
    if request is None:
        return False
    return bool(_BOT_RE.search(request.META.get("HTTP_USER_AGENT", "")))


def anonymous_id(request):
    if request is None:
        return ""
    return request.COOKIES.get("gv_aid", "") or (request.session.session_key or "")


def track(name, *, subject_type, subject_id, actor=None, owner_account=None, owner_organization=None,
          context=None, dedup_key=None, request=None, occurred_at=None, anon_id=None):
    """Пишет событие ровно один раз (по dedup_key, если задан). Возвращает событие или None.

    anon_id — явный анонимный идентификатор зрителя (например, только что выданная cookie gv_aid)."""
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    try:
        with transaction.atomic():
            return AnalyticsEvent.objects.create(
                name=name,
                actor=actor,
                anonymous_id=(anon_id or anonymous_id(request))[:64] if actor is None else "",
                subject_type=subject_type,
                subject_id=str(subject_id),
                owner_account=owner_account,
                owner_organization=owner_organization,
                context=context or {},
                dedup_key=dedup_key,
                rule_version=RULE_VERSION,
                occurred_at=occurred_at or timezone.now(),
            )
    except IntegrityError:
        return None


def track_view(name, request, *, subject_type, subject_id, owner_account=None, owner_organization=None, context=None,
               anon_id=None):
    """Квалифицированный просмотр (10, MET-08): без ботов, самопросмотров и повторов зрителя за сутки."""
    if is_bot(request):
        return None
    user = request.user if request.user.is_authenticated else None
    if user is not None and owner_account is not None and user.pk == owner_account.pk:
        return None
    if user is not None and owner_organization is not None:
        from apps.organizations.services.access import is_member

        if is_member(user, owner_organization):
            return None
    viewer = f"a:{user.pk}" if user else f"s:{anon_id or anonymous_id(request)}"
    if viewer == "s:":
        return None
    day = timezone.localdate().isoformat()
    dedup = f"v{RULE_VERSION}:{name}:{subject_type}:{subject_id}:{viewer}:{day}"
    return track(name, subject_type=subject_type, subject_id=subject_id, actor=user, owner_account=owner_account,
                 owner_organization=owner_organization, context=context, dedup_key=dedup, request=request,
                 anon_id=anon_id)
