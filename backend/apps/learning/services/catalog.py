"""Публичный каталог инструкторов (INS-01…03, INS-09, BR-01): фильтры, бейдж сертификата, цена «от», свободные окна."""
import datetime as dt
from decimal import Decimal, InvalidOperation

from django.db.models import Case, CharField, DecimalField, Exists, F, Min, OuterRef, Prefetch, Q, Subquery, Value, When
from django.db.models.functions import Least
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.common.exceptions import DomainError
from apps.learning.models import InstructorCertificate, InstructorOffer, InstructorProfile, LessonSession
from apps.learning.services.common import suspended_exists, with_seats
from apps.organizations.models import Membership, Organization
from apps.spots.models import Spot

C = InstructorCertificate.Status
ORDERINGS = {
    "rating": ("-rating_avg", "-rating_count"),
    "reviews": ("-rating_count", "-rating_avg"),
    "price": (F("effective_price").asc(nulls_last=True), "-rating_avg"),
    "experience": (F("teaching_since").asc(nulls_last=True), "-rating_avg"),
    "newest": ("-published_at",),
}
DEFAULT_ORDERING = ("-rating_avg", "-rating_count", "-published_at")


def _cert_status_annotation():
    today = timezone.localdate()
    valid = Q(valid_until__isnull=True) | Q(valid_until__gte=today)
    verified = InstructorCertificate.objects.filter(instructor=OuterRef("pk"), status=C.VERIFIED).filter(valid)
    uploaded = InstructorCertificate.objects.filter(instructor=OuterRef("pk"), status__in=[C.UPLOADED, C.VERIFIED])
    return Case(
        When(Exists(verified), then=Value("verified")),
        When(Exists(uploaded), then=Value("uploaded")),
        default=Value("none"), output_field=CharField(),
    )


def _min_offer_price():
    prices = (InstructorOffer.objects.filter(instructor=OuterRef("pk"), is_active=True).order_by()
              .values("instructor").annotate(m=Min("price")).values("m")[:1])
    return Subquery(prices, output_field=DecimalField(max_digits=10, decimal_places=2))


def bookable_sessions(now=None):
    """Занятия, на которые можно записаться: запланированные, в будущем, публичные (школа опубликована или
    частный урок опубликованного инструктора)."""
    now = now or timezone.now()
    return LessonSession.objects.filter(status=LessonSession.Status.SCHEDULED, starts_at__gt=now).filter(
        Q(organization__isnull=False, organization__kind=Organization.Kind.SCHOOL,
          organization__status=Organization.Status.PUBLISHED)
        | Q(organization__isnull=True, offer__isnull=False, offer__instructor__in=public_profiles())
    )


def free_sessions():
    return with_seats(bookable_sessions()).filter(free_seats_db__gt=0)


def public_profiles():
    """Публичные карточки инструкторов — единое правило для каталога, поиска, избранного, помощника и записи
    на частные слоты: опубликована, аккаунт активен, не удаляется и не ограничен модератором."""
    return (InstructorProfile.objects
            .filter(status=InstructorProfile.Status.PUBLISHED, account__is_active=True,
                    account__anonymized_at__isnull=True, account__deletion_requested_at__isnull=True)
            .exclude(suspended_exists("account_id")))


def is_profile_public(profile):
    return public_profiles().filter(pk=profile.pk).exists()


def school_memberships_prefetch():
    return Prefetch(
        "account__memberships",
        queryset=Membership.objects.filter(
            status=Membership.Status.ACTIVE, organization__kind=Organization.Kind.SCHOOL,
            organization__status=Organization.Status.PUBLISHED,
        ).select_related("organization").order_by("organization__name"),
        to_attr="public_school_memberships",
    )


def annotated(queryset):
    return (queryset
            .annotate(cert_status=_cert_status_annotation(), min_offer_price=_min_offer_price())
            .annotate(effective_price=Least("price_from", "min_offer_price"))
            .select_related("account__profile__avatar")
            .prefetch_related(
                "regions",
                Prefetch("spots", queryset=Spot.objects.filter(status=Spot.Status.PUBLISHED)
                         .select_related("region").order_by("name")),
                school_memberships_prefetch(),
            ))


