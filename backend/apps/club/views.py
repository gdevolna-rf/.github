from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers_public import PublicAccountSerializer
from apps.club.content import CLUB_ABOUT
from apps.club.models import ClubEvent, EventRegistration
from apps.club.serializers import (
    ClubAnnouncementWriteSerializer,
    ClubEventCardSerializer,
    ClubEventDetailSerializer,
    ClubEventWriteSerializer,
    ClubOverviewSerializer,
    ClubManagedAnnouncementSerializer,
    ClubManagedEventSerializer,
    ClubManagedRegistrationSerializer,
    ClubRegistrationResultSerializer,
)
from apps.club.services import events as service
from apps.club.services import manage
from apps.community.services.surfers import members_count
from apps.search.services.catalog import spot_ref

UPCOMING_ON_OVERVIEW = 6
ANNOUNCEMENTS_ON_OVERVIEW = 5


class IsClubManager(BasePermission):
    """Серверная роль organizer или администратор с 2FA (CLB-03)."""

    message = "Управление клубом доступно организаторам и администраторам."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and manage.is_club_manager(request))


class ClubOverviewView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=ClubOverviewSerializer, summary="Страница клуба: о проекте, статистика, анонсы, события",
                   tags=["club"])
    def get(self, request):
        upcoming = service.upcoming_events()
        return Response({
            "about": CLUB_ABOUT,
            "stats": {"members": members_count(), "upcoming_events": upcoming.count()},
            "announcements": [service.announcement_data(a)
                              for a in service.published_announcements()[:ANNOUNCEMENTS_ON_OVERVIEW]],
            "upcoming_events": [service.event_card(e) for e in upcoming[:UPCOMING_ON_OVERVIEW]],
        })


EVENT_FILTERS = [
    OpenApiParameter("from", OpenApiTypes.DATE, description="Начало окна календаря (дата или ISO 8601)"),
    OpenApiParameter("to", OpenApiTypes.DATE, description="Конец окна (включительно для даты)"),
    OpenApiParameter("kind", OpenApiTypes.STR, enum=ClubEvent.Kind.values),
    OpenApiParameter("region", OpenApiTypes.STR, description="slug или id региона"),
    OpenApiParameter("spot", OpenApiTypes.STR, description="slug или id спота"),
]


class ClubEventListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ClubEventCardSerializer

    def get_queryset(self):
        return service.filter_events(service.public_events(), self.request.query_params)

    @extend_schema(parameters=EVENT_FILTERS, summary="Календарь клубных событий (без окна — предстоящие)",
                   tags=["club"])
    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([service.event_card(e) for e in page])


class ClubEventDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=ClubEventDetailSerializer, summary="Карточка события (+ my_registration)", tags=["club"])
    def get(self, request, slug):
        return Response(service.event_detail(service.get_public_event(slug), request.user))


