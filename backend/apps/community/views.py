import datetime as dt

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserProfile
from apps.common.exceptions import DomainError
from apps.community.models import SurfSession
from apps.community.serializers import (
    DiaryEntrySerializer,
    DiaryEntryWriteSerializer,
    DiaryStatsSerializer,
    SurferCardSerializer,
    SurferDetailSerializer,
)
from apps.community.services import diary, surfers


def parse_date_param(request, name):
    value = request.query_params.get(name)
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        raise DomainError("validation_error", "Неверный формат даты.",
                          fields={name: ["Ожидается YYYY-MM-DD."]}) from None


def _apply_date_range(qs, request):
    date_from, date_to = parse_date_param(request, "from"), parse_date_param(request, "to")
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


SURFER_FILTERS = [
    OpenApiParameter("region", OpenApiTypes.STR, description="slug или id региона (только у разрешивших показ)"),
    OpenApiParameter("spot", OpenApiTypes.STR, description="slug или id любимого спота"),
    OpenApiParameter("level", OpenApiTypes.STR, enum=[c for c, _ in UserProfile.Level.choices]),
    OpenApiParameter("interest", OpenApiTypes.STR),
    OpenApiParameter("board_type", OpenApiTypes.STR),
    OpenApiParameter("q", OpenApiTypes.STR, description="Имя, handle, о себе, интересы"),
]
DATE_FILTERS = [OpenApiParameter("from", OpenApiTypes.DATE), OpenApiParameter("to", OpenApiTypes.DATE)]


class SurferListView(generics.ListAPIView):
    """Каталог GG Surfer: только участники с отдельным согласием (BR-12, ACC-06)."""

    permission_classes = [AllowAny]
    serializer_class = SurferCardSerializer

    def get_queryset(self):
        level = self.request.query_params.get("level")
        if level and level not in UserProfile.Level.values:
            raise DomainError("validation_error", "Неизвестный уровень катания.",
                              fields={"level": [f"Допустимо: {', '.join(UserProfile.Level.values)}."]})
        qs = surfers.gg_profiles_for(self.request.user)
        return surfers.filter_profiles(qs, self.request.query_params).order_by("-updated_at", "account_id")

    @extend_schema(parameters=SURFER_FILTERS, summary="Каталог участников GG Surfer", tags=["community"])
    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        blocked = surfers.blocked_account_ids(request.user)
        return self.get_paginated_response([surfers.surfer_card(p, request.user, blocked) for p in page])


class SurferDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: SurferDetailSerializer, 404: OpenApiResponse(description="Нет анкеты GG Surfer")},
        summary="Анкета участника GG Surfer (+ статистика видимых записей дневника). "
                "Для старого handle отвечает {\"redirect\": \"<новый>\"}",
        tags=["community"],
    )
    def get(self, request, handle):
        profile, redirect = surfers.get_surfer(handle, request.user)
        if redirect:
            return Response({"redirect": redirect})
        stats = diary.compute_stats(diary.visible_entries(profile.account, request.user), public=True)
        return Response(surfers.surfer_detail(profile, request.user, stats))


class SurferDiaryView(generics.ListAPIView):
    """Записи дневника участника по видимости: public — всем, community — участникам GG Surfer, private — никому."""

    permission_classes = [AllowAny]
    serializer_class = DiaryEntrySerializer

    def get_queryset(self):
        profile, redirect = surfers.get_surfer(self.kwargs["handle"], self.request.user)
        if redirect:
            profile = surfers.gg_profiles_for(self.request.user).get(handle=redirect)
        self.public = profile.account_id != getattr(self.request.user, "pk", None)
        qs = diary.visible_entries(profile.account, self.request.user)
        return diary.with_relations(_apply_date_range(qs, self.request))

    @extend_schema(parameters=DATE_FILTERS, summary="Дневник участника (только видимые записи)", tags=["community"])
    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([diary.entry_data(e, public=self.public) for e in page])


class MyDiaryView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DiaryEntrySerializer

    def get_queryset(self):
        qs = SurfSession.objects.filter(account=self.request.user)
        qs = _apply_date_range(qs, self.request)
        visibility = self.request.query_params.get("visibility")
        if visibility:
            qs = qs.filter(visibility=visibility)
        spot = self.request.query_params.get("spot")
        if spot:
            obj = surfers.lookup_public_spot(spot)
            qs = qs.filter(spot=obj) if obj else qs.none()
        return diary.with_relations(qs)

    @extend_schema(
        parameters=DATE_FILTERS + [
            OpenApiParameter("visibility", OpenApiTypes.STR, enum=SurfSession.Visibility.values),
            OpenApiParameter("spot", OpenApiTypes.STR, description="slug или id спота"),
        ],
        summary="Мой дневник катания", tags=["community"],
    )
    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([diary.entry_data(e) for e in page])

    @extend_schema(request=DiaryEntryWriteSerializer, responses={201: DiaryEntrySerializer},
                   summary="Добавить запись дневника", tags=["community"])
    def post(self, request, *args, **kwargs):
        data = DiaryEntryWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        entry = diary.create_entry(request.user, dict(data.validated_data))
        return Response(diary.entry_data(entry), status=status.HTTP_201_CREATED)


class MyDiaryEntryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=DiaryEntrySerializer, summary="Запись моего дневника", tags=["community"])
    def get(self, request, pk):
        return Response(diary.entry_data(diary.get_own_entry(request.user, pk)))

    def _update(self, request, pk, partial):
        entry = diary.get_own_entry(request.user, pk)
        data = DiaryEntryWriteSerializer(data=request.data, partial=partial)
        data.is_valid(raise_exception=True)
        entry = diary.update_entry(entry, request.user, dict(data.validated_data))
        return Response(diary.entry_data(entry))

    @extend_schema(request=DiaryEntryWriteSerializer, responses=DiaryEntrySerializer,
                   summary="Изменить запись дневника", tags=["community"])
    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    @extend_schema(request=DiaryEntryWriteSerializer, responses=DiaryEntrySerializer,
                   summary="Заменить запись дневника", tags=["community"])
    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    @extend_schema(responses={204: None}, summary="Удалить запись дневника", tags=["community"])
    def delete(self, request, pk):
        diary.delete_entry(diary.get_own_entry(request.user, pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyDiaryStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=DiaryStatsSerializer, summary="Моя статистика катания (MET-06)", tags=["community"])
    def get(self, request):
        return Response(diary.compute_stats(SurfSession.objects.filter(account=request.user)))

