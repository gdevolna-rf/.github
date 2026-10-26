"""Тонкие представления learning: права → сервис → сериализатор (docs/ARCHITECTURE.md §3 learning)."""
from django.db.models import Prefetch, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import HandleRedirect
from apps.analytics.services.periods import resolve_period
from apps.commerce.models import Booking
from apps.common.exceptions import NotFound
from apps.learning import serializers as s
from apps.learning.models import (
    InstructorCertificate,
    InstructorMedia,
    InstructorOffer,
    InstructorProfile,
    LessonSession,
    SchoolProgram,
    WaitlistEntry,
)
from apps.learning.services import catalog, instructors, sessions, students, waitlist
from apps.learning.services.access import (
    SCHOOL_STAFF_ROLES,
    get_own_profile,
    get_school,
    get_session_for,
    require_instructor,
)
from apps.learning.services.common import with_seats
from apps.organizations.models import Membership
from apps.organizations.services.access import MANAGE_ROLES, organization_ids_for
from apps.trust.services.audit import record
from apps.trust.services.restrictions import require_can_publish

ALL_ROLES = tuple(Membership.Role.values)
SESSION_RELATED = ("organization__region", "program", "offer__instructor__account", "spot__region",
                   "instructor__profile__avatar", "instructor__instructor_profile")

PERIOD_PARAMS = [
    OpenApiParameter("from", OpenApiTypes.STR, description="Дата YYYY-MM-DD или ISO datetime (включительно)"),
    OpenApiParameter("to", OpenApiTypes.STR, description="Дата YYYY-MM-DD (включительно) или ISO datetime"),
    OpenApiParameter("tz", OpenApiTypes.STR, description="IANA-часовой пояс границ (по умолчанию Europe/Moscow)"),
]


def session_queryset():
    return with_seats(LessonSession.objects.select_related(*SESSION_RELATED))


def manage_queryset():
    """Для кабинетов: + сводка броней и очередь ожидания одним запросом на страницу."""
    return session_queryset().prefetch_related(
        Prefetch("bookings", queryset=Booking.objects.only("id", "status", "lesson_session_id"),
                 to_attr="summary_bookings"),
        Prefetch("waitlist", queryset=WaitlistEntry.objects.filter(status=WaitlistEntry.Status.WAITING).only(
            "id", "session_id"), to_attr="waiting_entries"),
    )


def _filter_sessions(qs, params, *, default_future=True):
    if params.get("from") or params.get("to"):
        period = resolve_period(params, future_days=30, max_days=366)
        qs = qs.filter(starts_at__gte=period.start, starts_at__lt=period.end)
    status_value = params.get("status")
    if status_value:
        qs = qs.filter(status__in=[v for v in status_value.split(",") if v in LessonSession.Status.values])
    if params.get("instructor_id"):
        qs = qs.filter(instructor_id=params["instructor_id"])
    if params.get("program_id"):
        qs = qs.filter(program_id=params["program_id"])
    return qs.order_by("starts_at", "pk")


SESSION_LIST_PARAMS = PERIOD_PARAMS + [
    OpenApiParameter("status", OpenApiTypes.STR, description="scheduled,in_progress,completed,cancelled (через запятую)"),
    OpenApiParameter("instructor_id", OpenApiTypes.UUID),
    OpenApiParameter("program_id", OpenApiTypes.UUID),
]


class InstructorCabinetMixin:
    """Инструменты инструктора доступны при подключённом направлении (BR-11)."""

    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_instructor(request.user)

    def profile(self, required=True):
        if not hasattr(self, "_profile"):
            self._profile = get_own_profile(self.request.user, required=required)
        return self._profile


# --- публичный каталог -----------------------------------------------------------------------------------------

class _NoFormatOverride:
    URL_FORMAT_OVERRIDE = None


class FormatFilterNegotiation(DefaultContentNegotiation):
    """В каталоге ?format= — фильтр формата занятий (individual/group…), а не выбор рендерера DRF."""

    settings = _NoFormatOverride()


