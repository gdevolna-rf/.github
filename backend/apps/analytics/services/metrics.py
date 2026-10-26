"""Метрики дашбордов (раздел 10.1, MET-01…07, INS-10, SCH-12).

Источник — серверные события аналитики (квалифицированные просмотры) и транзакционные таблицы (брони, обращения,
отзывы). Клиентские числа не используются. Деньги — только amount_confirmed завершённых сделок (MET-07, ATX-29).
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Avg, Count, DurationField, Exists, ExpressionWrapper, F, OuterRef, Q, Sum, Value
from django.db.models.functions import Coalesce, Greatest, Least
from django.utils import timezone

from apps.accounts.models import Specialty
from apps.accounts.services.specialties import has_specialty
from apps.analytics.models import RULE_VERSION, AnalyticsEvent
from apps.boards.models import BoardModel, BoardType
from apps.commerce.models import Booking, Inquiry
from apps.common.exceptions import DomainError, Forbidden, NotFound
from apps.inventory.models import InventoryItem
from apps.learning.models import InstructorProfile, LessonSession, SchoolProgram
from apps.organizations.models import Membership, Organization
from apps.trust.models import Review

B = Booking.Status
SEAT_STATUSES = (B.CONFIRMED, B.IN_PROGRESS, B.COMPLETED, B.NO_SHOW)
RENTAL_ACTIVE = (B.CONFIRMED, B.IN_PROGRESS, B.COMPLETED)
STAFF_ROLES = (Membership.Role.OWNER, Membership.Role.MANAGER, Membership.Role.STAFF)
SCOPES = ("shaper", "instructor", "school", "rental", "surfer")


# --- helpers ---------------------------------------------------------------------------------------------------

def metric(key, label, value, unit, formula, currency=None):
    return {"key": key, "label": label, "value": value, "unit": unit, "formula": formula, "currency": currency}


def pct(num, den):
    return round(num * 100 / den, 1) if den else None


def money(value):
    return f"{(value or Decimal('0')).quantize(Decimal('0.01'))}"


def in_period(field, period):
    return {f"{field}__gte": period.start, f"{field}__lt": period.end}


def revenue_rows(qs, amount_field):
    """[{currency, amount, deals, average}] — только подтверждённые суммы."""
    rows = (qs.order_by().values("currency")
            .annotate(amount=Sum(amount_field), deals=Count("id"), average=Avg(amount_field)).order_by("currency"))
    return [{"currency": r["currency"], "amount": money(r["amount"]), "deals": r["deals"],
             "average": money(r["average"])} for r in rows]


def main_currency(rows, default="RUB"):
    for row in rows:
        if row["currency"] == default:
            return row
    return rows[0] if rows else {"currency": default, "amount": money(0), "deals": 0, "average": None}


def repeat_stats(completed_bookings):
    per_student = list(completed_bookings.order_by().values("customer_id").annotate(n=Count("id")))
    unique = len(per_student)
    repeat = sum(1 for r in per_student if r["n"] >= 2)
    return unique, repeat, pct(repeat, unique)


def cancellation_stats(bookings):
    considered = bookings.exclude(status=B.DECLINED)
    total = considered.count()
    cancelled = considered.filter(status=B.CANCELLED)
    by_side = {side: 0 for side in Booking.Side.values}
    for row in cancelled.order_by().values("cancelled_side").annotate(n=Count("id")):
        by_side[row["cancelled_side"] or "system"] = by_side.get(row["cancelled_side"] or "system", 0) + row["n"]
    return cancelled.count(), total, by_side


def org_brief(org):
    return {"id": str(org.pk), "slug": org.slug, "name": org.name, "kind": org.kind}


def account_brief(account):
    from apps.accounts.serializers_public import PublicAccountSerializer

    return PublicAccountSerializer(account).data


# --- выбор субъекта (права: владелец / сотрудники организации) -------------------------------------------------

def _member_orgs(account, kind, roles=STAFF_ROLES):
    return list(Organization.objects.filter(
        kind=kind, memberships__account=account, memberships__status=Membership.Status.ACTIVE,
        memberships__role__in=roles,
    ).distinct().order_by("name"))


def _requested_org(account, organization_id, kinds, roles=STAFF_ROLES):
    org = Organization.objects.filter(pk=organization_id).first()
    if org is None:
        raise NotFound("Организация не найдена.")
    membership = Membership.objects.filter(organization=org, account=account, status=Membership.Status.ACTIVE).first()
    if membership is None or membership.role not in roles:
        raise Forbidden("Статистика организации доступна владельцу и сотрудникам.")
    if kinds and org.kind not in kinds:
        raise DomainError("scope_mismatch", "Эта организация не подходит для выбранного раздела статистики.",
                          fields={"organization_id": ["Другой тип организации."]})
    return org


def _unavailable(message):
    raise Forbidden(message, code="scope_unavailable")


# --- шейпер (MET-03) -------------------------------------------------------------------------------------------

def shaper_metrics(account, organization_id, period):
    if organization_id:
        orgs = [_requested_org(account, organization_id, [Organization.Kind.WORKSHOP])]
    else:
        orgs = _member_orgs(account, Organization.Kind.WORKSHOP)
    if not orgs:
        _unavailable("Статистика шейпера появится после создания мастерской.")
    org_ids = [o.pk for o in orgs]
    views = AnalyticsEvent.objects.filter(name=AnalyticsEvent.Name.BOARD_VIEWED, owner_organization_id__in=org_ids,
                                          **in_period("occurred_at", period))
    total_views = views.count()
    model_views = views.filter(subject_type="board_model").count()
    variant_views = views.filter(subject_type="board_variant").count()
    published_models = BoardModel.objects.filter(workshop_id__in=org_ids, status=BoardModel.Status.PUBLISHED).count()

    inquiries = Inquiry.objects.filter(provider_organization_id__in=org_ids, **in_period("created_at", period))
    I = Inquiry.Status
    total_inquiries = inquiries.count()
    active = inquiries.filter(status__in=[I.NEW, I.IN_PROGRESS]).count()
    unique_clients = inquiries.values("customer_id").distinct().count()
    catalog_inquiries = inquiries.filter(Q(board_model__isnull=False) | Q(board_variant__isnull=False)).annotate(
        model_ref=Coalesce("board_model_id", "board_variant__model_id"))
    unique_catalog = catalog_inquiries.values("customer_id", "model_ref").distinct().count()

    deals = (Inquiry.objects.filter(provider_organization_id__in=org_ids, status=I.COMPLETED)
             .annotate(closed=Coalesce("closed_at", "updated_at")).filter(**in_period("closed", period)))
    completed = deals.count()
    confirmed = deals.filter(amount_confirmed=True, agreed_amount__isnull=False)
    revenue = revenue_rows(confirmed, "agreed_amount")
    main = main_currency(revenue)
    sales = deals.filter(kind__in=[Inquiry.Kind.BOARD_PURCHASE, Inquiry.Kind.CUSTOM_ORDER]).count()
    repairs = deals.filter(kind=Inquiry.Kind.REPAIR).count()
    rentals = Booking.objects.filter(kind=Booking.Kind.RENTAL, provider_organization_id__in=org_ids,
                                     status__in=RENTAL_ACTIVE, **in_period("starts_at", period)).count()

    type_names = dict(BoardType.objects.filter(Q(workshop__isnull=True) | Q(workshop_id__in=org_ids))
                      .values_list("code", "name"))
    interest = defaultdict(lambda: {"views": 0, "inquiries": 0})
    for row in views.order_by().values("context__board_type").annotate(n=Count("id")):
        interest[row["context__board_type"] or "unknown"]["views"] += row["n"]
    type_inquiries = catalog_inquiries.annotate(
        type_code=Coalesce("board_model__board_type__code", "board_variant__model__board_type__code"))
    for row in type_inquiries.order_by().values("type_code").annotate(n=Count("id")):
        interest[row["type_code"] or "unknown"]["inquiries"] += row["n"]
    by_type = sorted(({"board_type": code, "name": type_names.get(code, code), **vals} for code, vals in interest.items()),
                     key=lambda r: (-r["views"], -r["inquiries"], r["board_type"]))
    status_rows = {s: 0 for s in I.values}
    for row in inquiries.order_by().values("status").annotate(n=Count("id")):
        status_rows[row["status"]] = row["n"]

    metrics = [
        metric("published_models", "Опубликованных моделей", published_models, "count",
               "Модели досок мастерской в статусе «опубликована» на текущий момент"),
        metric("model_views", "Просмотры моделей", total_views, "count",
               "Квалифицированные board_viewed за период (без ботов, самопросмотров, повторов зрителя за сутки)"),
        metric("inquiries", "Обращения", total_inquiries, "count", "Обращения к мастерской, созданные за период"),
        metric("inquiries_active", "Активные обращения", active, "count",
               "Обращения периода в статусах «новое» и «в работе»"),
        metric("inquiries_completed", "Завершённые сделки", completed, "count",
               "Обращения, завершённые за период (статус completed)"),
        metric("unique_clients", "Уникальные клиенты", unique_clients, "count",
               "Число разных клиентов, создавших обращения за период"),
        metric("conversion", "Конверсия просмотр → обращение", pct(unique_catalog, total_views), "percent",
               "Уникальные обращения из каталога (клиент × модель) / квалифицированные просмотры × 100%"),
        metric("sales", "Продажи", sales, "count",
               "Завершённые за период сделки «покупка доски» и «индивидуальное изготовление»"),
        metric("repairs", "Ремонты", repairs, "count", "Завершённые за период обращения на ремонт"),
        metric("rentals", "Аренда", rentals, "count",
               "Подтверждённые/выданные/завершённые брони аренды мастерской с началом в периоде"),
        metric("revenue_confirmed", "Подтверждённая выручка", main["amount"], "money",
               "Сумма agreed_amount завершённых за период сделок с amount_confirmed=true; заявки без "
               "подтверждённой суммы не учитываются", currency=main["currency"]),
        metric("average_check", "Средний чек", main["average"] if main["deals"] else None, "money",
               "Подтверждённая выручка / число сделок с подтверждённой суммой", currency=main["currency"]),
    ]
    breakdowns = {
        "interest_by_board_type": by_type,
        "views_by_subject": {"board_model": model_views, "board_variant": variant_views},
        "inquiries_by_status": status_rows,
        "revenue_by_currency": revenue,
        "deals_unconfirmed": completed - confirmed.count(),
    }
    return {"organizations": [org_brief(o) for o in orgs]}, metrics, breakdowns


# --- инструктор (MET-04, INS-10) -------------------------------------------------------------------------------

def _rating(qs):
    agg = qs.filter(status=Review.Status.PUBLISHED).aggregate(avg=Avg("rating"), n=Count("id"))
    return (round(float(agg["avg"]), 2) if agg["avg"] is not None else None), agg["n"]


def instructor_metrics(account, organization_id, period):
    profile = InstructorProfile.objects.filter(account=account).first()
    if profile is None and not LessonSession.objects.filter(instructor=account).exists():
        _unavailable("Статистика инструктора появится после создания карточки или первого занятия.")
    views = AnalyticsEvent.objects.filter(name=AnalyticsEvent.Name.PROFILE_VIEWED, subject_type="instructor",
                                          owner_account=account, **in_period("occurred_at", period)).count()
    lesson_bookings = Booking.objects.filter(kind=Booking.Kind.LESSON, lesson_session__instructor=account)
    created = lesson_bookings.filter(**in_period("created_at", period))
    confirmed_count = lesson_bookings.filter(**in_period("confirmed_at", period)).count()
    inquiries = Inquiry.objects.filter(provider_account=account, **in_period("created_at", period))
    leads = set(inquiries.values_list("customer_id", flat=True)) | set(
        created.filter(lesson_session__organization__isnull=True).values_list("customer_id", flat=True))

    period_bookings = lesson_bookings.filter(**in_period("lesson_session__starts_at", period))
    unique, repeat, repeat_pct = repeat_stats(period_bookings.filter(status=B.COMPLETED))
    sessions = LessonSession.objects.filter(instructor=account, **in_period("starts_at", period))
    held = sessions.exclude(status=LessonSession.Status.CANCELLED)
    completed_lessons = sessions.filter(status=LessonSession.Status.COMPLETED).count()
    capacity = held.aggregate(n=Sum("capacity"))["n"] or 0
    seats = period_bookings.filter(status__in=SEAT_STATUSES).exclude(
        lesson_session__status=LessonSession.Status.CANCELLED).aggregate(n=Sum("seats"))["n"] or 0
    cancelled, considered, by_side = cancellation_stats(period_bookings)
    rating_avg, rating_count = _rating(Review.objects.filter(instructor=profile)) if profile else (None, 0)

    by_org = []
    rows = (held.order_by().values("organization_id")
            .annotate(sessions=Count("id"), capacity=Sum("capacity"),
                      completed=Count("id", filter=Q(status=LessonSession.Status.COMPLETED))))
    orgs = {o.pk: o for o in Organization.objects.filter(pk__in=[r["organization_id"] for r in rows if r["organization_id"]])}
    seat_rows = dict(period_bookings.filter(status__in=SEAT_STATUSES).exclude(
        lesson_session__status=LessonSession.Status.CANCELLED).order_by()
        .values_list("lesson_session__organization_id").annotate(n=Sum("seats")))
    for r in rows:
        org = orgs.get(r["organization_id"])
        taken = seat_rows.get(r["organization_id"], 0) or 0
        by_org.append({"organization": org_brief(org) if org else None, "kind": "school" if org else "private",
                       "sessions": r["sessions"], "completed_sessions": r["completed"], "capacity": r["capacity"] or 0,
                       "seats_confirmed": taken, "load_pct": pct(taken, r["capacity"] or 0)})
    by_org.sort(key=lambda r: (r["kind"] != "private", -(r["sessions"])))

    metrics = [
        metric("profile_views", "Просмотры профиля", views, "count",
               "Квалифицированные profile_viewed карточки инструктора за период (без ботов, самопросмотров, повторов)"),
        metric("inquiries", "Обращения", inquiries.count(), "count", "Обращения к инструктору, созданные за период"),
        metric("bookings", "Записи", created.count(), "count",
               "Записи на занятия, где вы инструктор (школы и частные), созданные за период"),
        metric("bookings_confirmed", "Подтверждённые записи", confirmed_count, "count",
               "Записи, подтверждённые за период (факт смены статуса на сервере)"),
        metric("conversion", "Конверсия просмотр → обращение/запись", pct(len(leads), views), "percent",
               "Уникальные клиенты с обращением или записью на частное занятие / просмотры профиля × 100%"),
        metric("unique_students", "Уникальные ученики", unique, "count",
               "Ученики с ≥1 завершённым занятием за период"),
        metric("repeat_students", "Повторные ученики", repeat_pct, "percent",
               "Ученики с ≥2 завершёнными занятиями / ученики с ≥1 завершённым занятием × 100% (за период)"),
        metric("completed_lessons", "Проведено занятий", completed_lessons, "count",
               "Занятия периода, отмеченные проведёнными (по факту, а не по плану)"),
        metric("load", "Загруженность", pct(seats, capacity), "percent",
               "Подтверждённые места / вместимость ваших неотменённых занятий периода × 100%"),
        metric("cancellation_share", "Доля отмен", pct(cancelled, considered), "percent",
               "Отменённые записи / все записи на занятия периода (кроме отклонённых) × 100%"),
        metric("rating", "Средняя оценка", rating_avg, "rating",
               "Сумма оценок опубликованных отзывов / число опубликованных отзывов (за всё время)"),
        metric("reviews", "Опубликованных отзывов", rating_count, "count", "Опубликованные отзывы об инструкторе"),
    ]
    breakdowns = {
        "by_organization": by_org,
        "cancellations_by_side": by_side,
        "repeat_students_count": repeat,
    }
    return {"account": account_brief(account)}, metrics, breakdowns


# --- школа (MET-05, SCH-12) ------------------------------------------------------------------------------------

def school_metrics(account, organization_id, period):
    if organization_id:
        org = _requested_org(account, organization_id, [Organization.Kind.SCHOOL])
    else:
        orgs = _member_orgs(account, Organization.Kind.SCHOOL)
        if not orgs:
            _unavailable("Статистика школы доступна владельцу и сотрудникам школы.")
        if len(orgs) > 1:
            raise DomainError("organization_required", "Выберите школу.",
                              fields={"organization_id": ["У вас несколько школ — укажите organization_id."]})
        org = orgs[0]
    sessions = LessonSession.objects.filter(organization=org, **in_period("starts_at", period))
    held = sessions.exclude(status=LessonSession.Status.CANCELLED)
    capacity = held.aggregate(n=Sum("capacity"))["n"] or 0
    bookings = Booking.objects.filter(kind=Booking.Kind.LESSON, lesson_session__organization=org,
                                      **in_period("lesson_session__starts_at", period))
    seat_bookings = bookings.filter(status__in=SEAT_STATUSES).exclude(lesson_session__status=LessonSession.Status.CANCELLED)
    seats = seat_bookings.aggregate(n=Sum("seats"))["n"] or 0
    confirmed_sessions = held.filter(Exists(Booking.objects.filter(lesson_session=OuterRef("pk"),
                                                                   status__in=SEAT_STATUSES))).count()
    completed_sessions = sessions.filter(status=LessonSession.Status.COMPLETED).count()
    attended = bookings.filter(status=B.COMPLETED).count()
    no_show = bookings.filter(status=B.NO_SHOW).count()
    unique, repeat, repeat_pct = repeat_stats(bookings.filter(status=B.COMPLETED))
    created = Booking.objects.filter(kind=Booking.Kind.LESSON, lesson_session__organization=org,
                                     **in_period("created_at", period))
    views = AnalyticsEvent.objects.filter(name=AnalyticsEvent.Name.ORGANIZATION_VIEWED, owner_organization=org,
                                          **in_period("occurred_at", period)).count()
    bookers = created.values("customer_id").distinct().count()
    cancelled, considered, by_side = cancellation_stats(bookings)
    programs = SchoolProgram.objects.filter(organization=org, is_active=True).count()
    rating_avg, rating_count = _rating(Review.objects.filter(organization=org))

    instructors = []
    rows = (held.filter(instructor__isnull=False).order_by().values("instructor_id")
            .annotate(sessions=Count("id"), capacity=Sum("capacity"),
                      completed=Count("id", filter=Q(status=LessonSession.Status.COMPLETED))))
    from apps.accounts.models import Account

    people = {a.pk: a for a in Account.objects.filter(pk__in=[r["instructor_id"] for r in rows])
              .select_related("profile__avatar", "instructor_profile")}
    per_instr = defaultdict(lambda: {"seats": 0, "completed": 0, "no_show": 0})
    for row in (bookings.exclude(lesson_session__status=LessonSession.Status.CANCELLED)
                .filter(lesson_session__instructor__isnull=False).order_by()
                .values("lesson_session__instructor_id", "status").annotate(seats=Sum("seats"), n=Count("id"))):
        bucket = per_instr[row["lesson_session__instructor_id"]]
        if row["status"] in SEAT_STATUSES:
            bucket["seats"] += row["seats"] or 0
        if row["status"] == B.COMPLETED:
            bucket["completed"] += row["n"]
        if row["status"] == B.NO_SHOW:
            bucket["no_show"] += row["n"]
    for r in rows:
        person = people.get(r["instructor_id"])
        profile = getattr(person, "instructor_profile", None) if person else None
        stats = per_instr[r["instructor_id"]]
        i_avg, i_count = _rating(Review.objects.filter(instructor=profile)) if profile else (None, 0)
        instructors.append({
            "instructor": account_brief(person) if person else None,
            "sessions": r["sessions"], "completed_sessions": r["completed"], "capacity": r["capacity"] or 0,
            "seats_confirmed": stats["seats"], "fill_rate_pct": pct(stats["seats"], r["capacity"] or 0),
            "attendance_pct": pct(stats["completed"], stats["completed"] + stats["no_show"]),
            "rating_avg": i_avg, "rating_count": i_count,
        })
    instructors.sort(key=lambda r: -r["sessions"])
    by_program = []
    for row in (held.order_by().values("program_id", "program__title")
                .annotate(sessions=Count("id"), capacity=Sum("capacity"))):
        taken = seat_bookings.filter(lesson_session__program_id=row["program_id"]).aggregate(n=Sum("seats"))["n"] or 0
        by_program.append({"program_id": str(row["program_id"]) if row["program_id"] else None,
                           "title": row["program__title"] or "Без программы", "sessions": row["sessions"],
                           "capacity": row["capacity"] or 0, "seats_confirmed": taken,
                           "fill_rate_pct": pct(taken, row["capacity"] or 0)})

    metrics = [
        metric("fill_rate", "Заполняемость групп", pct(seats, capacity), "percent",
               "Подтверждённые места / доступные места неотменённых занятий периода × 100%"),
        metric("programs", "Программ", programs, "count", "Активные программы школы на текущий момент"),
        metric("sessions_planned", "Занятий в расписании", held.count(), "count",
               "Неотменённые занятия школы с началом в периоде"),
        metric("sessions_confirmed", "Подтверждённые занятия", confirmed_sessions, "count",
               "Неотменённые занятия периода, где есть хотя бы одна подтверждённая запись"),
        metric("sessions_completed", "Проведено занятий", completed_sessions, "count",
               "Занятия периода, отмеченные проведёнными"),
        metric("attendance", "Посещаемость", pct(attended, attended + no_show), "percent",
               "Пришедшие (completed) / (пришедшие + неявки) по занятиям периода × 100%"),
        metric("unique_students", "Уникальные ученики", unique, "count",
               "Ученики с ≥1 завершённым занятием за период"),
        metric("repeat_students", "Повторные ученики", repeat_pct, "percent",
               "Ученики с ≥2 завершёнными занятиями / ученики с ≥1 завершённым занятием × 100% (за период)"),
        metric("bookings", "Записи", created.count(), "count", "Записи на занятия школы, созданные за период"),
        metric("profile_views", "Просмотры карточки школы", views, "count",
               "Квалифицированные organization_viewed за период"),
        metric("conversion", "Конверсия просмотр → запись", pct(bookers, views), "percent",
               "Уникальные клиенты с записью за период / квалифицированные просмотры карточки школы × 100%"),
        metric("cancellation_share", "Доля отмен", pct(cancelled, considered), "percent",
               "Отменённые записи / все записи на занятия периода (кроме отклонённых) × 100%"),
        metric("rating", "Средняя оценка", rating_avg, "rating",
               "Сумма оценок опубликованных отзывов о школе / число опубликованных отзывов"),
    ]
    breakdowns = {
        "instructors": instructors,
        "programs": by_program,
        "cancellations_by_side": by_side,
        "repeat_students_count": repeat,
        "reviews_count": rating_count,
    }
    return {"organizations": [org_brief(org)]}, metrics, breakdowns


# --- прокат ----------------------------------------------------------------------------------------------------

def rental_metrics(account, organization_id, period):
    if organization_id:
        org = _requested_org(account, organization_id, None)
        items = InventoryItem.objects.filter(owner_organization=org)
        subject = {"organizations": [org_brief(org)]}
    else:
        items = InventoryItem.objects.filter(owner_account=account)
        if not (has_specialty(account, Specialty.RENTAL) or items.exists()):
            _unavailable("Статистика проката доступна после подключения направления «Прокат».")
        subject = {"account": account_brief(account)}
    items = items.filter(purpose__in=[InventoryItem.Purpose.RENTAL, InventoryItem.Purpose.BOTH]).exclude(
        status=InventoryItem.Status.RETIRED)
    item_ids = list(items.values_list("pk", flat=True))
    now = timezone.now()
    rentals = Booking.objects.filter(kind=Booking.Kind.RENTAL, inventory_item_id__in=item_ids)
    booked_now_ids = set(rentals.filter(status__in=[B.CONFIRMED, B.IN_PROGRESS], starts_at__lte=now,
                                        ends_at__gt=now).values_list("inventory_item_id", flat=True))
    free_now = items.filter(status=InventoryItem.Status.AVAILABLE, is_published=True).exclude(
        pk__in=booked_now_ids).count()
    overlapping = rentals.filter(starts_at__lt=period.end, ends_at__gt=period.start)
    active = overlapping.filter(status__in=RENTAL_ACTIVE)
    duration = ExpressionWrapper(Least(F("ends_at"), Value(period.end)) - Greatest(F("starts_at"), Value(period.start)),
                                 output_field=DurationField())
    booked = active.annotate(d=duration).aggregate(total=Sum("d"))["total"]
    booked_hours = booked.total_seconds() / 3600 if booked else 0
    available_hours = len(item_ids) * period.days * 24
    revenue = revenue_rows(rentals.filter(status=B.COMPLETED, amount_confirmed=True, price_amount__isnull=False,
                                          **in_period("completed_at", period)), "price_amount")
    main = main_currency(revenue)
    cancelled, considered, by_side = cancellation_stats(rentals.filter(**in_period("starts_at", period)))
    views = AnalyticsEvent.objects.filter(name=AnalyticsEvent.Name.ITEM_VIEWED, subject_type="inventory_item",
                                          subject_id__in=[str(pk) for pk in item_ids],
                                          **in_period("occurred_at", period)).count()
    by_kind = []
    for row in items.order_by().values("kind").annotate(n=Count("id")).order_by("kind"):
        kind_ids = set(items.filter(kind=row["kind"]).values_list("pk", flat=True))
        by_kind.append({"kind": row["kind"], "items": row["n"], "booked_now": len(kind_ids & booked_now_ids)})
    top = []
    for row in (active.order_by().values("inventory_item_id", "inventory_item__title")
                .annotate(bookings=Count("id"), d=Sum(duration)).order_by("-bookings")[:10]):
        top.append({"item_id": str(row["inventory_item_id"]), "title": row["inventory_item__title"],
                    "bookings": row["bookings"], "hours": round(row["d"].total_seconds() / 3600, 1) if row["d"] else 0})

    metrics = [
        metric("items", "Единиц в прокате", len(item_ids), "count",
               "Экземпляры для аренды (аренда или продажа+аренда), кроме списанных"),
        metric("free_now", "Свободно сейчас", free_now, "count",
               "Доступные опубликованные экземпляры без подтверждённой/выданной брони в текущий момент"),
        metric("booked_now", "Забронировано сейчас", len(booked_now_ids), "count",
               "Экземпляры с подтверждённой или выданной бронью, интервал которой включает текущий момент"),
        metric("bookings_confirmed", "Подтверждённые брони", active.count(), "count",
               "Брони в статусах подтверждена/выдана/возвращена, пересекающиеся с периодом"),
        metric("utilization", "Загрузка", pct(booked_hours, available_hours), "percent",
               "Часы подтверждённых броней внутри периода / (число экземпляров × часы периода) × 100%"),
        metric("item_views", "Просмотры объявлений", views, "count", "Квалифицированные item_viewed за период"),
        metric("cancellation_share", "Доля отмен", pct(cancelled, considered), "percent",
               "Отменённые брони / все брони с началом в периоде (кроме отклонённых) × 100%"),
        metric("revenue_confirmed", "Подтверждённая выручка", main["amount"], "money",
               "Сумма price_amount возвращённых (completed) за период броней с amount_confirmed=true",
               currency=main["currency"]),
    ]
    breakdowns = {
        "by_kind": by_kind,
        "top_items": top,
        "revenue_by_currency": revenue,
        "cancellations_by_side": by_side,
        "booked_hours": round(booked_hours, 1),
    }
    return subject, metrics, breakdowns


# --- GG Surfer (MET-06) ----------------------------------------------------------------------------------------

def surfer_metrics(account, organization_id, period):
    from apps.community.models import SurfSession

    diary = SurfSession.objects.filter(account=account, date__gte=period.date_from, date__lte=period.date_to)
    ride_days = diary.values("date").distinct().count()
    spots = {}
    for row in diary.order_by().values("spot_id", "spot__slug", "spot__name", "spot_name").annotate(
            days=Count("date", distinct=True)):
        key = str(row["spot_id"]) if row["spot_id"] else (row["spot_name"] or "").strip().lower()
        if not key:
            continue
        entry = spots.setdefault(key, {"spot": ({"slug": row["spot__slug"], "name": row["spot__name"]}
                                                if row["spot_id"] else None),
                                       "name": row["spot__name"] or row["spot_name"], "days": 0})
        entry["days"] += row["days"]
    minutes = diary.aggregate(n=Sum("duration_min"))["n"] or 0
    by_month = [{"month": f"{row['date__year']:04d}-{row['date__month']:02d}", "days": row["days"]}
                for row in diary.order_by().values("date__year", "date__month")
                .annotate(days=Count("date", distinct=True)).order_by("date__year", "date__month")]
    lessons = Booking.objects.filter(customer=account, kind=Booking.Kind.LESSON, status=B.COMPLETED,
                                     **in_period("lesson_session__starts_at", period)).count()
    metrics = [
        metric("ride_days", "Дней катания", ride_days, "days", "Разные даты записей дневника за период"),
        metric("sessions", "Записей в дневнике", diary.count(), "count", "Записи дневника катания за период"),
        metric("visited_spots", "Посещённые споты", len(spots), "count",
               "Разные споты (или названия мест) в записях дневника за период"),
        metric("ride_minutes", "Время в воде", minutes, "minutes", "Сумма указанной длительности записей дневника"),
        metric("lessons_completed", "Пройдено занятий", lessons, "count",
               "Ваши записи на занятия, завершённые в периоде"),
    ]
    breakdowns = {
        "spots": sorted(spots.values(), key=lambda r: (-r["days"], r["name"] or "")),
        "by_month": by_month,
    }
    return {"account": account_brief(account)}, metrics, breakdowns


HANDLERS = {
    "shaper": shaper_metrics,
    "instructor": instructor_metrics,
    "school": school_metrics,
    "rental": rental_metrics,
    "surfer": surfer_metrics,
}


def compute(account, scope, period, organization_id=None):
    subject, metrics, breakdowns = HANDLERS[scope](account, organization_id, period)
    return {
        "scope": scope,
        "period": period.as_dict(),
        "rule_version": RULE_VERSION,
        "generated_at": timezone.now().isoformat(),
        "subject": subject,
        "metrics": metrics,
        "breakdowns": breakdowns,
    }