class ClubEventRegistrationView(APIView):
    permission_classes = [IsAuthenticated]

    def _result(self, registration, event_id):
        data = service.registration_data(registration)
        data["event"] = service.event_card(service.reload_event(event_id))
        return data

    @extend_schema(request=None, responses={201: ClubRegistrationResultSerializer, 200: ClubRegistrationResultSerializer},
                   summary="Зарегистрироваться (registered или waitlist; идемпотентно)", tags=["club"])
    def post(self, request, pk):
        registration, created = service.register(pk, request.user)
        return Response(self._result(registration, registration.event_id),
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(responses={204: None}, summary="Отменить регистрацию (место получает первый из листа ожидания)",
                   tags=["club"])
    def delete(self, request, pk):
        service.cancel_registration(pk, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- управление (организатор / админ)

def managed_event_data(event):
    data = service.event_card(event)
    data.update({
        "description": event.description,
        "my_registration": None,
        "spot": spot_ref(event.spot) if event.spot_id else None,
        "registration_open_flag": event.registration_open,
        "reminder_sent_at": event.reminder_sent_at,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    })
    return data


def managed_registration_data(registration):
    data = service.registration_data(registration)
    data.update({
        "account": PublicAccountSerializer(registration.account).data,
        "cancelled_at": registration.cancelled_at,
        "reminder_sent_at": registration.reminder_sent_at,
    })
    return data


def managed_announcement_data(announcement):
    data = service.announcement_data(announcement)
    data.update({
        "is_published": announcement.published_at is not None,
        "author": PublicAccountSerializer(announcement.author).data if announcement.author_id else None,
        "created_at": announcement.created_at,
        "updated_at": announcement.updated_at,
    })
    return data


class ManageEventListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsClubManager]
    serializer_class = ClubManagedEventSerializer

    def get_queryset(self):
        qs = manage.manageable_events(self.request).order_by("-starts_at", "id")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @extend_schema(parameters=[OpenApiParameter("status", OpenApiTypes.STR, enum=ClubEvent.Status.values)],
                   summary="Мои события (организатор) / все (админ)", tags=["club-manage"])
    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([managed_event_data(e) for e in page])

    @extend_schema(request=ClubEventWriteSerializer, responses={201: ClubManagedEventSerializer},
                   summary="Создать событие (slug генерируется сервером)", tags=["club-manage"])
    def post(self, request, *args, **kwargs):
        data = ClubEventWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        event = manage.create_event(request.user, request, dict(data.validated_data))
        return Response(managed_event_data(service.reload_event(event.pk)), status=status.HTTP_201_CREATED)


class ManageEventDetailView(APIView):
    permission_classes = [IsAuthenticated, IsClubManager]

    @extend_schema(responses=ClubManagedEventSerializer, summary="Событие (управление)", tags=["club-manage"])
    def get(self, request, pk):
        return Response(managed_event_data(manage.get_manageable_event(request, pk)))

    def _update(self, request, pk, partial):
        data = ClubEventWriteSerializer(data=request.data, partial=partial)
        data.is_valid(raise_exception=True)
        event = manage.update_event(request, pk, dict(data.validated_data))
        return Response(managed_event_data(service.reload_event(event.pk)))

    @extend_schema(request=ClubEventWriteSerializer, responses=ClubManagedEventSerializer,
                   summary="Изменить событие; status=cancelled отменяет и уведомляет участников", tags=["club-manage"])
    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    @extend_schema(request=ClubEventWriteSerializer, responses=ClubManagedEventSerializer, summary="Заменить событие",
                   tags=["club-manage"])
    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    @extend_schema(responses={204: None}, summary="Удалить событие без регистраций (иначе — отмена)",
                   tags=["club-manage"])
    def delete(self, request, pk):
        manage.delete_event(request, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ManageEventRegistrationsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsClubManager]
    serializer_class = ClubManagedRegistrationSerializer

    def get_queryset(self):
        return manage.event_registrations(self.request, self.kwargs["pk"], self.request.query_params.get("status"))

    @extend_schema(
        parameters=[OpenApiParameter("status", OpenApiTypes.STR, enum=EventRegistration.Status.values,
                                     description="По умолчанию — активные (registered + waitlist)")],
        summary="Участники события (публичные данные, без контактов)", tags=["club-manage"])
    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([managed_registration_data(r) for r in page])


class ManageAnnouncementListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsClubManager]
    serializer_class = ClubManagedAnnouncementSerializer

    def get_queryset(self):
        return manage.manageable_announcements(self.request)

    @extend_schema(summary="Анонсы клуба (свои / все для админа)", tags=["club-manage"])
    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([managed_announcement_data(a) for a in page])

    @extend_schema(request=ClubAnnouncementWriteSerializer, responses={201: ClubManagedAnnouncementSerializer},
                   summary="Создать анонс", tags=["club-manage"])
    def post(self, request, *args, **kwargs):
        data = ClubAnnouncementWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        announcement = manage.create_announcement(request, dict(data.validated_data))
        return Response(managed_announcement_data(announcement), status=status.HTTP_201_CREATED)


class ManageAnnouncementDetailView(APIView):
    permission_classes = [IsAuthenticated, IsClubManager]

    @extend_schema(responses=ClubManagedAnnouncementSerializer, summary="Анонс (управление)", tags=["club-manage"])
    def get(self, request, pk):
        return Response(managed_announcement_data(manage.get_manageable_announcement(request, pk)))

    def _update(self, request, pk, partial):
        data = ClubAnnouncementWriteSerializer(data=request.data, partial=partial)
        data.is_valid(raise_exception=True)
        return Response(managed_announcement_data(manage.update_announcement(request, pk, dict(data.validated_data))))

    @extend_schema(request=ClubAnnouncementWriteSerializer, responses=ClubManagedAnnouncementSerializer,
                   summary="Изменить анонс", tags=["club-manage"])
    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    @extend_schema(request=ClubAnnouncementWriteSerializer, responses=ClubManagedAnnouncementSerializer,
                   summary="Заменить анонс", tags=["club-manage"])
    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    @extend_schema(responses={204: None}, summary="Удалить анонс", tags=["club-manage"])
    def delete(self, request, pk):
        manage.delete_announcement(request, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