@extend_schema(tags=["instructors"], parameters=[
    OpenApiParameter("region", OpenApiTypes.STR, description="slug региона"),
    OpenApiParameter("spot", OpenApiTypes.STR, description="slug спота"),
    OpenApiParameter("level", OpenApiTypes.STR, description="уровень учеников: beginner|intermediate|advanced|pro"),
    OpenApiParameter("board_type", OpenApiTypes.STR, description="код типа доски (shortboard, longboard…)"),
    OpenApiParameter("format", OpenApiTypes.STR, description="individual|pair|group|kids"),
    OpenApiParameter("price_max", OpenApiTypes.NUMBER),
    OpenApiParameter("certificate", OpenApiTypes.STR, description="verified | uploaded (загружен или проверен) | none | any"),
    OpenApiParameter("date", OpenApiTypes.DATE, description="есть свободное окно в этот день"),
    OpenApiParameter("tz", OpenApiTypes.STR, description="часовой пояс для date (по умолчанию — регион или Europe/Moscow)"),
    OpenApiParameter("rating_min", OpenApiTypes.NUMBER),
    OpenApiParameter("q", OpenApiTypes.STR),
    OpenApiParameter("ordering", OpenApiTypes.STR, description="rating | reviews | price | experience | newest"),
])
class InstructorCatalogView(generics.ListAPIView):
    """Каталог сёрф-инструкторов (INS-09, BR-01): только опубликованные карточки активных аккаунтов."""

    permission_classes = [AllowAny]
    serializer_class = s.InstructorCardSerializer
    content_negotiation_class = FormatFilterNegotiation

    def get_queryset(self):
        return catalog.filter_catalog(catalog.annotated(catalog.public_profiles()), self.request.query_params)


class InstructorDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["instructors"], responses={
        200: OpenApiResponse(s.InstructorDetailSerializer,
                             description="Профиль. Для старого handle — {\"redirect\": \"<новый handle>\"}."),
        404: OpenApiResponse(description="Не найден или не опубликован")})
    def get(self, request, handle):
        base = catalog.annotated(InstructorProfile.objects.all())
        profile = catalog.annotated(catalog.public_profiles()).filter(account__profile__handle=handle).first()
        if profile is None and request.user.is_authenticated:
            profile = base.filter(account=request.user, account__profile__handle=handle).first()  # предпросмотр своей
        if profile is None:
            redirect = HandleRedirect.objects.filter(old_handle=handle).select_related("account__profile").first()
            if redirect and catalog.public_profiles().filter(account=redirect.account).exists():
                return Response({"redirect": redirect.account.profile.handle})
            raise NotFound("Инструктор не найден.")
        return Response(s.InstructorDetailSerializer(profile, context={"request": request}).data)


# --- кабинет инструктора ---------------------------------------------------------------------------------------

def _own_profile_response(profile, request, status_code=200):
    profile = catalog.annotated(InstructorProfile.objects.filter(pk=profile.pk)).first()
    return Response(s.InstructorOwnSerializer(profile, context={"request": request}).data, status=status_code)


class MyInstructorView(InstructorCabinetMixin, APIView):
    @extend_schema(tags=["instructor-cabinet"], responses={200: s.InstructorOwnSerializer})
    def get(self, request):
        return _own_profile_response(self.profile(), request)

    @extend_schema(tags=["instructor-cabinet"], request=s.InstructorProfileWriteSerializer,
                   responses={200: s.InstructorOwnSerializer})
    def put(self, request):
        serializer = s.InstructorProfileWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _own_profile_response(instructors.save_profile(request.user, serializer.validated_data), request)

    @extend_schema(tags=["instructor-cabinet"], request=s.InstructorProfileWriteSerializer,
                   responses={200: s.InstructorOwnSerializer})
    def patch(self, request):
        serializer = s.InstructorProfileWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return _own_profile_response(instructors.save_profile(request.user, serializer.validated_data), request)


class PublishView(InstructorCabinetMixin, APIView):
    @extend_schema(tags=["instructor-cabinet"], request=None, responses={200: s.InstructorOwnSerializer})
    def post(self, request):
        return _own_profile_response(instructors.publish(request.user, request), request)


class UnpublishView(InstructorCabinetMixin, APIView):
    @extend_schema(tags=["instructor-cabinet"], request=None, responses={200: s.InstructorOwnSerializer})
    def post(self, request):
        return _own_profile_response(instructors.unpublish(request.user, request), request)


def _media_list(profile):
    return s.InstructorMediaSerializer(profile.media_items.select_related("media").order_by("position", "id"),
                                       many=True).data