def _decimal(value, field):
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError):
        raise DomainError("validation_error", "Неверное число.", fields={field: ["Ожидается число."]}) from None
    if number < 0:
        raise DomainError("validation_error", "Значение не может быть отрицательным.", fields={field: ["Меньше нуля."]})
    return number


def filter_catalog(queryset, params):
    """region, spot, level, board_type, format, price_max, certificate, date (+tz), rating_min, q, ordering."""
    from apps.analytics.services.periods import get_tz
    from apps.spots.models import Region

    region = params.get("region")
    if region:
        queryset = queryset.filter(Q(regions__slug=region) | Q(spots__region__slug=region))
    spot = params.get("spot")
    if spot:
        queryset = queryset.filter(Q(spots__slug=spot) | Q(offers__is_active=True, offers__spot__slug=spot))
    level = params.get("level")
    if level:
        queryset = queryset.filter(Q(student_levels__contains=[level]) | Q(offers__is_active=True, offers__level=level))
    board_type = params.get("board_type")
    if board_type:
        queryset = queryset.filter(board_types__contains=[board_type])
    fmt = params.get("format")
    if fmt:
        queryset = queryset.filter(Q(formats__contains=[fmt]) | Q(offers__is_active=True, offers__format=fmt))
    price_max = params.get("price_max")
    if price_max not in (None, ""):
        queryset = queryset.filter(effective_price__lte=_decimal(price_max, "price_max"))
    certificate = params.get("certificate")
    if certificate:
        allowed = {"verified": ["verified"], "uploaded": ["uploaded", "verified"], "none": ["none"], "any": None}
        if certificate not in allowed:
            raise DomainError("validation_error", "Неизвестное значение фильтра сертификата.",
                              fields={"certificate": ["Допустимо: verified, uploaded, none, any."]})
        if allowed[certificate]:
            queryset = queryset.filter(cert_status__in=allowed[certificate])
    rating_min = params.get("rating_min")
    if rating_min not in (None, ""):
        queryset = queryset.filter(rating_avg__gte=_decimal(rating_min, "rating_min"), rating_count__gt=0)
    day = params.get("date")
    if day:
        parsed = parse_date(day) if len(day) == 10 else None
        if parsed is None:
            raise DomainError("validation_error", "Неверная дата.", fields={"date": ["Ожидается YYYY-MM-DD."]})
        tz_name = params.get("tz")
        if not tz_name and region:
            tz_name = Region.objects.filter(slug=region).values_list("timezone", flat=True).first()
        tz = get_tz(tz_name)
        start = dt.datetime.combine(parsed, dt.time.min, tzinfo=tz)
        slots = free_sessions().filter(instructor_id=OuterRef("account_id"), starts_at__gte=start,
                                       starts_at__lt=start + dt.timedelta(days=1))
        queryset = queryset.filter(Exists(slots))
    q = (params.get("q") or "").strip()
    if q:
        queryset = queryset.filter(
            Q(account__profile__first_name__icontains=q) | Q(account__profile__last_name__icontains=q)
            | Q(account__profile__handle__icontains=q) | Q(headline__icontains=q) | Q(about__icontains=q)
        )
    ordering = params.get("ordering")
    if ordering and ordering not in ORDERINGS:
        raise DomainError("validation_error", "Неизвестная сортировка.",
                          fields={"ordering": [f"Допустимо: {', '.join(ORDERINGS)}."]})
    return queryset.distinct().order_by(*(ORDERINGS.get(ordering) or DEFAULT_ORDERING), "pk")


def upcoming_free_slots(profile, limit=30):
    """Свободные окна: частные занятия по предложениям и занятия школ, где инструктор ведёт урок."""
    return list(free_sessions().filter(instructor_id=profile.account_id)
                .select_related("spot__region", "organization__region", "program", "offer",
                                "instructor__profile__avatar", "instructor__instructor_profile")
                .order_by("starts_at")[:limit])
