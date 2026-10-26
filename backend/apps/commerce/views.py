"""Тонкие представления: права → сервис → сериализатор (docs/dev/BACKEND_GUIDE.md)."""
import datetime as dt

from django.db.models import F, Prefetch, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.commerce import serializers as s
from apps.commerce.models import Booking, Inquiry
from apps.commerce.services import access
from apps.commerce.services import bookings as booking_service
from apps.commerce.services import inquiries as inquiry_service
from apps.common.exceptions import DomainError
from apps.common.idempotency import HEADER, run_idempotent
from apps.inventory.models import InventoryItemPhoto
from apps.messaging.services import conversations as chat
from apps.organizations.models import Organization

IDEMPOTENCY_PARAM = OpenApiParameter(HEADER, OpenApiTypes.STR, OpenApiParameter.HEADER, required=False,
                                     description="Повтор запроса с тем же ключом не создаёт дубль (9.1)")


def idempotent_create(request, endpoint, handler):
    """Повторы с одним Idempotency-Key сериализуются advisory-lock'ом внутри run_idempotent."""
    return run_idempotent(request, endpoint, handler)


def _csv(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _parse_bound(value, name):
    """Граница периода: дата (ГГГГ-ММ-ДД; для to — включительно) или ISO 8601 с временем."""
    if not value:
        return None
    day = parse_date(value) if len(value) == 10 else None
    if day is not None:
        parsed = timezone.make_aware(dt.datetime.combine(day, dt.time.min))
        return parsed + dt.timedelta(days=1) if name == "to" else parsed
    parsed = parse_datetime(value)
    if parsed is None:
        raise DomainError("validation_error", "Неверная дата.", fields={name: ["Ожидается ISO 8601."]})
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


# --- обращения ---------------------------------------------------------------------------------------------------------

# Фильтр «роль» единого inbox (MSG-01): к какому профессиональному кабинету относится входящее обращение.
ROLE_FILTERS = {
    "shaper": lambda: Q(provider_organization__kind=Organization.Kind.WORKSHOP),
    "school": lambda: Q(provider_organization__kind=Organization.Kind.SCHOOL),
    "instructor": lambda: (Q(provider_account__isnull=False, inventory_item__isnull=True)
                           & Q(kind__in=[Inquiry.Kind.LESSON, Inquiry.Kind.PROGRAM, Inquiry.Kind.GENERAL])),
    "rental": lambda: (Q(kind=Inquiry.Kind.RENTAL) | Q(provider_organization__kind=Organization.Kind.RENTAL)
                       | (Q(inventory_item__isnull=False)
                          & ~Q(provider_organization__kind=Organization.Kind.WORKSHOP))),
}


def inquiry_queryset(user):
    return (Inquiry.objects.select_related(
        "customer__profile__avatar", "provider_account__profile__avatar", "provider_account__instructor_profile",
        "customer__instructor_profile", "provider_organization__logo", "conversation",
    ))


class InquiryListCreateView(GenericAPIView):
    serializer_class = s.InquiryListSerializer

    @extend_schema(
        summary="Единый inbox обращений (MSG-01/02/07, ATX-27)",
        parameters=[
            OpenApiParameter("box", str, enum=["incoming", "outgoing"]),
            OpenApiParameter("role", str, enum=["customer", "shaper", "school", "instructor", "rental"]),
            OpenApiParameter("status", str, description="Один или несколько через запятую"),
            OpenApiParameter("kind", str, description="Один или несколько через запятую"),
            OpenApiParameter("organization", OpenApiTypes.UUID),
            OpenApiParameter("unread", bool, description="Только с непрочитанными"),
            OpenApiParameter("page", int), OpenApiParameter("page_size", int),
        ],
        responses=s.InquiryListSerializer(many=True),
    )
    def get(self, request):
        user = request.user
        org_ids = access.provider_org_ids(user)
        qs = inquiry_queryset(user).filter(access.visible_inquiries_q(user, org_ids))
        box = request.query_params.get("box")
        if box == "incoming":
            qs = qs.filter(access.incoming_inquiries_q(user, org_ids))
        elif box == "outgoing":
            qs = qs.filter(access.outgoing_inquiries_q(user))
        elif box:
            raise DomainError("validation_error", "box: incoming или outgoing.", fields={"box": ["Неверное значение."]})
        role = request.query_params.get("role")
        if role == "customer":
            qs = qs.filter(access.outgoing_inquiries_q(user))
        elif role in ROLE_FILTERS:
            qs = qs.filter(access.incoming_inquiries_q(user, org_ids)).filter(ROLE_FILTERS[role]())
        elif role:
            raise DomainError("validation_error", "Неизвестная роль.", fields={"role": ["Неверное значение."]})
        statuses = _csv(request.query_params.get("status"))
        if statuses:
            qs = qs.filter(status__in=statuses)
        kinds = _csv(request.query_params.get("kind"))
        if kinds:
            qs = qs.filter(kind__in=kinds)
        organization = request.query_params.get("organization")
        if organization:
            qs = qs.filter(provider_organization_id=organization)
        qs = qs.annotate(
            _unread=chat.unread_count_expression(user, "conversation__id"),
            _last_message_id=chat.last_message_id_expression("conversation__id"),
            _conversation_id=F("conversation__id"),
            _activity=Coalesce("conversation__last_message_at", "updated_at"),
        )
        if request.query_params.get("unread") in ("1", "true", "yes"):
            qs = qs.filter(_unread__gt=0)
        qs = qs.order_by("-_activity", "-created_at")
        page = self.paginate_queryset(qs)
        context = self.get_serializer_context()
        context["last_messages"] = chat.last_messages_by_id([getattr(i, "_last_message_id", None) for i in page])
        data = s.InquiryListSerializer(page, many=True, context=context).data
        return self.get_paginated_response(data)

    @extend_schema(
        summary="Создать обращение + чат + первое сообщение (AT-01, MSG-03/09)",
        request=s.InquiryCreateSerializer, responses={201: s.InquiryDetailSerializer},
        parameters=[IDEMPOTENCY_PARAM],
    )
    def post(self, request):
        def handler():
            serializer = s.InquiryCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            inquiry = inquiry_service.create_inquiry(request.user, request=request, **serializer.validated_data)
            return Response(_inquiry_detail(inquiry, request), status=status.HTTP_201_CREATED)

        return idempotent_create(request, "inquiries", handler)


def _inquiry_detail(inquiry, request):
    inquiry = (inquiry_queryset(request.user).prefetch_related("history__actor__profile__avatar", "milestones",
                                                              "bookings")
               .get(pk=inquiry.pk))
    conversation = getattr(inquiry, "conversation", None)
    context = {"request": request}
    if conversation is not None:
        chat.ensure_participant(conversation, request.user)
        last_id = (conversation.messages.filter(is_hidden=False).order_by("-created_at")
                   .values_list("id", flat=True).first())
        inquiry._last_message_id = last_id
        context["last_messages"] = chat.last_messages_by_id([last_id])
    return s.InquiryDetailSerializer(inquiry, context=context).data


class InquiryDetailView(GenericAPIView):
    serializer_class = s.InquiryDetailSerializer

    @extend_schema(summary="Обращение: история, этапы, детали, снимок объекта", responses=s.InquiryDetailSerializer)
    def get(self, request, pk):
        inquiry, _side = inquiry_service.get_inquiry_for(request.user, pk)
        return Response(_inquiry_detail(inquiry, request))


class InquiryActionView(GenericAPIView):
    action_name = None
    serializer_class = s.CommerceEmptySerializer

    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        inquiry = inquiry_service.transition_inquiry(
            request.user, pk, self.action_name, reason=data.get("reason", ""),
            agreed_amount=data.get("agreed_amount"), amount_confirmed=data.get("amount_confirmed", False),
            request=request)
        return Response(_inquiry_detail(inquiry, request))


def _inquiry_action(action, serializer_class, summary):
    view = type(f"Inquiry{action.title()}View", (InquiryActionView,),
                {"action_name": action, "serializer_class": serializer_class})
    view.post = extend_schema(summary=summary, request=serializer_class,
                              responses=s.InquiryDetailSerializer)(view.post)
    return view.as_view()


inquiry_accept = _inquiry_action("accept", s.CommerceEmptySerializer, "Принять в работу (исполнитель): new → in_progress")
inquiry_decline = _inquiry_action("decline", s.CommerceReasonSerializer, "Отказать (исполнитель): new|in_progress → declined")
inquiry_complete = _inquiry_action("complete", s.InquiryCompleteSerializer,
                                   "Завершить (исполнитель): in_progress → completed; сумма сделки (MET-07)")
inquiry_cancel = _inquiry_action("cancel", s.CommerceReasonSerializer, "Отменить (клиент): new|in_progress → cancelled")


class MilestoneListCreateView(GenericAPIView):
    serializer_class = s.InquiryMilestoneSerializer
    pagination_class = None

    @extend_schema(summary="Этапы обращения (SHO-06)", responses=s.InquiryMilestoneSerializer(many=True))
    def get(self, request, pk):
        inquiry, _side = inquiry_service.get_inquiry_for(request.user, pk)
        return Response(s.InquiryMilestoneSerializer(inquiry.milestones.all(), many=True).data)

    @extend_schema(summary="Добавить этап (исполнитель)", request=s.InquiryMilestoneSerializer,
                   responses={201: s.InquiryMilestoneSerializer})
    def post(self, request, pk):
        serializer = s.InquiryMilestoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        milestone = inquiry_service.create_milestone(request.user, pk, **serializer.validated_data)
        return Response(s.InquiryMilestoneSerializer(milestone).data, status=status.HTTP_201_CREATED)


class MilestoneDetailView(GenericAPIView):
    serializer_class = s.InquiryMilestoneSerializer

    @extend_schema(summary="Этап", responses=s.InquiryMilestoneSerializer)
    def get(self, request, pk, milestone_id):
        milestone, _inquiry, _side = inquiry_service.get_milestone_of(request.user, pk, milestone_id)
        return Response(s.InquiryMilestoneSerializer(milestone).data)

    @extend_schema(summary="Изменить запланированный этап (исполнитель)", request=s.InquiryMilestoneSerializer,
                   responses=s.InquiryMilestoneSerializer)
    def patch(self, request, pk, milestone_id):
        serializer = s.InquiryMilestoneSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        milestone = inquiry_service.update_milestone(request.user, pk, milestone_id, **serializer.validated_data)
        return Response(s.InquiryMilestoneSerializer(milestone).data)

    @extend_schema(summary="Удалить запланированный этап (исполнитель)", responses={204: None})
    def delete(self, request, pk, milestone_id):
        inquiry_service.delete_milestone(request.user, pk, milestone_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MilestoneDoneView(GenericAPIView):
    serializer_class = s.CommerceEmptySerializer

    @extend_schema(summary="Этап выполнен (исполнитель): planned → done", request=None,
                   responses=s.InquiryMilestoneSerializer)
    def post(self, request, pk):
        milestone = inquiry_service.milestone_done(request.user, pk, request=request)
        return Response(s.InquiryMilestoneSerializer(milestone).data)


class MilestoneConfirmView(GenericAPIView):
    serializer_class = s.CommerceEmptySerializer

    @extend_schema(summary="Подтвердить этап (клиент): done → confirmed", request=None,
                   responses=s.InquiryMilestoneSerializer)
    def post(self, request, pk):
        milestone = inquiry_service.milestone_confirm(request.user, pk, request=request)
        return Response(s.InquiryMilestoneSerializer(milestone).data)


# --- брони -------------------------------------------------------------------------------------------------------------

def booking_queryset():
    return (Booking.objects.select_related(
        "customer__profile__avatar", "provider_account__profile__avatar", "provider_account__instructor_profile",
        "provider_organization__logo", "lesson_session__program", "lesson_session__offer",
        "lesson_session__spot", "lesson_session__instructor__profile__avatar", "inventory_item",
    ).prefetch_related(Prefetch("inventory_item__photos", queryset=InventoryItemPhoto.objects.select_related("media"))))


class BookingListCreateView(GenericAPIView):
    serializer_class = s.BookingSerializer

    @extend_schema(
        summary="Мои брони (box=mine) или брони исполнителя (box=provider)",
        parameters=[
            OpenApiParameter("box", str, enum=["mine", "provider"]),
            OpenApiParameter("status", str, description="Один или несколько через запятую"),
            OpenApiParameter("kind", str, enum=["lesson", "rental"]),
            OpenApiParameter("from", OpenApiTypes.DATETIME, description="starts_at ≥ from (дата или ISO)"),
            OpenApiParameter("to", OpenApiTypes.DATETIME, description="starts_at < to"),
            OpenApiParameter("organization", OpenApiTypes.UUID),
            OpenApiParameter("page", int), OpenApiParameter("page_size", int),
        ],
        responses=s.BookingSerializer(many=True),
    )
    def get(self, request):
        user = request.user
        org_ids = access.provider_org_ids(user)
        box = request.query_params.get("box") or "mine"
        if box == "mine":
            qs = booking_queryset().filter(customer=user)
        elif box == "provider":
            qs = booking_queryset().filter(access.provider_bookings_q(user, org_ids))
        else:
            raise DomainError("validation_error", "box: mine или provider.", fields={"box": ["Неверное значение."]})
        statuses = _csv(request.query_params.get("status"))
        if statuses:
            qs = qs.filter(status__in=statuses)
        kind = request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        start = _parse_bound(request.query_params.get("from"), "from")
        if start:
            qs = qs.filter(ends_at__gt=start)
        end = _parse_bound(request.query_params.get("to"), "to")
        if end:
            qs = qs.filter(starts_at__lt=end)
        organization = request.query_params.get("organization")
        if organization:
            qs = qs.filter(provider_organization_id=organization)
        ordering = "starts_at" if request.query_params.get("order") == "asc" else "-starts_at"
        page = self.paginate_queryset(qs.order_by(ordering, "-created_at"))
        return self.get_paginated_response(s.BookingSerializer(page, many=True,
                                                               context=self.get_serializer_context()).data)

    @extend_schema(summary="Создать бронь: занятие или аренда (status=requested)", request=s.BookingCreateSerializer,
                   responses={201: s.BookingDetailSerializer}, parameters=[IDEMPOTENCY_PARAM])
    def post(self, request):
        def handler():
            serializer = s.BookingCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            if data.get("lesson_session_id"):
                booking = booking_service.create_lesson_booking(
                    request.user, lesson_session_id=data["lesson_session_id"], seats=data["seats"],
                    participant_name=data["participant_name"], participant_is_minor=data["participant_is_minor"],
                    guardian_consent=data["guardian_consent"], customer_note=data["customer_note"],
                    group_with=data.get("group_with"), request=request)
            else:
                booking = booking_service.create_rental_booking(
                    request.user, inventory_item_id=data["inventory_item_id"], starts_at=data["starts_at"],
                    ends_at=data["ends_at"], customer_note=data["customer_note"], group_with=data.get("group_with"),
                    request=request)
            return Response(_booking_detail(booking, request), status=status.HTTP_201_CREATED)

        return idempotent_create(request, "bookings", handler)


def _booking_detail(booking, request):
    booking = booking_queryset().prefetch_related("history__actor__profile__avatar").get(pk=booking.pk)
    return s.BookingDetailSerializer(booking, context={"request": request}).data


class BookingDetailView(GenericAPIView):
    serializer_class = s.BookingDetailSerializer

    @extend_schema(summary="Бронь: карточка, история, связанные брони", responses=s.BookingDetailSerializer)
    def get(self, request, pk):
        booking, _side = booking_service.get_booking_for(request.user, pk)
        return Response(_booking_detail(booking, request))


class BookingActionView(GenericAPIView):
    action_name = None
    serializer_class = s.CommerceEmptySerializer

    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        booking = booking_service.booking_action(request.user, pk, self.action_name, reason=data.get("reason", ""),
                                                 amount_confirmed=data.get("amount_confirmed"), request=request)
        return Response(_booking_detail(booking, request))


def _booking_action(action, serializer_class, summary):
    view = type(f"Booking{action.title().replace('_', '')}View", (BookingActionView,),
                {"action_name": action, "serializer_class": serializer_class})
    view.post = extend_schema(summary=summary, request=serializer_class,
                              responses=s.BookingDetailSerializer)(view.post)
    return view.as_view()


booking_confirm = _booking_action("confirm", s.CommerceEmptySerializer,
                                  "Подтвердить (исполнитель/менеджер/назначенный инструктор); 409 no_seats/resource_taken")
booking_decline = _booking_action("decline", s.CommerceRequiredReasonSerializer, "Отклонить запрос (исполнитель)")
booking_start = _booking_action("start", s.CommerceEmptySerializer, "Начать занятие / выдать инвентарь (исполнитель)")
booking_complete = _booking_action("complete", s.BookingCompleteSerializer,
                                   "Завершить занятие / принять возврат (исполнитель)")
booking_no_show = _booking_action("no_show", s.CommerceEmptySerializer, "Неявка клиента (исполнитель, после начала)")
booking_cancel = _booking_action("cancel", s.CommerceReasonSerializer,
                                 "Отменить: клиент (до начала) или исполнитель (причина обязательна)")