class MyMediaView(InstructorCabinetMixin, APIView):
    @extend_schema(tags=["instructor-cabinet"], responses={200: s.InstructorMediaSerializer(many=True)})
    def get(self, request):
        return Response(_media_list(self.profile()))

    @extend_schema(tags=["instructor-cabinet"], request=s.InstructorMediaAddSerializer,
                   responses={201: s.InstructorMediaSerializer})
    def post(self, request):
        serializer = s.InstructorMediaAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = instructors.add_media(self.profile(), serializer.validated_data["media_id"], request.user)
        return Response(s.InstructorMediaSerializer(item).data, status=status.HTTP_201_CREATED)

    @extend_schema(tags=["instructor-cabinet"], request=s.InstructorMediaReorderSerializer,
                   responses={200: s.InstructorMediaSerializer(many=True)}, summary="Новый порядок галереи",
                   operation_id="me_instructor_media_reorder")
    def patch(self, request):
        serializer = s.InstructorMediaReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instructors.reorder_media(self.profile(), serializer.validated_data["ids"])
        return Response(_media_list(self.profile()))


class MyMediaItemView(InstructorCabinetMixin, APIView):
    def _item(self, pk):
        item = InstructorMedia.objects.filter(pk=pk, profile=self.profile()).first()
        if item is None:
            raise NotFound("Файл галереи не найден.")
        return item

    @extend_schema(tags=["instructor-cabinet"], request=s.InstructorMediaMoveSerializer,
                   responses={200: s.InstructorMediaSerializer(many=True)}, summary="Переместить элемент галереи",
                   operation_id="me_instructor_media_move")
    def patch(self, request, pk):
        serializer = s.InstructorMediaMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instructors.move_media(self._item(pk), serializer.validated_data["position"])
        return Response(_media_list(self.profile()))

    @extend_schema(tags=["instructor-cabinet"], responses={204: None})
    def delete(self, request, pk):
        instructors.remove_media(self._item(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyCertificatesView(InstructorCabinetMixin, APIView):
    @extend_schema(tags=["instructor-cabinet"], responses={200: s.CertificateOwnSerializer(many=True)})
    def get(self, request):
        certs = self.profile().certificates.select_related("document").order_by("-created_at")
        return Response(s.CertificateOwnSerializer(certs, many=True).data)

    @extend_schema(tags=["instructor-cabinet"], request=s.CertificateUploadSerializer,
                   responses={201: s.CertificateOwnSerializer})
    def post(self, request):
        serializer = s.CertificateUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cert = instructors.upload_certificate(self.profile(), request.user, serializer.validated_data, request)
        return Response(s.CertificateOwnSerializer(cert).data, status=status.HTTP_201_CREATED)


class MyCertificateDetailView(InstructorCabinetMixin, APIView):
    def _cert(self, pk):
        cert = InstructorCertificate.objects.filter(pk=pk, instructor=self.profile()).select_related("document").first()
        if cert is None:
            raise NotFound("Сертификат не найден.")
        return cert

    @extend_schema(tags=["instructor-cabinet"], responses={200: s.CertificateOwnSerializer})
    def get(self, request, pk):
        return Response(s.CertificateOwnSerializer(self._cert(pk)).data)

    @extend_schema(tags=["instructor-cabinet"], request=s.CertificateUpdateSerializer,
                   responses={200: s.CertificateOwnSerializer})
    def patch(self, request, pk):
        serializer = s.CertificateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cert = instructors.update_certificate(self._cert(pk), request.user, serializer.validated_data, request)
        return Response(s.CertificateOwnSerializer(cert).data)

    @extend_schema(tags=["instructor-cabinet"], responses={204: None})
    def delete(self, request, pk):
        instructors.delete_certificate(self._cert(pk), request.user, request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CertificateScanView(APIView):
    """Presigned GET на скан (INS-04, ATX-23): публично — только проверенный и разрешённый к показу."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["instructors"], responses={200: s.CertificateScanUrlSerializer, 404: OpenApiResponse(description="Нет доступа")})
    def get(self, request, pk):
        return Response(instructors.scan_url(pk, request))


@extend_schema(tags=["instructor-cabinet"], parameters=[OpenApiParameter("active", OpenApiTypes.BOOL)])
class MyOffersView(InstructorCabinetMixin, generics.ListCreateAPIView):
    serializer_class = s.OfferSerializer

    def get_queryset(self):
        qs = InstructorOffer.objects.filter(instructor=self.profile()).select_related("spot__region")
        active = self.request.query_params.get("active")
        if active in ("true", "1"):
            qs = qs.filter(is_active=True)
        elif active in ("false", "0"):
            qs = qs.filter(is_active=False)
        return qs.order_by("-is_active", "price", "title")

    def perform_create(self, serializer):
        require_can_publish(self.request.user)
        offer = serializer.save(instructor=self.profile())
        record(self.request.user, "instructor_offer.created", offer, request=self.request)


@extend_schema(tags=["instructor-cabinet"])
class MyOfferDetailView(InstructorCabinetMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = s.OfferSerializer

    def get_queryset(self):
        return InstructorOffer.objects.filter(instructor=self.profile()).select_related("spot__region")

    def perform_update(self, serializer):
        require_can_publish(self.request.user)
        offer = serializer.save()
        record(self.request.user, "instructor_offer.updated", offer, request=self.request)

    def perform_destroy(self, instance):
        instructors.delete_offer(instance, self.request.user, self.request)


@extend_schema(tags=["instructor-cabinet"])
class MySessionsView(InstructorCabinetMixin, generics.ListCreateAPIView):
    """Слоты частных занятий по своим предложениям; пересечение с уроками школ → 409 instructor_busy (F11)."""

    serializer_class = s.SessionManageSerializer

    def get_queryset(self):
        qs = manage_queryset().filter(organization__isnull=True, offer__instructor=self.profile())
        return _filter_sessions(qs, self.request.query_params)

    @extend_schema(parameters=SESSION_LIST_PARAMS)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=s.PrivateSessionCreateSerializer, responses={201: s.SessionManageSerializer})
    def post(self, request, *args, **kwargs):
        serializer = s.PrivateSessionCreateSerializer(data=request.data, context={"profile": self.profile()})
        serializer.is_valid(raise_exception=True)
        session = sessions.create_private_session(self.profile(), request.user, serializer.validated_data, request)
        return Response(s.SessionManageSerializer(session_queryset().get(pk=session.pk)).data,
                        status=status.HTTP_201_CREATED)


class MySessionDetailView(InstructorCabinetMixin, APIView):
    def _session(self, pk):
        session = session_queryset().filter(pk=pk, organization__isnull=True, offer__instructor=self.profile()).first()
        if session is None:
            raise NotFound("Занятие не найдено.")
        return session

    @extend_schema(tags=["instructor-cabinet"], responses={200: s.SessionManageSerializer})
    def get(self, request, pk):
        return Response(s.SessionManageSerializer(self._session(pk)).data)

    @extend_schema(tags=["instructor-cabinet"], request=s.PrivateSessionUpdateSerializer,
                   responses={200: s.SessionManageSerializer})
    def patch(self, request, pk):
        session = self._session(pk)
        serializer = s.PrivateSessionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sessions.update_session(session, request.user, serializer.validated_data, request)
        return Response(s.SessionManageSerializer(session_queryset().get(pk=pk)).data)

    @extend_schema(tags=["instructor-cabinet"], responses={204: None})
    def delete(self, request, pk):
        sessions.delete_session(self._session(pk), request.user, request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyScheduleView(APIView):
    """Единое расписание инструктора: занятия всех школ и частные уроки (INS-07, SCH-06, AT-06)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["instructor-cabinet"], parameters=PERIOD_PARAMS + [
        OpenApiParameter("status", OpenApiTypes.STR, description="фильтр статусов через запятую")],
        responses={200: inline_serializer("ScheduleResponse", {
            "period": inline_serializer("SchedulePeriod", {
                "from": serializers.DateField(), "to": serializers.DateField(), "timezone": serializers.CharField(),
                "starts_at": serializers.DateTimeField(), "ends_at": serializers.DateTimeField()}),
            "results": s.ScheduleItemSerializer(many=True)})})
    def get(self, request):
        period = resolve_period(request.query_params, future_days=30, max_days=93)
        qs = (session_queryset().filter(instructor=request.user, starts_at__lt=period.end, ends_at__gt=period.start)
              .prefetch_related(Prefetch(
                  "bookings", to_attr="schedule_bookings",
                  queryset=Booking.objects.exclude(status__in=[Booking.Status.DECLINED, Booking.Status.CANCELLED])
                  .select_related("customer__profile__avatar").order_by("created_at"))))
        status_value = request.query_params.get("status")
        if status_value:
            qs = qs.filter(status__in=status_value.split(","))
        context = {"request": request, "managed_org_ids": set(organization_ids_for(request.user, roles=MANAGE_ROLES))}
        items = s.ScheduleItemSerializer(qs.order_by("starts_at", "pk"), many=True, context=context).data
        return Response({"period": period.as_dict(), "results": items})


STUDENTS_PAGE = inline_serializer("MyStudentsPage", {
    "count": serializers.IntegerField(), "next": serializers.URLField(allow_null=True),
    "previous": serializers.URLField(allow_null=True), "summary": s.StudentsSummarySerializer(),
    "results": s.MyStudentRowSerializer(many=True)})
SCHOOL_STUDENTS_PAGE = inline_serializer("SchoolStudentsPage", {
    "count": serializers.IntegerField(), "next": serializers.URLField(allow_null=True),
    "previous": serializers.URLField(allow_null=True), "summary": s.StudentsSummarySerializer(),
    "results": s.SchoolStudentRowSerializer(many=True)})


class _StudentsListMixin:
    def students_response(self, bookings, row_serializer, note_filter, *, require_completed=False):
        rows = students.aggregate_students(bookings, require_completed=require_completed)
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            matching = bookings.filter(Q(customer__profile__first_name__icontains=q)
                                       | Q(customer__profile__last_name__icontains=q)
                                       | Q(customer__profile__handle__icontains=q)
                                       | Q(participant_name__icontains=q)).values("customer_id")
            rows = rows.filter(customer_id__in=matching)
        if self.request.query_params.get("repeat") in ("true", "1"):
            rows = rows.filter(completed_count__gte=2)
        page = self.paginate_queryset(rows)
        data = row_serializer(students.hydrate(page, bookings=bookings, note_filter=note_filter), many=True,
                              context={"request": self.request}).data
        response = self.get_paginated_response(data)
        response.data["summary"] = students.summary(students.aggregate_students(bookings))
        return response


class MyStudentsView(InstructorCabinetMixin, _StudentsListMixin, generics.GenericAPIView):
    """Уникальные и повторные ученики по завершённым занятиям, где я вёл урок (INS-06, INS-10)."""

    @extend_schema(tags=["instructor-cabinet"], parameters=[
        OpenApiParameter("q", OpenApiTypes.STR), OpenApiParameter("repeat", OpenApiTypes.BOOL),
        OpenApiParameter("page", OpenApiTypes.INT), OpenApiParameter("page_size", OpenApiTypes.INT)],
        responses={200: STUDENTS_PAGE})
    def get(self, request):
        bookings = students.my_students_bookings(request.user)
        return self.students_response(bookings, s.MyStudentRowSerializer, Q(author=request.user),
                                      require_completed=True)


# --- школа: программы, занятия, ученики (SCH-04…10) ------------------------------------------------------------

class SchoolScopedMixin:
    permission_classes = [IsAuthenticated]
    read_roles = ALL_ROLES
    write_roles = MANAGE_ROLES

    def school(self):
        if not hasattr(self, "_school"):
            roles = self.read_roles if self.request.method in ("GET", "HEAD", "OPTIONS") else self.write_roles
            self._school, self._membership = get_school(self.kwargs["org_id"], self.request.user, roles)
        return self._school


@extend_schema(tags=["school"], parameters=[OpenApiParameter("active", OpenApiTypes.BOOL)])
class OrgProgramsView(SchoolScopedMixin, generics.ListCreateAPIView):
    serializer_class = s.ProgramSerializer

    def get_queryset(self):
        qs = SchoolProgram.objects.filter(organization=self.school())
        active = self.request.query_params.get("active")
        if active in ("true", "1"):
            qs = qs.filter(is_active=True)
        elif active in ("false", "0"):
            qs = qs.filter(is_active=False)
        return qs.order_by("-is_active", "title")

    def perform_create(self, serializer):
        require_can_publish(self.request.user)
        program = serializer.save(organization=self.school())
        record(self.request.user, "school_program.created", program, organization=program.organization,
               request=self.request)


@extend_schema(tags=["school"])
class OrgProgramDetailView(SchoolScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = s.ProgramSerializer

    def get_queryset(self):
        return SchoolProgram.objects.filter(organization=self.school())

    def perform_update(self, serializer):
        require_can_publish(self.request.user)
        program = serializer.save()
        record(self.request.user, "school_program.updated", program, organization=program.organization,
               request=self.request)

    def perform_destroy(self, instance):
        """Программа с занятиями архивируется (занятия и брони ссылаются на неё), без занятий — удаляется."""
        if instance.sessions.exists():
            instance.is_active = False
            instance.save(update_fields=["is_active", "updated_at"])
            record(self.request.user, "school_program.archived", instance, organization=instance.organization,
                   request=self.request)
            return
        record(self.request.user, "school_program.deleted", instance, organization=instance.organization,
               before={"title": instance.title}, request=self.request)
        instance.delete()


@extend_schema(tags=["school"])
class OrgSessionsView(SchoolScopedMixin, generics.ListCreateAPIView):
    serializer_class = s.SessionManageSerializer

    def get_queryset(self):
        return _filter_sessions(manage_queryset().filter(organization=self.school()), self.request.query_params)

    @extend_schema(parameters=SESSION_LIST_PARAMS)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=s.SchoolSessionCreateSerializer, responses={201: s.SessionManageSerializer})
    def post(self, request, *args, **kwargs):
        org = self.school()
        serializer = s.SchoolSessionCreateSerializer(data=request.data, context={"organization": org})
        serializer.is_valid(raise_exception=True)
        session = sessions.create_school_session(org, request.user, serializer.validated_data, request)
        return Response(s.SessionManageSerializer(session_queryset().get(pk=session.pk)).data,
                        status=status.HTTP_201_CREATED)


class OrgSessionDetailView(SchoolScopedMixin, APIView):
    def _session(self, pk):
        session = session_queryset().filter(pk=pk, organization=self.school()).first()
        if session is None:
            raise NotFound("Занятие не найдено.")
        return session

    @extend_schema(tags=["school"], responses={200: s.SessionManageSerializer})
    def get(self, request, org_id, pk):
        return Response(s.SessionManageSerializer(self._session(pk)).data)

    @extend_schema(tags=["school"], request=s.SessionUpdateSerializer, responses={200: s.SessionManageSerializer})
    def patch(self, request, org_id, pk):
        session = self._session(pk)
        serializer = s.SessionUpdateSerializer(data=request.data, context={"session": session})
        serializer.is_valid(raise_exception=True)
        sessions.update_session(session, request.user, serializer.validated_data, request)
        return Response(s.SessionManageSerializer(session_queryset().get(pk=pk)).data)

    @extend_schema(tags=["school"], responses={204: None})
    def delete(self, request, org_id, pk):
        sessions.delete_session(self._session(pk), request.user, request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrgStudentsView(SchoolScopedMixin, _StudentsListMixin, generics.GenericAPIView):
    """Ученики школы из броней: посещаемость, повторность, последнее занятие (SCH-10). Инструктор видит своих."""

    read_roles = SCHOOL_STAFF_ROLES + (Membership.Role.INSTRUCTOR,)

    @extend_schema(tags=["school"], parameters=[
        OpenApiParameter("q", OpenApiTypes.STR), OpenApiParameter("repeat", OpenApiTypes.BOOL),
        OpenApiParameter("page", OpenApiTypes.INT), OpenApiParameter("page_size", OpenApiTypes.INT)],
        responses={200: SCHOOL_STUDENTS_PAGE})
    def get(self, request, org_id):
        org = self.school()
        bookings = students.org_students_bookings(org, self._membership)
        return self.students_response(bookings, s.SchoolStudentRowSerializer,
                                      students.visible_notes_q(request.user) & Q(organization=org))


# --- занятие: публичная карточка и действия --------------------------------------------------------------------

class SessionDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["sessions"], responses={200: s.SessionDetailSerializer})
    def get(self, request, pk):
        session = get_session_for(request.user, pk)
        session = session_queryset().get(pk=session.pk)
        return Response(s.SessionDetailSerializer(session, context={"request": request}).data)


class _SessionActionView(APIView):
    permission_classes = [IsAuthenticated]
    input_serializer = None

    def respond(self, session):
        return Response(s.SessionManageSerializer(session_queryset().get(pk=session.pk)).data)

    def load(self, request, pk):
        session = get_session_for(request.user, pk)
        serializer = self.input_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return session, serializer.validated_data


class SessionAssignView(_SessionActionView):
    input_serializer = s.SessionAssignSerializer

    @extend_schema(tags=["sessions"], request=s.SessionAssignSerializer, responses={200: s.SessionManageSerializer})
    def post(self, request, pk):
        session, data = self.load(request, pk)
        return self.respond(sessions.assign_instructor(session, request.user, data["instructor_id"], request))


class SessionRescheduleView(_SessionActionView):
    input_serializer = s.SessionRescheduleSerializer

    @extend_schema(tags=["sessions"], request=s.SessionRescheduleSerializer, responses={200: s.SessionManageSerializer})
    def post(self, request, pk):
        session, data = self.load(request, pk)
        ends_at = data.get("ends_at") or data["starts_at"] + (session.ends_at - session.starts_at)
        return self.respond(sessions.reschedule(session, request.user, data["starts_at"], ends_at, data["reason"],
                                                request))


class SessionCancelView(_SessionActionView):
    input_serializer = s.SessionCancelSerializer

    @extend_schema(tags=["sessions"], request=s.SessionCancelSerializer, responses={200: s.SessionManageSerializer})
    def post(self, request, pk):
        session, data = self.load(request, pk)
        return self.respond(sessions.cancel_session(session, request.user, data["reason"], request))


class SessionCompleteView(_SessionActionView):
    input_serializer = s.SessionCompleteSerializer

    @extend_schema(tags=["sessions"], request=s.SessionCompleteSerializer, responses={200: s.SessionCompleteResultSerializer})
    def post(self, request, pk):
        session, data = self.load(request, pk)
        session, completed, no_show = sessions.complete_session(session, request.user, data["no_show_booking_ids"],
                                                                request)
        return Response({
            "session": s.SessionManageSerializer(session_queryset().get(pk=session.pk)).data,
            "completed_booking_ids": [str(b.pk) for b in completed],
            "no_show_booking_ids": [str(b.pk) for b in no_show],
        })


class SessionWaitlistView(APIView):
    """Лист ожидания на заполненное занятие (SCH-08)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["sessions"], request=None, responses={201: s.WaitlistEntrySerializer,
                                                               200: s.WaitlistEntrySerializer})
    def post(self, request, pk):
        session = get_session_for(request.user, pk)
        entry, created = waitlist.join(session, request.user)
        return Response(s.WaitlistEntrySerializer(entry).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(tags=["sessions"], responses={204: None})
    def delete(self, request, pk):
        session = get_session_for(request.user, pk)
        waitlist.leave(session, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- заметки об учениках ---------------------------------------------------------------------------------------

@extend_schema(tags=["school"])
class StudentNotesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = s.StudentNoteSerializer

    def get_queryset(self):
        qs = students.visible_notes(self.request.user)
        params = self.request.query_params
        for key, field in (("student", "student_id"), ("organization", "organization_id"), ("session", "session_id")):
            if params.get(key):
                qs = qs.filter(**{field: params[key]})
        return qs.order_by("-created_at")

    @extend_schema(parameters=[OpenApiParameter("student", OpenApiTypes.UUID),
                               OpenApiParameter("organization", OpenApiTypes.UUID),
                               OpenApiParameter("session", OpenApiTypes.UUID)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=s.StudentNoteCreateSerializer, responses={201: s.StudentNoteSerializer})
    def post(self, request):
        serializer = s.StudentNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = students.create_note(request.user, serializer.validated_data, request)
        return Response(s.StudentNoteSerializer(note, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)


class StudentNoteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["school"], responses={200: s.StudentNoteSerializer})
    def get(self, request, pk):
        note = students.get_note_for(request.user, pk)
        return Response(s.StudentNoteSerializer(note, context={"request": request}).data)

    @extend_schema(tags=["school"], request=s.StudentNoteUpdateSerializer, responses={200: s.StudentNoteSerializer})
    def patch(self, request, pk):
        note = students.get_note_for(request.user, pk)
        serializer = s.StudentNoteUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        note = students.update_note(request.user, note, serializer.validated_data, request)
        return Response(s.StudentNoteSerializer(note, context={"request": request}).data)

    @extend_schema(tags=["school"], responses={204: None})
    def delete(self, request, pk):
        note = students.get_note_for(request.user, pk)
        students.delete_note(request.user, note, request)
        return Response(status=status.HTTP_204_NO_CONTENT)

