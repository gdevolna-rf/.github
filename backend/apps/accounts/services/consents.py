"""Журнал согласий (TRUST-09, ACC-13): каждая выдача/отзыв — отдельная запись с IP и user-agent."""
from apps.accounts.models import ConsentRecord, UserProfile
from apps.common.exceptions import DomainError

K = ConsentRecord.Kind

# Согласия, которые пользователь может менять в настройках. Отзыв terms/privacy = удаление аккаунта.
USER_MANAGED = {K.GG_SURFER, K.BIRTHDAY, K.GEOLOCATION, K.MARKETING}
REQUIRED = {K.TERMS, K.PRIVACY}

# Согласия, продублированные флагами профиля (BR-12, ACC-06, COM-05).
PROFILE_FLAGS = {K.GG_SURFER: "gg_surfer_enabled", K.BIRTHDAY: "birthday_greetings_consent"}


def client_meta(request):
    if request is None:
        return None, ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None
    return ip, (request.META.get("HTTP_USER_AGENT") or "")[:300]


def record_consent(account, kind, granted, request=None):
    ip, user_agent = client_meta(request)
    return ConsentRecord.objects.create(account=account, kind=kind, granted=bool(granted), ip=ip,
                                        user_agent=user_agent)


def current_consents(account):
    """Последнее решение по каждому виду согласия; отсутствие записи = не выдано."""
    state = {kind: False for kind in K.values}
    for kind, granted in account.consents.order_by("created_at", "id").values_list("kind", "granted"):
        state[kind] = granted
    return state


def set_consent(account, kind, granted, request=None):
    """Изменение согласия пользователем; синхронизирует флаги профиля."""
    if kind not in K.values:
        raise DomainError("consent_kind_invalid", "Неизвестный вид согласия.", fields={"kind": ["Недопустимое значение."]})
    if kind in REQUIRED:
        if not granted:
            raise DomainError("consent_required",
                              "Это согласие обязательно для использования сервиса. Чтобы отозвать его, "
                              "запросите удаление аккаунта в настройках.")
    elif kind not in USER_MANAGED:
        raise DomainError("consent_not_managed", "Это согласие оформляется в рамках бронирования.")
    record = record_consent(account, kind, granted, request)
    field = PROFILE_FLAGS.get(kind)
    if field:
        UserProfile.objects.filter(account=account).update(**{field: bool(granted)})
    return record
